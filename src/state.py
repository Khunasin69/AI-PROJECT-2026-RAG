"""GameState เกม D&D ขนาดเล็ก (ไม่มี LLM ในไฟล์นี้)."""
# ไฟล์นี้เป็นเจ้าของ state ทั้งหมด ตัวเลขทุกอย่างมาจากที่นี่เท่านั้น

import json  # ใช้อ่านไฟล์ dungeon.json
import random  # ใช้สุ่มลูกเต๋าแบบใส่ seed ได้
from pathlib import Path  # ใช้หา path ไฟล์ dungeon แบบไม่พึ่ง working dir
from typing import Any, Dict, List, Optional  # type hints ให้อ่านง่าย


# ห้องสุดท้ายของเกม (ชนะเมื่อยืนที่นี่และบอสตาย)
FINAL_ROOM = "boss_room"
# id ของบอส (ชนะเมื่อตัวนี้ตาย)
FINAL_ENEMY = "orc"
# ทิศที่เดินได้มีแค่ 2 ทิศ (ดันเจี้ยนเป็นเส้นตรง)
VALID_DIRECTIONS = ("north", "south")
# หน้าเต๋าที่อนุญาตให้ทอยเล่นได้
VALID_DICE = (4, 6, 8, 10, 12, 20, 100)
# ยาฟื้นกี่ HP (ตรงกับ GAME_SPEC)
POTION_HEAL = 8


