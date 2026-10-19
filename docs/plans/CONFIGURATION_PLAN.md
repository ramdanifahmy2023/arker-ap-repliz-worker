# Rencana konfigurasi melalui panel

Status: spesifikasi, belum ada form/API aktif. Contoh konfigurasi publik tidak berisi nilai akses.

## Satu alur penerapan

Draft → validasi → tes yang diperlukan → ringkasan dampak → apply → konfirmasi worker.

Setiap perubahan membawa base_version. Jika dua tab mengubah versi yang sama, penulisan kedua harus menyelesaikan konflik, bukan menimpa diam-diam. Double-click memakai command ID/idempotency key yang sama. Restart/crash tidak boleh menyebabkan apply ganda.

Panel menunjukkan desired_version, applied_version, waktu, actor, lingkup perubahan, dan alasan kegagalan. Status tersimpan tidak ditampilkan sebagai aktif. Gagal tes tidak mengganti konfigurasi aktif. Rollback konfigurasi tidak membatalkan posting yang sudah diterima provider.

## Repliz

Lokasi: Koneksi layanan → Repliz.

| Kolom / kontrol | Perilaku yang direncanakan |
| --- | --- |
| Access Key | Input rahasia baru; tidak diisi ulang dari server |
| Secret Key | Input rahasia baru; tidak dikirim kembali melalui GET |
| Status konfigurasi | Belum diisi / tersimpan / validasi gagal / menunggu apply / aktif |
| Tes koneksi | GET terbatas melalui adapter dan rate limiter; tidak membuat jadwal atau reply |
| Ringkasan hasil tes | Identitas koneksi nonrahasia, akun terbaca, waktu tes, kelengkapan snapshot |
| Terapkan | Menunggu batas operasi aman, memuat credential version, membentuk snapshot baru lengkap |

Backend menyimpan rahasia di direktori Credential lokal yang dikecualikan Git; paket terpasang memakai direktori data privat per OS. UI hanya memperoleh configured=true/false dan credential_version. Kolom kosong berarti tetap memakai nilai lama; penghapusan merupakan tindakan terpisah yang menjelaskan dampak.

Tidak memasukkan rahasia ke localStorage, URL, analytics, error, log, diff konfigurasi, ekspor, atau backup umum. Isi input baru boleh dilihat sementara oleh pengisi; nilai tersimpan tidak memiliki endpoint reveal. Akses filesystem dibatasi kepada akun layanan, memakai permission/ACL sesuai OS. Penulisan dilakukan secara atomik dan tahan crash.

Endpoint provider dibatasi daftar tujuan yang didukung; form tidak menjadi proxy ke alamat pengguna. Saat kredensial diganti, operasi dengan intent aktif diselesaikan/direkonsiliasi sesuai credential version-nya; kredensial lama tidak dibuang sebelum batas aman. Semua secret version tetap berada pada penyimpanan privat. Jika akses lama dicabut, status ambigu tetap ditahan. Snapshot gagal atau parsial tidak mengosongkan pool atau mereset kuota.

## Folder bank konten

Lokasi: Penyimpanan & cleanup → Bank konten.

- Tampilkan lokasi pada mesin worker, volume, status terpasang, kemampuan baca/tulis, ruang bebas, dan pasangan folder Drive.
- Pilihan folder melalui agen lokal/API terbatas ke akar yang diizinkan admin. Browser HP tidak dapat memakai file picker lokalnya untuk memilih folder Mac/Windows/Linux worker.
- Normalisasi path berdasarkan OS; periksa traversal, symlink/reparse point, izin, volume lepas, folder di dalam runtime sementara, serta tabrakan dengan bank instalasi lain.
- Perubahan path adalah konfigurasi baru, bukan perintah memindahkan atau menghapus isi lama.
- Job menyimpan storage_config_version dan referensi file; aset lama tetap dapat dibaca/verifikasi/cleanup sesuai root lamanya.
- Root lama tetap dilindungi selama masih mempunyai referensi, termasuk preview dan arsip. Migrasi eksplisit memerlukan rencana, checksum, dan kemampuan pemulihan.
- Penulisan penanda untuk tes izin, jika diperlukan, harus dijelaskan sebagai tes folder; hanya penanda milik tes yang boleh dihapus. Tidak ada penghapusan rekursif.

