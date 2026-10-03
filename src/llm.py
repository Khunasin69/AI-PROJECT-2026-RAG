"""Client คุยกับ LLM + stub ออฟไลน์ (interface เดียวกัน สลับกันได้)."""
# ทั้ง StubModel และ RealModel มีเมธอด reply() หน้าตาเดียวกัน agent จึงสลับได้โดยไม่แก้โค้ด

import json  # ใช้แกะ arguments ของ tool call
import os  # ใช้อ่านค่า LLM_* จาก env
from dataclasses import dataclass, field  # สร้างคลาสเก็บข้อมูลแบบง่าย
from typing import Any, Dict, List, Optional  # type hints ให้อ่านง่าย

import httpx  # ยิง HTTP (มากับ mcp อยู่แล้ว ไม่ต้องลงเพิ่ม)
from dotenv import load_dotenv  # โหลดไฟล์ .env เข้า env

load_dotenv()  # อ่าน .env ถ้ามี (ไม่มีก็ข้าม ไม่พัง)


@dataclass
class ToolCall:
    """โมเดลขอเรียก 1 tool (ชื่อ + argument)."""

    name: str
    arguments: Dict[str, Any]


@dataclass
class ModelReply:
    """สิ่งที่โมเดลตอบกลับมา (ข้อความ หรือ ขอเรียก tools)."""

    text: str = ""  # ข้อความเล่าเรื่อง (ถ้ามี)
    tool_calls: List[ToolCall] = field(default_factory=list)  # tools ที่ขอเรียก


