# IMEI Tracker Simulator Bot

> **Educational privacy-awareness demo.**  
> This bot pretends to track phones by IMEI – but it **never** uses real location data.

⚠️ **Every user-facing message in the bot ends with:**  
`⚠️ Simulation only. Real IMEI tracking is illegal without a court order.`

---

## Features

- 🛰️ **IMEI simulation**  
  - Luhn-validated 15-digit IMEIs  
  - Deterministic fake tracks per IMEI + per day  
  - Daily “location refresh” at 00:00 UTC  

- 🗺️ **Pretty output**
  - Static PNG map via [Geoapify](https://www.geoapify.com/) Static Maps API  
  - 5-point polyline route with timestamps & fake addresses  
  - “Last seen” in human-readable form (e.g., “3 hours ago”)  

- 🧠 **Fake Tracking Engine**
  - `HMAC-SHA256(IMEI + daily_seed, SECRET_KEY)`  
  - Generates realistic lat/lon within ±0.3° variance  
  - Optionally snaps coordinates to nearest road using OSRM demo server  
  - Cached per IMEI in Redis for 1 hour  

- 🚦 **Rate limiting**
  - 3 IMEI checks per user per day (PostgreSQL + Redis leaky-bucket)  
  - Friendly message when limit is hit with time until reset  

- 🛡️ **Privacy & safety**
  - Never logs full IMEI (stores first 8 chars + `********`)  
  - Clear disclaimer on **every** message  
  - Educational framing, not a surveillance tool  

- 🛠️ **Admin tools**
  - `/adminstats` – total users, total queries, top IMEIs, abuse count  
  - `/broadcast` – send Markdown to all users  
  - Abuse reports forwarded to admins  

- 🌍 **I18n**
  - English (`en`), Spanish (`es`), Russian (`ru`), Hindi (`hi`)  
  - `/lang` command plus fallback to `user.language_code`  

- 🧪 **Tests & CI**
  - `pytest-asyncio`, `fakeredis`, lightweight handler tests  
  - GitHub Actions: `ruff` → `pytest` → Docker build → push to GHCR  

- 📦 **Dev & deploy**
  - Python 3.11  
  - `python-telegram-bot` v20 (async)  
  - PostgreSQL 15 (`asyncpg`)  
  - Redis 7  
  - Docker + docker-compose  
  - Optional “Deploy to Fly.io”  

---

## Quick start

### 1. Clone & configure

```bash
git clone <this-repo-url> imei-simulator-bot
cd imei-simulator-bot/bot
cp .env.example .env
