# Menjalankan Arker

## Instalasi dan data privat

Ikuti instalasi source di [README](../README.md). Untuk membuat wheel, pasang prasyarat build dengan `python -m pip install -r requirements-dev.lock` setelah frontend dibangun, lalu jalankan `python scripts/package.py`. Pasang file `.whl` pada environment baru dengan `python -m pip install <file-wheel>`. Wheel memuat frontend yang sudah dibangun, API, worker, dan font.

| Sistem | Direktori data bawaan |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Arker` |
| macOS | `~/Library/Application Support/Arker` |
| Linux | `$XDG_DATA_HOME/arker` atau `~/.local/share/arker` |

Gunakan disk lokal untuk database dan jurnal. Folder bank dapat berbeda dari data directory. Jangan menaruh SQLite di folder sinkronisasi atau network share. `ARKER_DATA_DIR` atau `arker --data-dir <folder> ...` mengganti lokasi privat. Direktori berisi DB, Credential terenkripsi, jurnal, work, bank bawaan, log, dan backup. Git mengabaikan runtime; jangan memaksa memasukkannya.

## Login pertama

Jalankan `arker init` di terminal. Masukkan email admin dan password minimal 12 karakter. Terminal tidak menampilkan password ketika diketik; source tidak memiliki login bawaan. Bootstrap menolak menimpa admin yang sudah ada. Aplikasi belum menyediakan reset password berbasis email atau multi-user.

## Layanan dan panel

```sh
arker doctor
arker start
arker status
arker open
arker stop
```

`start` menjalankan supervisor, API, dan worker sebagai proses terpisah. Menutup tab tidak menghentikan worker. Halaman Kendali worker menggunakan supervisor untuk start/stop/restart worker sambil menjaga API tetap tersedia. Tindakan menunggu batas operasi yang aman; status permintaan diterima bukan bukti proses sudah berhenti.

Untuk debugging, `arker run` berjalan di foreground. `arker serve` dan `arker worker` tersedia terpisah; kontrol proses dari web memerlukan supervisor, bukan API standalone. Satu data directory hanya menerima satu API dan satu worker melalui file lock. Port default 8765; ubah lewat `arker start --port 18765`.

Server bawaan terikat loopback. Akses dari HP/host lain memerlukan deployment HTTPS dan origin yang disetujui melalui `create_app(..., allowed_origins=[...], secure_cookies=True)`. Reverse proxy/tunnel dan domain publik belum dipasang oleh repo ini. Jangan meneruskan server lokal ke internet tanpa konfigurasi tersebut.

Log lokal: `logs/api.log`, `logs/worker.log`, `logs/supervisor.log`. Detail kegagalan pengguna berada di Riwayat aktivitas. Transport tidak mencetak token atau body provider. Log tidak mempunyai rotasi otomatis pada rilis ini; pantau ukuran log.

## Autostart saat login

```sh
arker service install
arker service start
arker service status
arker service stop
arker service uninstall
```

Perintah menggunakan launchd user agent di macOS, systemd user unit di Linux, dan Task Scheduler ONLOGON di Windows. Windows menggunakan task pengguna, bukan Windows SCM service. Install tidak mengaktifkan publishing. Definisi layanan menunjuk interpreter environment saat pemasangan; pasang ulang definisi jika environment dipindah.

Tes CI memeriksa definisi dan lifecycle supervisor di ketiga OS. Pendaftaran service manager native perlu diperiksa pada host operator; pengujian repo tidak mengubah autostart komputer pengguna. Linux memerlukan sesi user/systemd; linger tidak diaktifkan otomatis.

## Mengisi konfigurasi

1. Tetap gunakan shadow selama setup. Isi bank lokal dan link folder Drive pada Penyimpanan.
2. Isi Repliz Access Key/Secret Key pada Koneksi layanan. Nilai input dibersihkan setelah disimpan. Browser hanya mendapat configured/version.
3. Google Drive memakai access token baca. Token yang kedaluwarsa perlu diganti; alur OAuth refresh token otomatis belum tersedia.
4. Atur satu aplikasi sinkronisasi eksternal. Arker tidak mengunggah media ke Drive. Provider memerlukan izin baca tautan; Arker hanya memeriksa dan tidak mengubah sharing.
5. AI bersifat opsional. Tanpa AI, metadata sumber dipakai sebagai fallback yang dibatasi; aplikasi tidak mengarang transkrip. Transkripsi lokal membutuhkan whisper.cpp, model lokal, dan opsi yang diaktifkan.
6. Persona mempunyai versi dan binding akun. Jadwal/kuota memakai Asia/Jakarta. Akun hanya dapat mengirim setelah identitas, koneksi, snapshot kuota, dan ownership memenuhi syarat.
7. Simpan, lihat versi menunggu, lalu periksa versi aktif. Worker menguji koneksi baru secara hanya-baca sebelum mengakui versi. Pekerjaan lama mempertahankan versi dan referensi bank asal.

Telegram nonaktif secara default. Ketika diaktifkan operator, intake hanya memproses chat privat agar rincian batch tidak bocor ke grup. Public ingest berarti orang lain dapat mengirim lewat chat privat sesuai batas backlog, bukan kendali admin terbuka. Notifikasi Telegram adalah pesan nyata; jangan mengaktifkannya dalam pengujian tanpa publikasi/pesan.

## Preview tanpa jaringan

```sh
arker preview --output .artifacts/preview-baru
```

Perintah membuat video dan audio buatan, enam frame, render H.264/AAC, serta evidence JSON. Pemeriksaan membandingkan hook sebelum/pada detik 3, orientasi kiri/kanan, zoom, frame rate, progress encoder, dan korelasi audio. Folder output harus baru. Tidak ada unduhan Instagram atau request provider.

## Backup dan pemulihan

```sh
arker backup
arker --data-dir <folder-baru> restore <folder-bundle>
```

Backup SQLite online dan jurnal memakai lock bersama pengiriman. Manifest menyimpan ukuran/hash dan setiap attempt harus mempunyai intent journal. Credential dan media tidak masuk backup ini; simpan bank/media serta kunci akses secara privat terpisah. Backup DB tetap sensitif karena memuat hash login, riwayat, dan konteks konten.

Restore hanya ke direktori baru, tidak menimpa runtime aktif. Ia mempertahankan konfigurasi historis, membuat konfigurasi shadow baru, mengosongkan sesi dan kepemilikan akun, menonaktifkan otomatisasi, serta menahan proses dan pengiriman. `restore_requires_reconciliation` mencegah pengiriman sebelum rekonsiliasi. Rilis ini menyediakan pemulihan untuk inspeksi; aktivasi kembali hasil restore memerlukan migrasi/review jurnal dan pemetaan ulang media secara terpisah. Tidak ada tombol bypass.

## Cleanup

`arker cleanup` dan tombol Periksa kandidat hanya menampilkan rencana. Penghapusan melalui perintah worker memerlukan cleanup aktif pada konfigurasi yang sudah diterapkan. Hanya file sumber/work yang terbukti aman dapat dihapus satu per satu.

Semua tiga tujuan wajib published terverifikasi, retensi minimum 24 jam sejak tujuan terakhir, bank dengan bukti Drive dan hash cocok, konteks dan enam frame arsip, tanpa lease aktif, symlink/hardlink, atau referensi aset lain. Bank, Drive, hasil render, frame, transkrip, konfigurasi, jurnal, dan histori tetap disimpan.

## Mode live

Mode live tidak diaktifkan pada pengujian implementasi. Sebelum live, operator harus menetapkan akun khusus atau menyelesaikan pemindahan ownership dari instalasi lain. Daftar pengecualian akun diisi privat. Satu instance ID hanya mengendalikan database ini; ia bukan distributed lock antarhost. Native automation provider tidak diubah otomatis. Pastikan provider/worker lain tidak mengirim atau membalas pada scope yang sama.
