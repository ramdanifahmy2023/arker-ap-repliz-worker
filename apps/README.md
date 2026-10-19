# Batas aplikasi yang direncanakan

Folder ini mencatat struktur implementasi berikutnya; belum ada aplikasi yang dapat dijalankan.

- `web`: antarmuka TypeScript, visualisasi, formulir dan aksesibilitas.
- `api`: autentikasi, query, secret/config management dan durable commands.
- `worker`: pipeline, scheduler, adapter, jurnal, telemetry dan recovery.

Subfolder dan package manifest dibuat bersama implementasi nyata. Lihat [arsitektur](../docs/architecture/OVERVIEW.md). Jangan menjalankan worker kedua terhadap scope produksi yang sudah dimiliki instalasi lain.