class GameState:
    """เก็บ state ทั้งหมดของเกม 1 รอบ (ผู้เล่น 1 คน ศัตรู 2 ตัว)."""

    def __init__(self, dungeon_path: Optional[str] = None, seed: Optional[int] = None) -> None:
        """สร้างเกมใหม่จากไฟล์ dungeon.json."""
        # ถ้าไม่ส่ง path มา ให้หา data/dungeon.json จากตำแหน่งไฟล์นี้เอง
        if dungeon_path is None:
            here = Path(__file__).resolve().parent  # โฟลเดอร์ src/
            dungeon_path = str(here.parent / "data" / "dungeon.json")
        # เปิดไฟล์ด้วย utf-8 เสมอ (มีภาษาไทยในคำอธิบายห้อง)
        with open(dungeon_path, encoding="utf-8") as f:
            data = json.load(f)
        # ตัวสุ่มของเกมนี้ (ใส่ seed แล้วทอยซ้ำได้ เทสต์ง่าย)
        self.rng = random.Random(seed)
        # --- ค่าผู้เล่น (ตรงกับ GAME_SPEC) ---
        p = data["player"]
        self.player_hp: int = int(p["hp"])  # เลือดปัจจุบัน
        self.player_max_hp: int = 20  # เลือดเต็ม
        self.player_ac: int = int(p["ac"])  # ค่าป้องกัน (12)
        self.player_attack_bonus: int = int(p["attack_bonus"])  # โบนัสตี (+4)
        self.player_pos: str = str(p["position"])  # ห้องที่ยืนอยู่
        self.inventory: List[str] = list(p["inventory"])  # ของในกระเป๋า
        # --- ค่าห้อง (id -> ข้อมูลห้อง) ---
        self.rooms: Dict[str, Dict[str, Any]] = {}
        for r in data["rooms"]:
            self.rooms[str(r["id"])] = {
                "name": str(r["name"]),
                "desc": str(r["desc"]),
                "exits": dict(r["exits"]),  # เช่น {"north": "hallway"}
                "items": list(r.get("items", [])),  # ของที่วางในห้อง
            }
        # --- ค่าศัตรู (id -> ข้อมูลศัตรู) ---
        self.enemies: Dict[str, Dict[str, Any]] = {}
        for e in data["enemies"]:
            eid = str(e["id"])
            self.enemies[eid] = {
                "name": str(e.get("name", eid)),
                "hp": int(e["hp"]),
                "max_hp": int(e["hp"]),
                "ac": int(e["ac"]),
                "attack_bonus": int(e["attack_bonus"]),
                "position": str(e["position"]),
                "alive": True,
            }
        # --- ตัวนับเทิร์น / จบเกม ---
        const = data.get("constants", {})
        self.turn_limit: int = int(const.get("turn_limit", 30))  # เกินนี้แพ้
        self.turn_count: int = 0  # เริ่มที่ 0
        self.game_over: bool = False  # จบหรือยัง
        self.result: str = "ongoing"  # ongoing | win | lose

    # ---------- ฟังก์ชันช่วย (private) ----------

    def _check_end(self) -> None:
        """เช็กว่าชนะ/แพ้หรือยัง แล้วตั้ง game_over/result."""
        # เลือดหมด = แพ้ก่อน (สำคัญสุด)
        if self.player_hp <= 0:
            self.player_hp = 0  # กันเลขติดลบ
            self.game_over = True
            self.result = "lose"
            return
        # เดินเกินลิมิต = แพ้ (กันเกมยืด)
        if self.turn_count > self.turn_limit:
            self.game_over = True
            self.result = "lose"
            return
        # ยืนห้องสุดท้ายและบอสตาย = ชนะ
        boss = self.enemies.get(FINAL_ENEMY)
        if boss is not None and self.player_pos == FINAL_ROOM and not boss["alive"]:
            self.game_over = True
            self.result = "win"
            return

    def _enemy_counter(self) -> List[Dict[str, Any]]:
        """ให้ศัตรูในห้องเดียวกันตีสวน คนละ 1 ครั้ง คืน log ให้ DM เล่า."""
        log: List[Dict[str, Any]] = []
        # วนดูศัตรูทุกตัว
        for eid, e in self.enemies.items():
            # ข้ามตัวที่ตายแล้ว หรืออยู่คนละห้อง
            if not e["alive"] or e["position"] != self.player_pos:
                continue
            # ทอย d20 + โบนัส เทียบ AC ผู้เล่น (12)
            roll = self.rng.randint(1, 20)
            total = roll + int(e["attack_bonus"])
            hit = total >= self.player_ac
            dmg = 0
            if hit:
                # โดน = ทอย d6 ลบเลือดผู้เล่น
                dmg = self.rng.randint(1, 6)
                self.player_hp = max(0, self.player_hp - dmg)
            log.append({"enemy": eid, "roll": roll, "total": total, "hit": hit, "damage": dmg})
        return log

    # ---------- 5 tools (public) ----------

    def get_state(self) -> Dict[str, Any]:
        """ดูสถานะปัจจุบัน (ไม่เสียเทิร์น เรียกตอนไหนก็ได้)."""
        room = self.rooms[self.player_pos]  # ห้องที่ยืนอยู่
        # ศัตรูที่ยืนห้องเดียวกัน (DM ใช้เล่าเรื่อง)
        here = [eid for eid, e in self.enemies.items() if e["position"] == self.player_pos and e["alive"]]
        return {
            "ok": True,
            "player": {
                "hp": self.player_hp,
                "max_hp": self.player_max_hp,
                "ac": self.player_ac,
                "position": self.player_pos,
                "inventory": list(self.inventory),
            },
            "current_room": {
                "id": self.player_pos,
                "name": room["name"],
                "desc": room["desc"],
                "exits": dict(room["exits"]),
                "items": list(room["items"]),
            },
            "enemies_here": here,  # id ศัตรูที่เจอในห้องนี้
            "enemies": {eid: dict(e) for eid, e in self.enemies.items()},
            "turn_count": self.turn_count,
            "turn_limit": self.turn_limit,
            "game_over": self.game_over,
            "result": self.result,
        }

    def move(self, direction: str) -> Dict[str, Any]:
        """เดิน north/south (สำเร็จเสีย 1 เทิร์น)."""
        # เกมจบแล้วห้ามเดินต่อ
        if self.game_over:
            return {"ok": False, "error": "เกมจบแล้ว เดินต่อไม่ได้"}
        # รับเฉพาะ north/south (กันพิมพ์มั่ว)
        d = str(direction).strip().lower()
        if d not in VALID_DIRECTIONS:
            return {"ok": False, "error": "ทิศต้องเป็น north หรือ south เท่านั้น"}
        room = self.rooms[self.player_pos]
        # ไม่มีทางออกด้านนั้น = ทะลุกำแพง
        if d not in room["exits"]:
            return {"ok": False, "error": f"เดิน {d} จาก {self.player_pos} ไม่ได้ ไม่มีทางออก"}
        # ย้ายห้อง (ผ่านทุกด่านแล้ว)
        self.player_pos = str(room["exits"][d])
        self.turn_count += 1  # เดินสำเร็จเสีย 1 เทิร์น
        # เข้าห้องแล้วเก็บของอัตโนมัติ (เช่น potion ใน armory)
        picked: List[str] = []
        new_room = self.rooms[self.player_pos]
        if new_room["items"]:
            picked = list(new_room["items"])
            self.inventory.extend(picked)
            new_room["items"] = []  # เก็บแล้วห้องว่าง
        # เช็กชนะก่อน (เช่น เดินเข้าบอสห้องหลังบอสตาย)
        self._check_end()
        counter: List[Dict[str, Any]] = []
        # ถ้ายังไม่ชนะ โดนศัตรูในห้องสวนได้
        if not self.game_over:
            counter = self._enemy_counter()
            self._check_end()  # สวนแล้วอาจตายหรือหมดเวลา
        return {
            "ok": True,
            "position": self.player_pos,
            "picked": picked,
            "counter": counter,
            "player_hp": self.player_hp,
            "turn_count": self.turn_count,
            "game_over": self.game_over,
            "result": self.result,
            "message": f"เดิน {d} ไป {self.player_pos}",
        }

    def attack(self, target: str) -> Dict[str, Any]:
        """โจมตี goblin/orc (สำเร็จเสีย 1 เทิร์น)."""
        # เกมจบแล้วห้ามตีต่อ
        if self.game_over:
            return {"ok": False, "error": "เกมจบแล้ว โจมตีไม่ได้"}
        t = str(target).strip().lower()
        # ชื่อผิด = ไม่รู้จัก
        if t not in self.enemies:
            return {"ok": False, "error": f"ไม่รู้จักศัตรู {target} มีแค่ goblin, orc"}
        e = self.enemies[t]
        # ศพตีซ้ำไม่ได้
        if not e["alive"]:
            return {"ok": False, "error": f"{t} ตายแล้ว โจมตีซ้ำไม่ได้"}
        # อยู่คนละห้องตีไม่ได้
        if e["position"] != self.player_pos:
            return {"ok": False, "error": f"{t} อยู่ {e['position']} แต่คุณอยู่ {self.player_pos} ตีไม่ได้"}
        # ทอย d20 + 4 เทียบ AC เป้าหมาย
        roll = self.rng.randint(1, 20)
        total = roll + self.player_attack_bonus
        hit = total >= int(e["ac"])
        dmg = 0
        if hit:
            # โดน = ทอย d6 ลบเลือด
            dmg = self.rng.randint(1, 6)
            e["hp"] = max(0, int(e["hp"]) - dmg)
            if e["hp"] <= 0:
                e["alive"] = False  # เลือดหมด = ตาย
        self.turn_count += 1  # ตีสำเร็จเสีย 1 เทิร์น (โดนหรือไม่โดนก็นับ)
        # เช็กชนะ (ฆ่าบอสในห้องสุดท้าย) ก่อนโดนสวน
        self._check_end()
        counter: List[Dict[str, Any]] = []
        # ถ้ายังไม่จบเกม โดนตัวที่เหลือสวน
        if not self.game_over:
            counter = self._enemy_counter()
            self._check_end()
        return {
            "ok": True,
            "hit": hit,
            "attack_roll": roll,
            "total": total,
            "damage": dmg,
            "target_hp": e["hp"],
            "target_alive": e["alive"],
            "counter": counter,
            "player_hp": self.player_hp,
            "turn_count": self.turn_count,
            "game_over": self.game_over,
            "result": self.result,
        }

    def use_item(self, item: str) -> Dict[str, Any]:
        """ใช้ potion ฟื้น 8 HP (สำเร็จเสีย 1 เทิร์น)."""
        # เกมจบแล้วใช้ของไม่ได้
        if self.game_over:
            return {"ok": False, "error": "เกมจบแล้ว ใช้ของไม่ได้"}
        name = str(item).strip().lower()
        # ตอนนี้มีแค่ potion
        if name != "potion":
            return {"ok": False, "error": f"ไม่รู้จักของ {item} ตอนนี้มีแค่ potion"}
        # ไม่มีของในกระเป๋า
        if "potion" not in self.inventory:
            return {"ok": False, "error": "ไม่มี potion ในกระเป๋า"}
        # เลือดเต็มแล้วห้ามกดทิ้ง
        if self.player_hp >= self.player_max_hp:
            return {"ok": False, "error": "HP เต็มแล้ว ไม่ต้องใช้ potion"}
        # ฟื้น 8 แต่ไม่เกินเลือดเต็ม แล้วทิ้งขวด
        healed = min(POTION_HEAL, self.player_max_hp - self.player_hp)
        self.player_hp += healed
        self.inventory.remove("potion")
        self.turn_count += 1  # ใช้สำเร็จเสีย 1 เทิร์น
        # ใช้ยาก็โดนสวนได้ถ้ามีมอนในห้อง
        counter = self._enemy_counter()
        self._check_end()
        return {
            "ok": True,
            "healed": healed,
            "player_hp": self.player_hp,
            "inventory": list(self.inventory),
            "counter": counter,
            "turn_count": self.turn_count,
            "game_over": self.game_over,
            "result": self.result,
        }

    def roll_dice(self, sides: int) -> Dict[str, Any]:
        """ทอยเต๋าเล่น (ไม่เสียเทิร์น ใช้เทสต์ RNG)."""
        # รับเฉพาะด้านที่กำหนด (กันค่าประหลาด)
        if sides not in VALID_DICE:
            return {"ok": False, "error": f"sides ต้องเป็นหนึ่งใน {list(VALID_DICE)}"}
        # ทอย 1..sides จากตัวสุ่มของเกม
        value = self.rng.randint(1, int(sides))
        return {"ok": True, "sides": int(sides), "result": value}