# สคีมา tools ทั้ง 5 ตัว (ฟอร์แมต OpenAI เอาไว้ส่งให้โมเดลจริง)
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_state",
            "description": "ดูสถานะปัจจุบัน (ตำแหน่ง HP ของ เวลาเทิร์น)",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move",
            "description": "เดินไปห้องข้างๆ (north/south เท่านั้น)",
            "parameters": {
                "type": "object",
                "properties": {"direction": {"type": "string", "enum": ["north", "south"]}},
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "attack",
            "description": "โจมตีศัตรูที่อยู่ห้องเดียวกัน",
            "parameters": {
                "type": "object",
                "properties": {"target": {"type": "string", "enum": ["goblin", "orc"]}},
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "use_item",
            "description": "ใช้ potion ฟื้น 8 HP",
            "parameters": {
                "type": "object",
                "properties": {"item": {"type": "string", "enum": ["potion"]}},
                "required": ["item"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "ทอยเต๋าเล่น",
            "parameters": {
                "type": "object",
                "properties": {"sides": {"type": "integer", "enum": [4, 6, 8, 10, 12, 20, 100]}},
                "required": ["sides"],
            },
        },
    },
]


class ChatModel:
    """หน้าตากลางของโมเดล (stub กับของจริงสืบทอดคลาสนี้)."""

    kind: str = "base"  # ชื่อชนิดโมเดล (เอาไว้ log)

    def reply(
        self,
        system: str,  # system prompt ของ DM
        messages: List[Dict[str, str]],  # บทสนทนา [{role, content}]
        tools: List[Dict[str, Any]],  # สคีมา tools (stub ไม่ใช้ แต่รับไว้ให้เหมือนกัน)
    ) -> ModelReply:
        """ตอบ 1 ครั้ง (อาจเป็นข้อความ หรือขอเรียก tools)."""
        raise NotImplementedError("คลาสลูกต้องเขียน reply() เอง")


def _has(text: str, words: List[str]) -> bool:
    """เช็กว่าข้อความมีคำไหนในรายการหรือไม่ (ตัวเล็กหมดแล้ว)."""
    return any(w in text for w in words)


class StubModel(ChatModel):
    """โมเดลปลอมรันออฟไลน์ (จับคีย์เวิร์ดไทย/อังกฤษ ไม่ใช้เน็ต)."""

    kind: str = "stub"

    def reply(self, system: str, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> ModelReply:
        """เลือก tool จากข้อความล่าสุด (ผล tool เล่าเป็นข้อความ ไม่เข้าใจก็บอกตรงๆ)."""
        last = messages[-1]  # ดูแค่ก้อนล่าสุดก็พอ (กฎง่ายๆ)
        # --- กรณี 1: ก้อนล่าสุดคือผล tool -> เล่าผลนั้นเป็นภาษาไทย ---
        if last.get("role") == "tool":
            result = json.loads(str(last.get("content", "{}")))
            return ModelReply(text=_narrate_tool(str(last.get("name", "")), result))
        # --- กรณี 2: ข้อความผู้เล่น -> จับคีย์เวิร์ดเลือก tool ---
        text = str(messages[-1].get("content", "")).lower()
        # โจมตีก่อน (เฉพาะสุด) ต้องระบุชื่อเป้า ถ้าไม่ระบุให้ถามกลับ
        if _has(text, ["โจมตี", "ตี", "attack", "kill", "ฟัน", "แทง"]):
            if _has(text, ["goblin", "ก็อบลิน", "ก๊อบลิน"]):
                return ModelReply(tool_calls=[ToolCall("attack", {"target": "goblin"})])
            if _has(text, ["orc", "ออร์ค", "อ๊อค", "บอส", "boss"]):
                return ModelReply(tool_calls=[ToolCall("attack", {"target": "orc"})])
            return ModelReply(text="จะตีตัวไหนเหรอ (goblin หรือ orc)?")
        # เดิน: อ่านทิศจากคำบอกทิศก่อน (เหนือ/ใต้/ตะวันออก/ตะวันตก)
        # เจอทิศไหนส่งทิศนั้นให้ tool (ทิศผิดให้ tool ตอบ error เอง stub ห้ามตัดสิน)
        direction = _read_direction(text)
        if direction is not None:
            return ModelReply(tool_calls=[ToolCall("move", {"direction": direction})])
        # มีแต่คำกริยา (เดิน/ไป) ไม่ระบุทิศ = ถามกลับ ไม่เรียก tool มั่ว
        if _has(text, ["เดิน", "ไป", "go", "ถอย", "กลับ"]):
            return ModelReply(text="จะเดินไปทิศไหนเหรอ (north หรือ south)?")
        # ใช้ยา
        if _has(text, ["potion", "ยา", "ฮีล", "heal", "กิน", "ดื่ม"]):
            return ModelReply(tool_calls=[ToolCall("use_item", {"item": "potion"})])
        # ทอยเต๋า (เจอเลข dN ใช้เลขนั้น ไม่เจอทอย d20)
        if _has(text, ["ทอย", "roll", "เต๋า", "dice", "d20", "d6", "d12", "d100", "d4", "d8", "d10"]):
            return ModelReply(tool_calls=[ToolCall("roll_dice", {"sides": _pick_sides(text)})])
        # ดูสถานะ
        if _has(text, ["สถานะ", "state", "status", "สเตตัส", "สำรวจ", "อยู่ไหน", "ดู", "ห้องไหน", "เช็ก"]):
            return ModelReply(tool_calls=[ToolCall("get_state", {})])
        # ไม่เข้าข่ายไหนเลย = บอกตรงๆ ว่าไม่เข้าใจ ไม่เรียก tool มั่ว
        return ModelReply(text="ขอโทษ ไม่เข้าใจคำสั่ง ลองบอกว่าจะเดินไปไหน ตีตัวอะไร หรือใช้ยา")


def _read_direction(text: str) -> Optional[str]:
    """อ่านทิศจากข้อความ (เจอคำบอกทิศคืนทิศนั้น ไม่เจอคืน None)."""
    # เช็กตะวันออก/ตกก่อน (คำยาว กันไปชนคำสั้น)
    if _has(text, ["ตะวันออก", "east"]):
        return "east"
    if _has(text, ["ตะวันตก", "west"]):
        return "west"
    if _has(text, ["เหนือ", "north"]):
        return "north"
    if _has(text, ["ใต้", "south"]):
        return "south"
    # ดันเจี้ยนเป็นเส้นตรง คำว่าเดินหน้าคือ north (ไม่มีในข้อความ = None)
    if _has(text, ["ข้างหน้า", "เดินหน้า"]):
        return "north"
    return None


def _pick_sides(text: str) -> int:
    """เลือกหน้าเต๋าจากข้อความ (เจอ dN ใช้เลขนั้นก่อน)."""
    for n in (100, 20, 12, 10, 8, 6, 4):  # เช็กเลขใหญ่ก่อน (กัน d1 ไปชน d10)
        if f"d{n}" in text or str(n) in text.split():
            return n
    return 20  # ไม่เจอเลข = ทอย d20


def _narrate_tool(name: str, result: Dict[str, Any]) -> str:
    """เล่าผล tool 1 ครั้งเป็นภาษาไทยสั้นๆ (ตัวเลขเอาจาก result เท่านั้น)."""
    # tool พลาด = บอกตามจริง ห้ามแต่งว่าสำเร็จ
    if not result.get("ok", False):
        return f"ทำไม่ได้: {result.get('error', 'ผิดพลาด')}"
    # สำเร็จแต่ละตัว = เล่าสั้นๆ พร้อมตัวเลขจริง
    if name == "move":
        picked = result.get("picked", [])
        tail = f" เก็บของได้ {picked}" if picked else ""
        return f"ย้ายไป {result.get('position')} แล้ว (HP {result.get('player_hp')}){tail}"
    if name == "attack":
        if result.get("hit"):
            return f"ตีโดน {result.get('damage')} ดาเมจ ศัตรูเหลือ {result.get('target_hp')} (เรา HP {result.get('player_hp')})"
        return f"ตีพลาด! (เรา HP {result.get('player_hp')})"
    if name == "use_item":
        return f"ดื่มยา ฟื้น {result.get('healed')} ตอนนี้ HP {result.get('player_hp')}"
    if name == "roll_dice":
        return f"ทอย d{result.get('sides')} ได้ {result.get('result')}"
    if name == "get_state":
        p = result.get("player", {})
        return f"อยู่ที่ {p.get('position')} HP {p.get('hp')} ของในกระเป๋า {p.get('inventory')}"
    return "เรียบร้อย"


def _read_timeout() -> float:
    """อ่าน LLM_TIMEOUT จาก env (ไม่ตั้ง/ผิดรูปแบบ = 300 วินาที)."""
    try:
        return float(os.getenv("LLM_TIMEOUT", "300"))
    except ValueError:
        return 300.0  # ใส่ตัวเลขไม่ได้ = ใช้ค่าเริ่มต้น


class RealModel(ChatModel):
    """โมเดลจริงผ่าน OpenAI-compatible API (chat completions + tool calling)."""

    kind: str = "real"

    def __init__(
        self,
        base_url: str = "",  # ไม่ส่งมา = อ่านจาก env
        api_key: str = "",  # ไม่ส่งมา = อ่านจาก env
        model: str = "",  # ไม่ส่งมา = อ่านจาก env
        timeout: float = 0,  # ไม่ส่งมา (<=0) = อ่านจาก env
    ) -> None:
        """จำค่า config (base_url ตัด / ท้ายออก กันต่อ path เบิ้ล)."""
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "")
        # ไม่มีคีย์ = บอกตรงๆ ให้ใช้ stub แทน (ไม่แอบรันมั่ว)
        if not self.api_key:
            raise ValueError("ไม่มี LLM_API_KEY ใน .env ให้เล่นด้วย --model stub แทน")
        if not self.model:
            raise ValueError("ไม่มี LLM_MODEL ใน .env ให้ตั้งชื่อโมเดลก่อน")
        self.timeout = timeout if timeout > 0 else _read_timeout()
        self.retries = 1  # หมดเวลาให้ลองใหม่ได้อีก 1 ครั้ง (รวมยิงสูงสุด 2 ครั้ง)

    def _post(self, payload: Dict[str, Any]) -> Any:
        """ยิง HTTP 1 ครั้ง (แยกไว้ให้เทสต์ mock ง่าย)."""
        return httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )

    def reply(self, system: str, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> ModelReply:
        """ยิง chat completions (หมดเวลาลองใหม่ 1 ครั้ง) แล้วแปลง tool_calls กลับเป็นของเรา."""
        payload = {  # body ตามสเปก OpenAI
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "tools": tools,
            "tool_choice": "auto",  # ให้โมเดลเลือกเองว่าจะเรียก tool หรือตอบเลย
        }
        for attempt in (1, 2):  # รอบ 1 = ยิงจริง รอบ 2 = retry
            try:
                resp = self._post(payload)
                resp.raise_for_status()  # status 4xx/5xx ให้ error ทันที
                break  # สำเร็จ = ออกจาก loop
            except httpx.TimeoutException as e:  # หมดเวลา = ลองใหม่ได้อีก 1 ครั้ง
                if attempt == 1:
                    continue  # รอบแรกหมดเวลา = ใช้โควตา retry
                raise RuntimeError(f"เรียก LLM หมดเวลา ({type(e).__name__} timeout={self.timeout}s ลองใหม่ {self.retries} ครั้งแล้ว): {e}") from e
            except Exception as e:  # error อื่น (เน็ต/คีย์/status) ไม่ retry
                raise RuntimeError(f"เรียก LLM ไม่สำเร็จ ({type(e).__name__}): {e}") from e
        msg = resp.json()["choices"][0]["message"]  # เอาข้อความแรกที่โมเดลตอบ
        calls = []  # แปลง tool_calls ของ OpenAI เป็นของเรา
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}  # arguments เพี้ยน = ใช้ dict ว่าง (tool จะด่าเอง)
            calls.append(ToolCall(name=str(fn.get("name", "")), arguments=args))
        return ModelReply(text=str(msg.get("content") or ""), tool_calls=calls)
