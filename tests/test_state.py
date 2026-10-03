"""Unit test ของ GameState (ไม่ใช้ LLM รันออฟไลน์ได้)."""
# ใช้ seed คงที่ทุกเทสต์เพื่อให้ทอยซ้ำได้ ผลไม่แกว่ง

from src.state import GameState


# seed คงที่สำหรับทุกเทสต์ (เปลี่ยนเลขนี้แล้วผลทอยเปลี่ยน)
SEED = 42


def new_game() -> GameState:
    """สร้างเกมใหม่ด้วย seed คงที่."""
    return GameState(seed=SEED)


# ---------- ตรวจ state เริ่มเกม ----------

def test_initial_state():
    """state เริ่มต้องตรง GAME_SPEC."""
    g = new_game()
    s = g.get_state()
    assert s["ok"] is True
    assert s["player"]["hp"] == 20
    assert s["player"]["ac"] == 12
    assert s["player"]["position"] == "entrance"
    assert s["player"]["inventory"] == ["potion"]
    assert s["turn_count"] == 0
    assert s["game_over"] is False


# ---------- move: ปกติ / ทะลุกำแพง ----------

def test_move_ok():
    """เดิน north จาก entrance -> hallway สำเร็จ เสีย 1 เทิร์น."""
    g = new_game()
    r = g.move("north")
    assert r["ok"] is True
    assert r["position"] == "hallway"
    assert r["turn_count"] == 1


def test_move_wall_error():
    """เดิน south จาก entrance ไม่มีทางออก = error."""
    g = new_game()
    r = g.move("south")
    assert r["ok"] is False
    assert "ไม่มีทางออก" in r["error"]


def test_move_invalid_direction():
    """ทิศอื่นนอกจาก north/south = error."""
    g = new_game()
    r = g.move("east")
    assert r["ok"] is False
    assert "north" in r["error"]


def test_armory_auto_pickup():
    """เข้าห้อง armory ครั้งแรกต้องเก็บ potion อัตโนมัติ."""
    g = new_game()
    g.player_pos = "hallway"  # วาร์ปไปตั้งหลัก (ไม่เสียเทิร์น เพราะเซ็ตตรง)
    g.enemies["goblin"]["alive"] = False  # ฆ่าก็อบลินก่อน กันโดนสวน
    before = list(g.inventory)
    r = g.move("north")  # hallway -> armory
    assert r["ok"] is True
    assert r["position"] == "armory"
    assert r["picked"] == ["potion"]  # เก็บได้ 1 ขวด
    assert len(g.inventory) == len(before) + 1


# ---------- attack: ปกติ / ผิดห้อง / ตายแล้ว ----------

def test_attack_ok():
    """ยืนห้องเดียวกับ goblin แล้วตี = สำเร็จ เสีย 1 เทิร์น."""
    g = new_game()
    g.player_pos = "hallway"  # ยืนห้องเดียวกับ goblin
    r = g.attack("goblin")
    assert r["ok"] is True
    assert r["turn_count"] == 1
    # ผลต้องมีครบให้ DM เล่า (โดน/พลาด + เลือดที่เหลือ)
    assert "hit" in r and "damage" in r and "target_hp" in r


def test_attack_wrong_room():
    """อยู่ entrance ตี goblin (อยู่ hallway) = error."""
    g = new_game()
    assert g.player_pos == "entrance"
    r = g.attack("goblin")
    assert r["ok"] is False
    assert "คนละห้อง" in r["error"] or "ตีไม่ได้" in r["error"]


def test_attack_dead_enemy():
    """ตีศัตรูที่ตายแล้ว = error."""
    g = new_game()
    g.player_pos = "hallway"
    g.enemies["goblin"]["alive"] = False  # แกล้งฆ่าก่อน
    g.enemies["goblin"]["hp"] = 0
    r = g.attack("goblin")
    assert r["ok"] is False
    assert "ตายแล้ว" in r["error"]


def test_attack_unknown_enemy():
    """ตีชื่อมั่ว = error."""
    g = new_game()
    g.player_pos = "hallway"
    r = g.attack("dragon")
    assert r["ok"] is False
    assert "ไม่รู้จัก" in r["error"]


# ---------- use_item: ปกติ / ของไม่มี / hp เต็ม ----------

def test_use_item_ok():
    """เลือดลดแล้วใช้ potion ฟื้น 8 (ไม่เกิน 20)."""
    g = new_game()
    g.player_hp = 10  # แกล้งเจ็บก่อน
    r = g.use_item("potion")
    assert r["ok"] is True
    assert r["healed"] == 8
    assert r["player_hp"] == 18
    assert "potion" not in r["inventory"]  # ใช้แล้วขวดหาย


def test_use_item_no_potion():
    """ไม่มี potion แล้วกดใช้ = error."""
    g = new_game()
    g.inventory = []  # ทิ้งของหมด
    r = g.use_item("potion")
    assert r["ok"] is False
    assert "ไม่มี potion" in r["error"]


def test_use_item_full_hp():
    """เลือดเต็มแล้วกดใช้ = error (กันกดทิ้ง)."""
    g = new_game()
    assert g.player_hp == 20
    r = g.use_item("potion")
    assert r["ok"] is False
    assert "เต็ม" in r["error"]


