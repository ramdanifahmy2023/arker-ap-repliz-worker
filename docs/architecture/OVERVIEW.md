# Arsitektur yang direncanakan

Status: rancangan, bukan layanan yang sudah tersedia.

## Komponen

| Komponen | Tanggung jawab |
| --- | --- |
| Web | Login, 22 menu, chart, tabel, preview, draft konfigurasi |
| Control API | Autentikasi, otorisasi, query, validasi, config version, durable command |
| Event/read model | Snapshot konsisten, event cursor, kualitas data, agregasi chart |
| Worker | Lease, antrean, preflight, execution, jurnal intent, rekonsiliasi |
| Adapter | Repliz, downloader, AI, FFmpeg, Drive, Telegram, service manager OS |
| Storage privat | DB, jurnal, Credential, bank, cache, backup; terpisah dari source repo |

Web tidak menulis DB atau TOML langsung. API tidak menjalankan shell string dari input dan tidak menjadi pengirim posting kedua. Worker tetap pemilik eksekusi. Mutasi memakai perintah bernama dengan schema dan batas yang jelas.

## Deployment awal

API dan worker sebagai proses terpisah pada satu host, dengan data privat sendiri. Web dapat dilayani API atau static server. Host adalah Windows, macOS, atau Linux sesuai adapter yang lulus pengujian.

Koneksi jarak jauh opsional menggunakan HTTPS dan pintu autentikasi. Jika web/API juga berada pada host worker, host mati berarti panel tidak dapat dibuka. Jika worker saja berhenti, API masih dapat menampilkan status dan menerima kontrol service yang diizinkan. Panel cloud yang tetap tersedia saat host mati merupakan tahap lanjutan dengan command queue dan sinkronisasi state tersendiri.

## Entitas

Batch → source asset → artifacts/context → tiga delivery → schedule/post evidence.

Entitas pendukung: account identity, capability/quota snapshots, reservations, immutable persona/config versions, operation attempts, durable journals, comments/replies, notification outbox, health samples, command records, audit events, storage profiles dan backup manifests.

Identitas remote, idempotency, kuota, dan bukti intent harus bertahan setelah restart. Status unknown tidak boleh dipaksa queued hanya untuk mengaktifkan tombol ulang.

## Pemisahan source dan data

Checkout Git hanya memuat kode, dokumen dan contoh nonrahasia. Data directory dipilih saat bootstrap dengan default per OS. Secret store menggunakan Credential di dalam direktori privat; hanya referensi credential yang masuk konfigurasi umum. Bank diatur terpisah dan tidak boleh mengarah otomatis ke bank instalasi produksi lain.

Tidak ada dependency absolut ke komputer pengembang, script bash-only untuk lifecycle inti, SQLite pada network share, atau shell command gabungan dari teks pengguna.

## Ownership

Instalasi diberi instance ID dan scope akun. Mode awal shadow. Live memerlukan bukti bahwa tidak ada instalasi lain yang mengirim/reply untuk scope yang sama; bisa melalui akun khusus atau cutover yang mencatat pemindahan ownership. Membuat repo baru tidak memberikan hak kirim baru. Mekanisme koordinasi antarinstalasi menjadi syarat desain sebelum live.
