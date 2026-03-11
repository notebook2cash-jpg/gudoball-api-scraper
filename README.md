# Gudoball Scraper API

โปรเจกต์นี้ดึงข้อมูลจาก [gudoball.club](https://www.gudoball.club/) และแปลงเป็น JSON เพื่อให้แอปเรียกใช้ผ่าน API

## ข้อมูลที่ดึง (4 ส่วน)

1. `section_1_analysis_today` - รายการบทวิเคราะห์บอลวันนี้
2. `section_2_tips_combo` - ทีเด็ดบอลเต็ง/บอลชุด
3. `section_3_opinion_today` - ตารางคะแนนทรรศนะบอลล่าสุด
4. `section_4_opinion_previous` - ตารางคะแนนทรรศนะบอลก่อนหน้า

## เริ่มใช้งานในเครื่อง

```bash
cd ~/Downloads/gudoball-api-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_scrape.py
uvicorn app.main:app --reload
```

## API Endpoints

- `GET /health`
- `GET /api/v1/gudoball/latest`
- `GET /api/v1/gudoball/sections/1`
- `GET /api/v1/gudoball/sections/2`
- `GET /api/v1/gudoball/sections/3`
- `GET /api/v1/gudoball/sections/4`
- `POST /api/v1/gudoball/refresh?token=...`

> ถ้าตั้ง `REFRESH_TOKEN` เป็น environment variable ระบบจะตรวจ token ตอนเรียก refresh

## GitHub Actions Schedule

ไฟล์ workflow: `.github/workflows/scrape.yml`

- รันเวลา `11:45` และ `16:15` ตามเวลาไทย
- cron ใน GitHub ใช้ UTC จึงตั้งเป็น:
  - `45 4 * * *`
  - `15 9 * * *`

workflow จะ scrape แล้วอัปเดต `data/latest.json` อัตโนมัติ
