# Peta 22 menu

Semua menu di bawah masih direncanakan. Sidebar dibagi enam kelompok yang dapat dilipat; favorit dan pencarian membantu akses harian. Detail konten juga dapat dibuka lewat tautan langsung dari menu lain.

| No. | Kelompok / menu | Informasi | Kontrol yang direncanakan |
| --- | --- | --- | --- |
| 1 | Pemantauan / Ringkasan | Heartbeat, antrean, tren, hambatan | Filter waktu/akun/platform, buka rincian chart |
| 2 | Pemantauan / Peta alur | Tahap, jumlah menunggu, durasi, aktivitas | Klik tahap untuk pekerjaan dan konfigurasi terkait |
| 3 | Pemantauan / Kendali worker | Service, loop, konfigurasi aktif | Jeda/lanjut per modul; restart terencana |
| 4 | Pemantauan / Perlu perhatian | Failed, held, unknown, data stale | Periksa hasil; retry hanya jika aman |
| 5 | Konten / Tambah konten | Link, duplikat, batas penerimaan | Validasi dan kirim batch |
| 6 | Konten / Batch & antrean | Pengirim, sumber, tahap, usia antrean | Pencarian, filter, buka sumber/delivery |
| 7 | Konten / Bank konten | Thumbnail, asal, berkas, checksum | Buka detail; tautan ke konfigurasi bank |
| 8 | Konten / Detail & preview | Video, hook, transkrip, metadata, tiga delivery | Preview terisolasi; riwayat versi |
| 9 | Akun & publikasi / Akun sosial | Identitas, koneksi, capability | Sinkronisasi dan panduan koneksi akun |
| 10 | Akun & publikasi / Rotasi & kuota | Eligible, reservasi, pemakaian, sisa | Batas sah dan kebijakan rotasi untuk pekerjaan berikutnya |
| 11 | Akun & publikasi / Kalender posting | Jadwal lokal/remote, WIB, hasil | Jendela jadwal; pemindahan remote perlu capability tersendiri |
| 12 | Akun & publikasi / Hasil publikasi | Post ID, tautan, waktu verifikasi | Filter dan pemeriksaan hasil |
| 13 | Video, AI & interaksi / Pengolahan video & AI | Profil render, transkrip, model, token | Uji preview dan konfigurasi untuk konten baru |
| 14 | Video, AI & interaksi / Persona & caption | Persona per akun, kredit sumber, versi | Draft perubahan, preview, penerapan versi |
| 15 | Video, AI & interaksi / Komentar & balasan | Thread, konteks, draft, sent/unknown | Jeda/lanjut reply, kuota, review aman |
| 16 | Video, AI & interaksi / Laporan & statistik | Snapshot akun, pertumbuhan, kualitas data | Filter, jadwal yang didukung, pengaktifan kolektor |
| 17 | Koneksi & penyimpanan / Koneksi layanan | Repliz, AI, downloader, Drive | Ganti kredensial, tes koneksi, lihat versi aktif |
| 18 | Koneksi & penyimpanan / Telegram & notifikasi | Input, outbox, status transport | Konfigurasi bot dan preferensi notifikasi sesuai hak akses |
| 19 | Koneksi & penyimpanan / Penyimpanan & cleanup | Bank, link Drive, ruang, verifikasi | Pilih folder, tes kecocokan, rencana cleanup |
| 20 | Administrasi / Backup & pemulihan | Bundle, checksum, gap bukti | Backup dan restore terpandu tanpa aktivasi otomatis |
| 21 | Administrasi / Riwayat aktivitas | Event, error, perubahan, actor | Filter, detail tersanitasi, ekspor nonrahasia |
| 22 | Administrasi / Pengaturan & akses | Sesi, admin, config draft/aktif | Autentikasi, sesi, versioning, preferensi tampilan |

## Perjalanan pengguna

- Chart “Render menunggu” → antrean terfilter → detail video → alasan dan konfigurasi terkait.
- Akun “Belum siap” → bukti koneksi/capability/kuota → tes baca → snapshot lengkap; tidak ada tombol yang mengabaikan guard.
- Penyimpanan “Drive belum cocok” → pasangan folder → ukuran/checksum → penjelasan file yang belum selesai sinkron.
- Config “Tersimpan” → dampak perubahan → perintah apply → worker mengonfirmasi versi → status “Aktif”.

Di HP, grafik dan detail disusun vertikal. Tabel besar mempunyai ringkasan kartu dan halaman detail, bukan memaksa seluruh kolom diperkecil.
