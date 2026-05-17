---
title: BTN Net
emoji: 📡
colorFrom: red
colorTo: gray
sdk: docker
pinned: false
app_port: 7860
---

# BTN Net — Voucher Wi-Fi & Langganan

Aplikasi Flask untuk pembelian voucher hotspot dan monitoring transaksi. Zona waktu tampilan & logika bisnis: **WIB (Asia/Jakarta)**.

## Deploy ke Hugging Face Spaces

### 1. Buat Space

1. [huggingface.co/new-space](https://huggingface.co/new-space)
2. **SDK**: pilih **Docker**
3. Hubungkan repo GitHub proyek ini (atau upload manual)

### 2. Secrets (Settings → Variables and secrets)

| Variabel | Wajib | Contoh |
|----------|-------|--------|
| `DATABASE_URI` | Ya | `mysql+pymysql://user:pass@host:3306/db?ssl_ca=...` |
| `SECRET_KEY` | Ya | string acak panjang |
| `APP_BASE_URL` | Ya | `https://USERNAME-SPACENAME.hf.space` |
| `PRODUCTION` | Ya | `true` (produksi) / `false` (presentasi) |
| `DEMO_RESET_ON_START` | Tidak | `false` di produksi |

**Penting:** `APP_BASE_URL` harus URL Space Anda (tanpa slash di akhir), agar Stripe/n8n redirect & webhook benar.

### 3. Database

Gunakan **MySQL cloud** (Aiven, PlanetScale, dll.). HF Spaces tidak menyediakan MySQL persisten bawaan — jangan andalkan SQLite di container (data hilang saat rebuild).

### 4. n8n + Stripe setelah deploy

Di workflow **create_checkout**, pakai dari payload Flask:

- `success_url` → `https://ANDA.hf.space/payment/complete/{transaction_id}`
- `cancel_url` → URL cancel dari payload

Opsional: POST ke `https://ANDA.hf.space/api/payment-success` dengan body `{"transaction_id": 123}`.

### 5. Build

Space akan mem-build `Dockerfile` otomatis. Port default HF: **7860** (sudah diset di Dockerfile).

## Jalankan lokal

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env
python run.py
```

Buka `http://127.0.0.1:5000`.

## Mode presentasi

```env
PRODUCTION=false
DEMO_RESET_ON_START=true
APP_BASE_URL=http://127.0.0.1:5000
```

## Struktur singkat

- `run.py` — entrypoint Gunicorn / dev server
- `app/` — Flask app, models, routes
- `app/timezone_util.py` — WIB helpers
- `Dockerfile` — image untuk HF Spaces