def test_use_item_unknown():
    """ของชื่ออื่น = error."""
    g = new_game()
    r = g.use_item("elixir")
    assert r["ok"] is False
    assert "แค่ potion" in r["error"]


# ---------- roll_dice ----------

def test_roll_dice_ok():
    """ทอย d20 ได้เลข 1..20 ไม่เสียเทิร์น."""
    g = new_game()
    before = g.turn_count
    r = g.roll_dice(20)
    assert r["ok"] is True
    assert 1 <= r["result"] <= 20
    assert g.turn_count == before  # ทอยเล่นไม่นับเทิร์น


def test_roll_dice_invalid():
    """ขอเต๋า 7 ด้าน (ไม่อยู่ในรายการ) = error."""
    g = new_game()
    r = g.roll_dice(7)
    assert r["ok"] is False
    assert "sides" in r["error"]


def test_seed_deterministic():
    """seed เดียวกัน ทอยครั้งแรกต้องได้เท่ากัน (ซ้ำได้)."""
    a = GameState(seed=SEED)
    b = GameState(seed=SEED)
    assert a.roll_dice(20)["result"] == b.roll_dice(20)["result"]


# ---------- ชนะ / แพ้ / เกิน 30 เทิร์น ----------

def test_win():
    """ยืน boss_room + ฆ่า orc = ชนะ."""
    g = new_game()
    g.player_pos = "boss_room"  # วาร์ปไปห้องสุดท้าย
    g.enemies["orc"]["hp"] = 1  # แกล้งบอสใกล้ตาย
    g.enemies["orc"]["attack_bonus"] = -100  # กันสวนโดน (เทสต์ชนะอย่างเดียว)
    # ตีจนกว่าจะตาย (กันพลาดเป้า) สูงสุด 10 ครั้ง
    won = False
    for _ in range(10):
        r = g.attack("orc")
        assert r["ok"] is True
        if r["result"] == "win":
            won = True
            break
    assert won is True
    assert g.game_over is True
    assert g.result == "win"


def test_lose_by_death():
    """เลือดเหลือ 2 โดน goblin สวนตาย = แพ้."""
    g = new_game()
    g.player_pos = "hallway"
    g.player_hp = 2  # ใกล้ตาย
    g.enemies["goblin"]["hp"] = 100  # บัฟมอนให้ไม่ตายก่อน
    g.enemies["goblin"]["attack_bonus"] = 100  # ตีโดนชัวร์
    r = g.attack("goblin")  # ตีแล้วโดนสวนตาย
    assert r["ok"] is True
    assert g.player_hp == 0
    assert g.game_over is True
    assert g.result == "lose"


def test_turn_limit():
    """เทิร์นเกิน 30 = แพ้เวลาหมด."""
    g = new_game()
    g.turn_count = 30  # จ่อลิมิต
    g.player_pos = "armory"
    g.enemies["orc"]["attack_bonus"] = -100  # กันตายก่อน (อยากแพ้เวลา)
    r = g.move("north")  # เทิร์นที่ 31
    assert r["ok"] is True
    assert r["turn_count"] == 31
    assert g.game_over is True
    assert g.result == "lose"


# ---------- error ไม่เสียเทิร์น + เกมจบแล้วล็อก ----------

def test_error_no_turn_cost():
    """เรียกผิดกฎ 4 แบบ เทิร์นกับเลือดต้องไม่ขยับ."""
    g = new_game()
    t0 = g.turn_count
    hp0 = g.player_hp
    assert g.move("south")["ok"] is False  # ทะลุกำแพง
    assert g.attack("goblin")["ok"] is False  # ผิดห้อง
    assert g.use_item("elixir")["ok"] is False  # ของผิด
    assert g.roll_dice(7)["ok"] is False  # เต๋าผิด
    assert g.turn_count == t0
    assert g.player_hp == hp0


def test_counter_only_same_room():
    """ใช้ potion ในห้องว่าง (entrance) ต้องไม่มีใครสวน."""
    g = new_game()
    assert g.player_pos == "entrance"  # ไม่มีมอนห้องนี้
    g.player_hp = 10
    r = g.use_item("potion")
    assert r["ok"] is True
    assert r["counter"] == []  # ไม่มีสวน


def test_game_over_blocks_mutation():
    """เกมจบแล้ว move/attack/use ห้ามเปลี่ยน state แต่ get_state ดูได้."""
    g = new_game()
    g.player_pos = "boss_room"
    g.enemies["orc"]["hp"] = 1
    g.enemies["orc"]["attack_bonus"] = -100
    for _ in range(10):  # ตีจนชนะ
        r = g.attack("orc")
        if g.game_over:
            break
    assert g.game_over is True
    t0 = g.turn_count
    assert g.move("south")["ok"] is False  # ล็อก
    assert g.attack("orc")["ok"] is False
    assert g.use_item("potion")["ok"] is False
    assert g.turn_count == t0  # เทิร์นไม่ขยับ
    assert g.get_state()["ok"] is True  # ดูได้อย่างเดียว
