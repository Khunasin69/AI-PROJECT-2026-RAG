"""เทสต์ชั้น MCP server (เรียก tool ผ่าน server ไม่ใช้ LLM)."""
# ทุกเทสต์รีเซ็ตเกมก่อนเสมอ เพราะ server มี GameState ตัวเดียวร่วมกัน

import asyncio  # ใช้เรียก list_tools (เป็น async)
import json  # ใช้แกะผล tool ที่ส่งกลับเป็น JSON text
import os  # ใช้ส่ง GAME_SEED ให้ subprocess
from pathlib import Path  # ใช้หาโฟลเดอร์โปรเจกต์ให้ subprocess รันถูกที่

import src.mcp_server as srv  # โมดูล server ที่จะเทสต์
from src.state import GameState  # state จริง เอาไว้เทียบว่า server คืนค่าตรง


# seed คงที่ให้ผลซ้ำได้
SEED = 42


def test_list_tools_has_five():
    """server ต้อง expose ครบ 5 tools ชื่อตรงสเปก."""
    tools = asyncio.run(srv.mcp.list_tools())
    names = sorted(t.name for t in tools)
    assert names == ["attack", "get_state", "move", "roll_dice", "use_item"]


def test_server_move_ok_and_wall_error():
    """เรียก move ผ่าน server: north สำเร็จ / south ทะลุกำแพง."""
    srv.reset_game(seed=SEED)  # เริ่มเกมใหม่ทุกครั้ง
    ok = srv.move("north")
    assert ok["ok"] is True
    assert ok["position"] == "hallway"
    bad = srv.move("east")  # ทิศผิด (ไม่มีในเกม)
    assert bad["ok"] is False
    assert "error" in bad  # ต้องคืน error อ่านรู้เรื่อง ไม่ throw


def test_server_attack_delegates():
    """เดินไปหา goblin แล้วตีผ่าน server ต้องสำเร็จและเสียเทิร์น."""
    srv.reset_game(seed=SEED)
    srv.move("north")  # entrance -> hallway (ห้อง goblin)
    before = srv.get_state()["turn_count"]
    r = srv.attack("goblin")
    assert r["ok"] is True
    assert srv.get_state()["turn_count"] == before + 1


def test_server_use_item_delegates():
    """เจ็บแล้วใช้ potion ผ่าน server ต้องฟื้น 8."""
    srv.reset_game(seed=SEED)
    srv._get_game().player_hp = 10  # แกล้งเจ็บ (เซ็ตตรง ไม่ผ่าน tool)
    r = srv.use_item("potion")
    assert r["ok"] is True
    assert r["player_hp"] == 18


def test_server_roll_dice():
    """ทอยผ่าน server: 20 ได้ 1..20 / 7 ผิดต้อง error."""
    srv.reset_game(seed=SEED)
    ok = srv.roll_dice(20)
    assert ok["ok"] is True
    assert 1 <= ok["result"] <= 20
    bad = srv.roll_dice(7)
    assert bad["ok"] is False


def test_reset_game_for_eval():
    """reset_game ต้องคืนเกมสด (hp เต็ม อยู่ entrance เทิร์น 0) ใช้เริ่มเกมใหม่ตอน eval."""
    srv.reset_game(seed=SEED)
    srv.move("north")  # เล่นไป 1 ตาให้ state เพี้ยน
    assert srv.get_state()["turn_count"] == 1
    fresh = srv.reset_game(seed=SEED)  # เริ่มใหม่
    assert fresh["ok"] is True
    assert fresh["player"]["hp"] == 20
    assert fresh["player"]["position"] == "entrance"
    assert fresh["turn_count"] == 0


def test_stdio_subprocess_list_and_get_state():
    """เปิด server จริงเป็น subprocess ผ่าน stdio: list ได้ 5 tools และ get_state ตรง state จริง."""
    from mcp import ClientSession, StdioServerParameters  # client ของ MCP
    from mcp.client.stdio import stdio_client  # ตัวเปิด server เป็น subprocess

    root = Path(__file__).resolve().parent.parent  # โฟลเดอร์โปรเจกต์ (ให้ -m หา src เจอ)
    env = dict(os.environ)
    env["GAME_SEED"] = str(SEED)  # ล็อก seed ฝั่ง subprocess ให้เทียบกับ state จริงได้

    async def go() -> None:
        params = StdioServerParameters(command="python", args=["-m", "src.mcp_server"], env=env, cwd=str(root))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()  # จับมือเปิด session
                tools = await session.list_tools()  # ขอรายชื่อ tools
                names = sorted(t.name for t in tools.tools)
                assert names == ["attack", "get_state", "move", "roll_dice", "use_item"]
                res = await session.call_tool("get_state", {})  # เรียก tool จริง
                assert not res.isError
                # FastMCP ส่ง dict กลับเป็น JSON text ใน content ก้อนแรก
                got = json.loads(res.content[0].text)
                want = GameState(seed=SEED).get_state()  # state จริงจาก seed เดียวกัน
                assert got == want  # ต้องตรงกันทั้งก้อน (hp/ห้อง/ของ/เทิร์น)

    asyncio.run(go())
