"""MCP server ห่อ 5 tools จาก state.py (ไม่มีตรรกะเกมในไฟล์นี้)."""
# กฎ: ไฟล์นี้แค่ส่งต่อให้ GameState ตัวเดียว ห้ามคำนวณ HP/ดาเมจเอง
# ห้าม print ลง stdout (stdio transport ใช้ช่องนั้นคุย) log ลง stderr เท่านั้น

import os  # ใช้อ่านค่า seed จาก env
import sys  # ใช้เขียน log ลง stderr
from typing import Any, Dict, Optional  # type hints ให้อ่านง่าย

from dotenv import load_dotenv  # โหลดไฟล์ .env เข้า env
from mcp.server.fastmcp import FastMCP  # คลาส server ของ MCP (ต้อง mcp<2)

from src.state import GameState  # คลาสเกมตัวจริง (ตรรกะอยู่ที่นั่น)

load_dotenv()  # อ่าน .env ถ้ามี (ไม่มีก็ข้าม ไม่พัง)


def _log(msg: str) -> None:
    """เขียน log ลง stderr (ห้ามใช้ print เพราะจะกวน stdio)."""
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def _read_seed_from_env() -> Optional[int]:
    """อ่าน GAME_SEED จาก env (ไม่ตั้ง/ผิดรูปแบบ = สุ่ม)."""
    raw = os.getenv("GAME_SEED", "").strip()
    # ไม่ตั้งค่า = สุ่มตามปกติ
    if raw == "":
        return None
    try:
        return int(raw)  # ตั้งเป็นเลข = ล็อก seed ซ้ำได้
    except ValueError:
        _log(f"[server] GAME_SEED={raw!r} ไม่ใช่เลข จะสุ่มแทน")
        return None


# GameState เดียวของ server (แชร์กันทุก tool ตามสเปก)
_game: Optional[GameState] = None


def _get_game() -> GameState:
    """คืนเกมตัวเดียวของ server (ยังไม่มีก็สร้างใหม่)."""
    global _game
    # สร้างครั้งแรกแบบขี้เกียจ (import แล้วไม่สร้างจนกว่าจะมีคนเรียก)
    if _game is None:
        _game = GameState(seed=_read_seed_from_env())
        _log("[server] สร้างเกมใหม่แล้ว")
    return _game


def reset_game(seed: Optional[int] = None) -> Dict[str, Any]:
    """เริ่มเกมใหม่ (ฟังก์ชันธรรมดา ไม่ใช่ tool เอาไว้ให้ eval/เทสต์)."""
    global _game
    # ถ้าไม่ส่ง seed มา ให้ลองอ่านจาก env (ไม่ตั้งก็สุ่ม)
    if seed is None:
        seed = _read_seed_from_env()
    _game = GameState(seed=seed)
    _log(f"[server] รีเซ็ตเกมแล้ว (seed={seed})")
    return _game.get_state()


# สร้าง server ชื่อเกมเรา
mcp = FastMCP("dnd-ai-dm")


@mcp.tool()
def get_state() -> Dict[str, Any]:
    """ดูสถานะปัจจุบัน (ไม่เสียเทิร์น)."""
    return _get_game().get_state()


@mcp.tool()
def move(direction: str) -> Dict[str, Any]:
    """เดิน north/south (สำเร็จเสีย 1 เทิร์น)."""
    return _get_game().move(direction)


@mcp.tool()
def attack(target: str) -> Dict[str, Any]:
    """โจมตี goblin/orc ในห้องเดียวกัน (สำเร็จเสีย 1 เทิร์น)."""
    return _get_game().attack(target)


@mcp.tool()
def use_item(item: str) -> Dict[str, Any]:
    """ใช้ potion ฟื้น 8 HP (สำเร็จเสีย 1 เทิร์น)."""
    return _get_game().use_item(item)


@mcp.tool()
def roll_dice(sides: int) -> Dict[str, Any]:
    """ทอยเต๋าเล่น (ไม่เสียเทิร์น)."""
    return _get_game().roll_dice(sides)


if __name__ == "__main__":
    # รันผ่าน stdio (AI client ต่อมาทางช่องนี้ ห้าม print แทรก)
    mcp.run()
