# Aplikasi web

`web/` memuat React, TypeScript, konfigurasi build, dan tes frontend. Backend API serta worker berada pada package Python `src/arker/`; keduanya dijalankan sebagai proses terpisah melalui CLI.

Frontend produksi dibangun dengan `npm run build --prefix apps/web`, lalu dilayani API pada origin yang sama. Wheel membundel hasil build melalui `scripts/package.py`.
