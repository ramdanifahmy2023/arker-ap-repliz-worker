# Roadmap dan kriteria penerimaan

Rancangan tahap awal 19 Oktober 2026. P0 sampai implementasi web/pipeline dan pengujian terisolasi tersedia. Lihat [penerimaan](../ACCEPTANCE.md) untuk bukti per area. P6 aktivasi nyata ditunda atas instruksi pengguna; pembungkus desktop opsional tersedia, installer/signing belum dibuktikan.

| Tahap | Hasil | Bukti selesai |
| --- | --- | --- |
| P0 Fondasi | Repo terpisah, plan, navigasi, visual, konfigurasi contoh, CI dokumen | Pemeriksaan lokal, review visual, repo publik dan CI pada SHA yang sama |
| P1 Desain & kontrak | Layar Ringkasan/Detail/Koneksi/Storage, schema data/config | Preview desktop/HP, normal/reduced motion, kontrak error/offline |
| P2 Panel baca | Login dasar, snapshot API, chart, timeline, pagination | Fixture kosong/parsial/unknown/stale; angka chart cocok data sumber |
| P3 Konfigurasi & kontrol | Secret store, folder bank/Drive, apply/ack, worker commands | Rahasia tidak bocor, konflik versi, restart, crash dan offline tertangani |
| P4 Pipeline | Adapter download/AI/render/Drive/Repliz; scheduler, jurnal, reply | Suite offline, dedup, ownership, kuota, checksum, preview nyata tanpa posting |
| P5 Lintas OS | Service adapters dan storage Linux | Tes Windows/macOS/Linux, media preview per platform, lifecycle/recovery |
| P6 Aktivasi | Scope akun dan storage baru atau cutover terencana | Backup, ownership tunggal, pilot berizin, bukti published/reply sesuai scope |
| P7 Desktop | Pembungkus aplikasi jika dibutuhkan | Instalasi/update/signing dan kontrol worker tidak bergantung jendela UI |

## Prioritas UX awal

Ringkasan, Peta alur, Konten/Detail, Kendali worker, Repliz, serta Bank/Drive mendapat preview lebih dahulu. Ke-22 menu tetap ada dalam rencana; rilis tidak berisi tombol palsu untuk menu yang belum dibuat.

## Penerimaan chart dan animasi

- Aset dan delivery tidak tercampur satuan. Filter dan timestamp konsisten.
- Unknown, scheduled, failed dan published terverifikasi dibedakan.
- Data hilang bukan nol; tidak ada persen atau ETA yang dibuat timer.
- Reduced motion, keyboard, fokus, tooltip sentuh, zoom 200% dan narrow layout lulus.
- Animasi tidak menghalangi kontrol dan tidak tetap menunjukkan aktivitas saat telemetry stale.

## Penerimaan konfigurasi

- Credential tidak terlihat dalam bundle frontend, Git, log, export, response GET atau backup umum.
- Tes koneksi tidak membuat publikasi/reply dan tidak mengganti pool parsial.
- Form membedakan saved/applied serta config baru/job lama.
- Bank dan folder Drive diterapkan sebagai pasangan; referensi lama dipertahankan.
- Path salah, volume lepas, URL arbitrer, checksum beda, double-submit dan crash tidak menghasilkan pengiriman ganda.

## Penerimaan produksi

Repo dan bot baru tidak memberikan ownership otomatis. Aktivasi memerlukan scope eksklusif atau migrasi yang merekonsiliasi seluruh intent, jadwal, reply dan kuota. Hasil accepted berbeda dari published. Cleanup memerlukan seluruh tujuan wajib + retensi dan bukti file. Backup harus dapat dipulihkan dalam keadaan tidak aktif sebelum layanan boleh dinyatakan siap.
