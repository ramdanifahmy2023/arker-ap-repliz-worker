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

## 19 Oktober 2026: implementasi aplikasi dan pengujian tanpa publikasi

Permintaan: implementasikan seluruh panel dan worker pada proyek terpisah, uji hingga lulus, lalu gabungkan dan push ke main. Klarifikasi pengguna menetapkan pengujian tanpa publikasi terlebih dahulu. Tidak menggunakan credential, DB, media, service, atau source privat instalasi lain.

Base: `6805a26d354bfe84bdd399859d52c206e044efbc` pada origin/main. Branch `work/20261019-full-implementation`, worktree privat `.worktrees/20261019-full-implementation`. Backend, frontend, dan worker dikerjakan paralel oleh subagent dengan pembagian file; integrasi, lifecycle, backup/cleanup, packaging, CI, dan review dilakukan pada worktree yang sama.

Perubahan: package `src/arker`, React/TypeScript di `apps/web`, CLI, sesi admin/CSRF, credential terenkripsi, konfigurasi immutable dan apply/ack, intake/dedup, journal/recovery, scheduler/kuota, adapter Repliz/Drive/AI/Telegram/media, persona, laporan, supervisor, service definitions, backup/restore, serta cleanup berbasis bukti. Font Barlow berasal dari Google Fonts publik dan dibundel bersama OFL. README berisi screenshot aplikasi dengan label fixture, diagram alur, menu, dan panduan operasi. Dependency/runtime lock, harness browser, wheel builder, dan CI tiga OS ditambahkan.

Perbaikan hasil review: snapshot parsial mempertahankan pool, credential gagal tidak mengganti versi aktif, request ambigu tidak diulang, restore ditahan, API tetap hidup ketika worker stop, status config mengikuti acknowledgment, chart memisahkan aset/delivery, input URL/path/executable diperketat, credential menolak symlink/junction, body API dibatasi saat dibaca, frame rate diterapkan sebelum hook, dan progress memakai waktu encoder sebenarnya.

Pemeriksaan lokal: validator publikasi nol temuan; 88 tes Python API/core/worker/adapter/operations/lifecycle; 36 tes frontend, format dan build; 33 pemeriksaan browser dengan 1.000 aset fixture; lima pemeriksaan lifecycle melalui UI; axe nol pelanggaran pada enam tampilan. Preview FFmpeg nyata dan worker lokal membuktikan 15 pemeriksaan, termasuk orientasi, zoom, hook sebelum/pada detik 3, H.264/AAC, korelasi audio, progress, enam frame, bank, source credit, dan tiga delivery shadow. Packaging wheel memuat UI/API/worker/font tanpa DB atau credential. Verifier dan browser wrapper dapat dijalankan ulang.

Batas bukti: provider memakai transport fixture. Tidak ada publikasi sosial, balasan, pesan Telegram, atau akses credential produksi. Transkripsi model nyata, token/Drive sync operator, native service registration, akses HTTPS publik, desktop signing, dan cutover belum diuji. SQLite/session fixture dan screenshot yang memuat path lokal tetap privat. CI/upload hanya menerima laporan tes, evidence sintetis, dan wheel.

Integrasi Git: commit/push branch dilakukan setelah PASS lokal; main hanya digabung fast-forward setelah CI pada SHA branch lulus. CI main dan SHA remote diperiksa lagi. Hash akhir, run ID, dan manifest pembersihan disimpan pada `.artifacts/` privat agar tidak membuat commit hanya untuk mencatat hash dirinya sendiri. Worktree baru dihapus tanpa force setelah seluruh layanan fixture berhenti, bukti diarsipkan, serta merge/push/CI selesai.

Review integrasi tambahan: CI awal pada commit `13d787d` lulus di tiga OS, termasuk browser Linux. Review menemukan readiness startup sebelum bind port, resolusi bank relatif, dan AI yang masih aktif pada restore. Perbaikan menambahkan handshake API siap, regresi port terpakai/URL stale, resolusi bank konsisten, penonaktifan AI/transkripsi saat restore, serta fixture path Unicode. Verifikasi diulang pada commit perbaikan sebelum main digabung.