## Link Google Drive

Lokasi utama: Penyimpanan & cleanup → Google Drive; Koneksi layanan memberi tautan ke form yang sama.

| Kolom / kontrol | Makna |
| --- | --- |
| Link folder | URL HTTPS folder Drive yang didukung; ID diurai backend |
| Folder ID | Hasil pembacaan, bukan ID tebakan berdasarkan nama |
| Folder bank pasangan | Storage profile yang sinkron dengan folder tersebut |
| Adapter sinkronisasi | External sync atau adapter Linux yang kelak diuji; satu penulis sinkronisasi |
| Periksa folder | Buktikan folder dapat dibaca; tidak mengubah sharing diam-diam |
| Periksa pasangan file | Cocokkan ID, ukuran, dan seluruh checksum file lokal/Drive |
| Status | Belum diuji / menunggu sinkron / cocok / tidak cocok / akses ditolak |

Backend hanya menerima host/path Google yang didukung, memvalidasi redirect, dan menolak localhost/private-IP maupun URL arbitrer. Link folder publik bukan bukti semua video telah terunggah. File bernama sama tidak otomatis sama isinya. Duplikat nama, checksum berbeda, link login/HTML, dan ID usang menahan publikasi.

Windows/macOS dapat memakai Drive Desktop. Linux membutuhkan adapter eksternal atau adapter sinkronisasi yang dibangun dan diuji tersendiri. Arker tidak menambahkan uploader kedua ke folder yang sudah dikelola penulis lain. Penggantian folder Drive dipasangkan atomik dengan profil bank; konfigurasi lama tetap tersimpan untuk pekerjaan lama.

## Login dan kendali

Metode login belum ditetapkan. Rancangan mendukung admin email dengan password yang di-hash oleh backend, atau penyedia login terverifikasi. Tidak ada akun/default password di repo. Akun bootstrap ditetapkan saat pemasangan privat.

Autentikasi dan otorisasi berlaku pada halaman, API, aliran event, serta unduhan preview. Sesi memakai cookie aman pada deployment HTTPS, pemeriksaan asal/CSRF untuk mutasi, batas percobaan login, dan kedaluwarsa. Kredensial provider tidak menjadi password login aplikasi. Service kontrol tetap dapat dihubungi ketika worker berhenti, selama host/API hidup.

## Dampak perubahan

| Perubahan | Berlaku untuk | Perlu perhatian |
| --- | --- | --- |
| Tema / gerak minimal | Sesi pengguna | Tidak memengaruhi worker |
| Jeda video / reply / laporan | Modul terkait setelah perintah diterima | Jeda tidak membatalkan jadwal remote |
| Persona / hook | Draft atau render baru yang belum dikunci | Hasil lama tidak dirender ulang otomatis |
| Batas/jam posting | Reservasi/jadwal berikutnya | Tidak memindah remote schedule tanpa dukungan dan bukti |
| Kredensial Repliz | Klien pada versi baru setelah batas aman | Snapshot lengkap, intent aktif, dan rekonsiliasi |
| Bank / link Drive | Job baru setelah pasangan terverifikasi | Referensi lama dipertahankan; tidak memindah file |
| Tool media / adapter OS | Proses baru setelah validasi | Restart jika klien/layanan memerlukannya |

## Kriteria uji

Kunci salah, timeout/429, snapshot parsial, double-click, dua tab, crash saat menulis, apply tanpa worker, volume lepas, path Unicode/spasi, symlink/reparse point, link Drive salah, ID cache usang, checksum berbeda, file duplikat, akses nonadmin, kebocoran rahasia, serta restart dengan intent belum pasti harus mempunyai hasil deterministik tanpa pengiriman ganda.
