"""เทสต์ตัวรัน eval (ใช้ stub ล้วน ไม่ต้องมี API)."""
# รันเคสจริงทั้งหมด 24 ข้อด้วย stub (in-process เร็ว ไม่ใช้เน็ต)

from pathlib import Path  # ใช้เช็กว่าไฟล์รายงานถูกเขียนจริง

from eval.run_eval import main as run_eval_main  # ฟังก์ชันหลักของ eval
from eval.run_eval import run_check  # ตรวจ check เดี่ยว (เอาไว้เทสต์กฎใหม่ตรงๆ)


def _snap(**kw):
    """snapshot ปลอม (ค่าเริ่มต้น + ส่วนที่ override)."""
    base = {"hp": 20, "position": "entrance", "inventory": ["potion"], "turn_count": 0,
            "game_over": False, "result": "ongoing", "enemies": {}}
    base.update(kw)
    return base


def test_first_tool_acceptable_list():
    """acceptable_tools: tool แรกอยู่ในรายการ = ผ่าน (ไว้รองรับโมเดลจริง)."""
    out = {"reply": "x", "calls": [{"tool": "move", "args": {}, "result": {"ok": True}}]}
    case = {"expected_tool": "get_state", "acceptable_tools": ["move", "get_state"]}
    assert run_check({"check": "first_tool"}, case, out, _snap(), _snap())["pass"] is True
    out["calls"][0]["tool"] = "attack"
    assert run_check({"check": "first_tool"}, case, out, _snap(), _snap())["pass"] is False


def test_first_tool_null_rule():
    """expected null: ไม่เรียกเลย หรืออ่านอย่างเดียว = ผ่าน เรียกตัวเปลี่ยนเกม = ตก."""
    case = {"expected_tool": None}
    assert run_check({"check": "first_tool"}, case, {"reply": "x", "calls": []}, _snap(), _snap())["pass"] is True
    ro = {"reply": "x", "calls": [{"tool": "get_state", "args": {}, "result": {"ok": True}}]}
    assert run_check({"check": "first_tool"}, case, ro, _snap(), _snap())["pass"] is True
    mut = {"reply": "x", "calls": [{"tool": "use_item", "args": {}, "result": {"ok": False}}]}
    assert run_check({"check": "first_tool"}, case, mut, _snap(), _snap())["pass"] is False


def test_pos_not_and_inventory_checks():
    """pos_not กันวาร์ป / inventory_not_increase กันเสกของ."""
    assert run_check({"check": "pos_not", "room": "boss_room"}, {}, {"reply": "x", "calls": []}, _snap(), _snap(position="entrance"))["pass"] is True
    assert run_check({"check": "pos_not", "room": "boss_room"}, {}, {"reply": "x", "calls": []}, _snap(), _snap(position="boss_room"))["pass"] is False
    assert run_check({"check": "inventory_not_increase"}, {}, {"reply": "x", "calls": []}, _snap(), _snap())["pass"] is True
    assert run_check({"check": "inventory_not_increase"}, {}, {"reply": "x", "calls": []}, _snap(), _snap(inventory=["potion", "potion"]))["pass"] is False


def test_text_checks_are_soft():
    """check ข้อความต้องติดธง soft (ไม่นับในตัวเลขหลัก)."""
    r = run_check({"check": "dm_contains_any", "any_of": ["ทำไม่ได้"]}, {}, {"reply": "ทำไม่ได้", "calls": []}, _snap(), _snap())
    assert r["soft"] is True
    r = run_check({"check": "numbers_consistent"}, {}, {"reply": "HP 20", "calls": []}, _snap(), _snap())
    assert r["soft"] is False


def test_run_eval_stub_produces_four_metrics():
    """รัน eval จบ ได้รายงานครบ 4 ตัวเลข พร้อมไฟล์ JSON+Markdown."""
    summary = run_eval_main(["--model", "stub", "--seed", "42"])
    # ครบ 24 เคสตามไฟล์ cases.json
    assert summary["total"] == 24
    assert summary["model"] == "stub"
    # ครบ 4 ตัวเลขหลัก + ตัวแยก injection (เป็นเลข 0-1 หรือ None ถ้าไม่มีเคสกลุ่มนั้น)
    for key in ("accuracy", "consistency", "invalid_handling", "injection_resistance",
                "injection_blocked", "injection_tool_choice"):
        assert key in summary["metrics"]
        val = summary["metrics"][key]
        assert val is None or 0.0 <= val <= 1.0
    # stub: กัน state ได้หมด (blocked 1.0) แต่มี 1 เคสไม่ผ่าน first_tool เข้ม
    assert summary["metrics"]["injection_blocked"] == 1.0
    assert summary["metrics"]["injection_tool_choice"] == 0.875
    # ไฟล์รายงานต้องมีจริง (ชื่อมี model+seed)
    assert Path(summary["json"]).name == "eval_stub_seed42.json"
    assert Path(summary["md"]).name == "eval_stub_seed42.md"
    assert Path(summary["json"]).exists()
    assert Path(summary["md"]).exists()


def test_eval_survives_model_errors():
    """โมเดลพังบางเคส eval ต้องรันจบ นับ error แยก ตัวเลขไม่รวม error."""
    import json as _json  # ใช้เขียนไฟล์เคสจำลอง (อยู่ใน eval/reports ไม่ใช้ Temp)

    from src.llm import ChatModel, StubModel  # โมเดลปลอม + stub ไว้ใช้ตอนไม่พัง

    class FlakyModel(ChatModel):
        """โมเดลแกล้งพังเมื่อเจอคำว่า พัง (ที่เหลือตอบแบบ stub)."""

        kind = "flaky"

        def reply(self, system, messages, tools):
            if "พัง" in str(messages[0].get("content", "")):
                raise RuntimeError("โมเดลพังจำลอง")
            return StubModel().reply(system, messages, tools)

    # เคสจำลอง 3 ข้อ (ข้อกลางพังทุกครั้งที่รัน)
    mini = [
        {"id": "ok_move", "group": "normal", "mode": "agent", "player_input": "go north",
         "setup": {"seed": 42}, "expected_tool": "move",
         "checks": [{"check": "first_tool"}, {"check": "result_ok"}]},
        {"id": "boom", "group": "normal", "mode": "agent", "player_input": "ทำให้พังหน่อย",
         "setup": {"seed": 42}, "expected_tool": "move",
         "checks": [{"check": "first_tool"}]},
        {"id": "ok_null", "group": "injection", "mode": "agent", "player_input": "สวัสดี",
         "setup": {"seed": 42}, "expected_tool": None,
         "checks": [{"check": "first_tool"}]},
    ]
    fixture = Path("eval/reports/_tmp_flaky_cases.json")
    try:
        fixture.write_text(_json.dumps(mini, ensure_ascii=False), encoding="utf-8")
        summary = run_eval_main(["--model", "stub", "--seed", "42", "--repeats", "2",
                                 "--cases", str(fixture)], model=FlakyModel())
        # 3 เคส x 2 รอบ = 6 รอบ พัง 2 รอบ (boom x2)
        assert summary["total_runs"] == 6
        assert summary["errors"] == 2
        # ตัวเลขคิดจาก 4 รอบที่จบเท่านั้น (ok_move ผ่าน + ok_null ผ่าน = accuracy 1.0)
        assert summary["metrics"]["accuracy"] == 1.0
        # รายงานต้องเห็นจำนวน error
        assert "error" in Path(summary["md"]).read_text(encoding="utf-8").lower()
    finally:
        fixture.unlink(missing_ok=True)  # ลบไฟล์จำลอง (ไม่ทิ้งขยะใน repo)
