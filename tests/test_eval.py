"""เทสต์ตัวรัน eval (ใช้ stub ล้วน ไม่ต้องมี API)."""
# รันเคสจริงทั้งหมด 24 ข้อด้วย stub (in-process เร็ว ไม่ใช้เน็ต)

from pathlib import Path  # ใช้เช็กว่าไฟล์รายงานถูกเขียนจริง

from eval.run_eval import main as run_eval_main  # ฟังก์ชันหลักของ eval


def test_run_eval_stub_produces_four_metrics():
    """รัน eval จบ ได้รายงานครบ 4 ตัวเลข พร้อมไฟล์ JSON+Markdown."""
    summary = run_eval_main(["--model", "stub", "--seed", "42"])
    # ครบ 24 เคสตามไฟล์ cases.json
    assert summary["total"] == 24
    assert summary["model"] == "stub"
    # ครบ 4 ตัวเลข (เป็นเลข 0-1 หรือ None ถ้าไม่มีเคสกลุ่มนั้น)
    for key in ("accuracy", "consistency", "invalid_handling", "injection_resistance"):
        assert key in summary["metrics"]
        val = summary["metrics"][key]
        assert val is None or 0.0 <= val <= 1.0
    # ไฟล์รายงานต้องมีจริง (ชื่อมี model+seed)
    assert Path(summary["json"]).name == "eval_stub_seed42.json"
    assert Path(summary["md"]).name == "eval_stub_seed42.md"
    assert Path(summary["json"]).exists()
    assert Path(summary["md"]).exists()
