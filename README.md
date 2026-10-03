# D&D AI DM (MVP) — Final Project วิชา AI

เกม D&D ขนาดเล็กที่ AI รับบท Dungeon Master
สถาปัตยกรรม: MCP server (เจ้าของ state + tools) + agent loop (LLM เล่าเรื่องแล้วเรียก tools)

สเปกหลักดูที่ `GAME_SPEC.md` (แหล่งความจริงเดียว)

## ติดตั้ง (ทำในโฟลเดอร์นี้เท่านั้น)

```powershell
python --version
# ต้อง 3.10+ (ตรวจแล้ว 3.14.3 ผ่าน)
copy .env.example .env
# ถ้ามีคีย์จริงค่อยใส่ใน .env ถ้าไม่มีก็เล่นด้วย stub ออฟไลน์ได้
pip install -r requirements.txt
```

## รัน / เทสต์ (จะใช้ได้ครบหลังทำถึงขั้นนั้น)

```powershell
# ขั้น 2: unit test (ยังไม่มีในขั้น 1)
pytest -q
# ขั้น 3: เริ่ม MCP server (ยังไม่มีในขั้น 1)
python -m src.mcp_server
# ขั้น 4: เล่นผ่าน terminal ด้วย stub (ยังไม่มีในขั้น 1)
python -m src.cli --stub
# ขั้น 5: รัน eval (ยังไม่มีในขั้น 1)
python eval/run_eval.py
```

## โครงโฟลเดอร์ (ขั้น 1)

```text
GAME_SPEC.md, data/dungeon.json = ความจริงของเกม
src/  = โค้ด (จะเขียนขั้น 2-4)
tests/ = เทสต์ (จะเขียนขั้น 2)
eval/  = เกณฑ์วัด (จะเขียนขั้น 5)
```
