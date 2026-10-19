# Worklog Arker

## 19 Oktober 2026 — rancangan lengkap dan repo terpisah

Permintaan: melengkapi menu; visual modern dengan chart/progress beranimasi; konfigurasi Repliz, folder bank dan link Google Drive; simpan seluruh proyek terpisah dan buat repo publik arker-ap-repliz-worker dengan dokumentasi/visual profesional serta target Windows/macOS/Linux.

Base: folder tujuan kosong, belum ada repo atau commit awal. Pekerjaan fondasi dibuat di root proyek baru; tidak ada worktree implementasi karena belum mengimplementasikan aplikasi. Branch awal main. Worker lama dan repositorinya tidak diubah; tidak menyalin code privat, runtime, DB, Credential atau media produksi.

Perubahan: README, rencana produk/menu/UX/config/roadmap, arsitektur/kontrak kontrol/lintas OS, visual SVG berlabel simulasi, contoh konfigurasi aman, spesifikasi JSON, validator Python, tes validator, dan CI lintas OS. Semua isi publik menggunakan istilah generik dan fixture buatan. Tidak menyimpan email/password admin, ID akun privat atau path komputer pengguna.

Alasan: memisahkan aplikasi baru dari operasi produksi dan membuat requirement yang dapat diuji. Google Drive Desktop tidak tersedia di Linux; adapter sinkronisasi Linux dinyatakan belum dipilih/diuji, bukan diklaim sudah didukung. UI UX Pro Max dan antislop dipakai untuk kontrak visual, progres berbasis bukti dan aksesibilitas.

Pemeriksaan lokal: validator PASS tanpa temuan, enam tes validator PASS, dan regenerasi tiga SVG identik. Tes mencakup file Credential yang dipaksa masuk Git, pola rahasia, path privat, link relatif/spasi dan path di luar repo. Ketiga SVG telah dirender penuh dan ditinjau; percobaan thumbnail Quick Look terpotong sehingga bukan bukti final. Render penuh memakai resvg pada artefak lokal yang diabaikan Git. Pasangan teks utama/sekunder pada panel memiliki rasio kontras 14,44:1 dan 8,17:1; pemeriksaan ini belum membuktikan aksesibilitas aplikasi interaktif.

Publikasi: [repo publik](https://github.com/ramdanifahmy2023/arker-ap-repliz-worker) telah dibuat, deskripsi dan topik diisi, dan 30 file fondasi dipush ke main. Commit awal 0c1f92c lulus [CI 39192587614](https://github.com/ramdanifahmy2023/arker-ap-repliz-worker/actions/runs/39192587614): validator, enam tes dan regenerasi SVG berhasil pada Windows/macOS/Linux. Push SSH awal memakai deploy key yang tidak berhak atas repo baru; remote diubah ke HTTPS dan credential helper akun GitHub pemilik yang sudah login, tanpa menyalin token. Push berikutnya berhasil. Tidak ada force-push atau merge dari repo lama.

Catatan penutupan ini mengikuti commit/push tersendiri; SHA, run CI dan hasil remote terakhir disimpan lokal pada .artifacts/publication.json agar tidak membuat commit hanya untuk merekam hash sendiri. Repo hanya menerbitkan fondasi rencana; tidak menjalankan worker, mengirim pesan, membuat jadwal/post/reply, mengganti kredensial, memindah bank, atau mengaktifkan uploader.

Batas bukti: diagram adalah konsep dengan data simulasi; bukan aplikasi berjalan. CI dokumen/validator bukan bukti runtime tiga OS. Isi peta eksternal belum dibaca karena akses 403. Metode login, domain remote, framework final, lisensi dan adapter Linux masih keputusan lanjutan.

Pembersihan: folder proyek baru adalah hasil yang diminta dan dipertahankan. Artefak pemeriksaan lokal masuk .artifacts yang diabaikan Git. Tidak ada file produksi atau worktree lama yang dihapus.
