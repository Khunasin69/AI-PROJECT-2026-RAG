"""เทสต์ RealModel เรื่อง timeout/retry (mock HTTP ไม่ใช้เน็ต)."""
# ไม่ยิงเน็ตจริงแม้แต่ครั้งเดียว (patch httpx.post หมด)

import httpx  # ใช้ชนิด error timeout ของจริง

from src.llm import RealModel  # client ที่จะเทสต์


def _resp():
    """response ปลอม (สำเร็จ)."""

    class FakeResp:
        """เลียนแบบ httpx.Response แค่ 2 เมธอดที่ใช้."""

        def raise_for_status(self):
            """status ดี = ไม่ทำอะไร."""

        def json(self):
            """body ปลอม."""
            return {"choices": [{"message": {"content": "hi", "tool_calls": None}}]}

    return FakeResp()


def test_timeout_read_from_env_and_retry_once(monkeypatch):
    """LLM_TIMEOUT=7 ต้องส่ง timeout=7 ให้ httpx และลองใหม่ 1 ครั้งเมื่อหมดเวลา."""
    monkeypatch.setenv("LLM_TIMEOUT", "7")
    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        """post ปลอม (ครั้งแรกหมดเวลา ครั้งที่สองสำเร็จ)."""
        calls["n"] += 1
        assert kwargs["timeout"] == 7.0  # ต้องใช้ค่าจาก env
        if calls["n"] == 1:
            raise httpx.ReadTimeout("boom")
        return _resp()

    monkeypatch.setattr("src.llm.httpx.post", fake_post)
    model = RealModel(base_url="http://x", api_key="k", model="m")
    out = model.reply("s", [{"role": "user", "content": "hi"}], [])
    assert out.text == "hi"
    assert calls["n"] == 2  # ยิง 2 ครั้ง (จริง 1 + retry 1)


def test_timeout_twice_names_type_and_timeout(monkeypatch):
    """หมดเวลาทั้ง 2 ครั้ง error ต้องบอกชนิด error และ timeout ที่ใช้."""
    monkeypatch.setenv("LLM_TIMEOUT", "9")
    monkeypatch.setattr("src.llm.httpx.post", lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout("slow")))
    model = RealModel(base_url="http://x", api_key="k", model="m")
    try:
        model.reply("s", [{"role": "user", "content": "hi"}], [])
        assert False, "ต้อง raise"
    except RuntimeError as e:
        assert "ReadTimeout" in str(e)  # บอกชนิด error
        assert "9" in str(e)  # บอก timeout ที่ใช้


def test_timeout_default_300(monkeypatch):
    """ไม่ตั้ง LLM_TIMEOUT ต้องได้ 300."""
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    model = RealModel(base_url="http://x", api_key="k", model="m")
    assert model.timeout == 300.0
