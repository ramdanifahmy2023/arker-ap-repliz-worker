# Kontrak kontrol dan telemetry

Status: draft API; endpoint berikut belum diimplementasikan.

| Kontrak | Respons / perilaku |
| --- | --- |
| GET health | Host/service/loop state, heartbeat age, stale reason, config version |
| GET summary & metrics | Snapshot ID, waktu sumber, unit, filter, coverage, missing reason |
| GET assets / deliveries | Pagination stabil, ID, state, stage, per-platform evidence |
| GET accounts | Identitas, readiness, capability, quota snapshot; tidak berisi credential |
| GET configuration | Nilai nonrahasia, configured flags, desired/applied version |
| POST configuration/validate | Validasi draft tanpa mengganti config aktif |
| POST connections/test | GET adapter terbatas, tanpa membuat posting/reply |
| POST commands | Perintah bertipe, idempotency key, base version, actor, scope |
| GET commands/{id} | Requested/accepted/running/applied/rejected/uncertain dan alasan |
| GET events | Cursor monoton, snapshot version, reconnect/resync untuk gap |

## Penerapan konfigurasi

API menyimpan draft dan perintah secara durable. Worker memeriksa ownership, revision dan batas operasi aman, kemudian menerapkan config version. Applied hanya boleh ditulis sesudah worker membaca dan memvalidasi versi tersebut. Restart-required tidak boleh dilaporkan applied sebelum restart dan health berhasil.

Konfigurasi rahasia dipisahkan dari payload umum dan tidak masuk log request body. Audit mencatat field yang berubah dan credential version, bukan nilai rahasia. Perubahan beberapa field terkait, seperti bank dan Drive, adalah satu transaksi konfigurasi.

## Progres dan chart

Event membawa entity ID, stage, attempt number, monotonic sequence, timestamp, total/completed jika tersedia, dan status kualitas. Client mengabaikan event duplikat/terlambat dan mengambil snapshot baru ketika ada gap. Refresh tidak memicu polling provider tambahan per browser; backend berbagi cache/limiter.

Persen valid hanya jika total > 0 dan sumber melaporkan completed yang konsisten. UI membatasi animasi ke nilai terkonfirmasi; tidak memperkirakan kenaikan memakai timer. Render percent dan published evidence adalah dimensi berbeda.

P50/p95 dihitung dari sampel selesai yang menyertakan stage dan durasi. Waktu antre berbeda dari waktu eksekusi. Grafik tidak dibangun dari log teks yang tidak mempunyai struktur waktu/entitas cukup. Data lama yang tidak memenuhi kontrak diberi missing reason.

## Kontrol aman

Pause video, pause reply dan pause report memiliki scope terpisah. Stop service dan restart adalah operasi berbeda. Jadwal yang telah diterima provider dapat terus berjalan walau worker dijeda. Reconcile melakukan pemeriksaan hasil, bukan resend. Retry hanya ditawarkan jika server mengembalikan available_actions yang sesuai bukti terbaru.
