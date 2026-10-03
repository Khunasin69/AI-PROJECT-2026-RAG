"""เล่นเกมผ่าน terminal (วนรับคำสั่งทีละเทิร์น)."""
# วิธีเล่น: python -m src.cli --model stub --seed 42
# พิมพ์ quit เพื่อออก

import argparse  # รับ flag --model/--seed (ของ stdlib ไม่ต้องลงเพิ่ม)

import src.mcp_server as srv  # ใช้อ่านสถานะมาพิมพ์ท้ายเทิร์น (ไม่เสียเทิร์น)
from src.agent import Agent  # DM loop
from src.llm import RealModel, StubModel  # โมเดล 2 แบบ (interface เดียวกัน)


def _parse_args() -> argparse.Namespace:
    """อ่าน flag จาก command line."""
    p = argparse.ArgumentParser(description="D&D AI DM (terminal)")
    p.add_argument("--model", default="stub", choices=["stub", "real"], help="stub=ออฟไลน์ real=ใช้ API")
    p.add_argument("--seed", default=None, type=int, help="ล็อกสุ่มเกม (ไม่ใส่=สุ่ม)")
    return p.parse_args()


def main() -> None:
    """วนรับคำสั่งจนจบเกมหรือพิมพ์ quit."""
    args = _parse_args()
    # เลือกโมเดลตาม flag (real ต้องมีคีย์ใน .env ไม่งั้น error ตั้งแต่ตรงนี้)
    model = RealModel() if args.model == "real" else StubModel()
    agent = Agent(model=model, seed=args.seed)
    print("=== D&D AI DM === (พิมพ์ quit เพื่อออก)")
    # วนทีละเทิร์น
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):  # pipe หมด / กด Ctrl+C = ออกดีๆ
            print()
            break
        # ออกเกม (3 คำ)
        if text.lower() in ("quit", "exit", "ออก"):
            break
        # บรรทัดว่าง = ข้าม (ไม่เสียเทิร์น)
        if not text:
            continue
        out = agent.turn(text)  # เล่น 1 เทิร์นผ่าน DM loop
        print(out["reply"])  # คำเล่าของ DM
        st = srv.get_state()  # อ่านสถานะจริงมาพิมพ์ท้ายเทิร์น
        p = st["player"]
        print(f"[HP {p['hp']}/{p['max_hp']} | ห้อง {p['position']} | เทิร์น {st['turn_count']}]")
        # จบเกม = ประกาศผลแล้วออก
        if out["game_over"]:
            print(f"*** จบเกม: {out['result']} ***")
            break


if __name__ == "__main__":
    main()
