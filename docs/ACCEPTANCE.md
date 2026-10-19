# Bukti penerimaan implementasi

Tanggal: 19 Oktober 2026. Cakupan yang diminta: implementasi dan pengujian tanpa publikasi. Hasil pada halaman ini membedakan kode yang tersedia, pengujian fixture, preview media nyata, dan operasi provider.

| Area | Pemeriksaan | Batas bukti |
| --- | --- | --- |
| Login/API | Password hash, session, CSRF/Origin, pembatasan login, body bounded, akses media | Admin tunggal; reset email belum tersedia |
| Credential/config | Enkripsi, versi, input write-only, konflik edit, validasi URL/path, apply gagal mempertahankan versi aktif | Enkripsi memakai kunci lokal; tidak melindungi dari admin OS |
| Pipeline | 1 aset/3 delivery, dedup, konfigurasi historis, persona, kuota, jurnal/unknown, restart | Provider melalui transport fixture; belum publikasi nyata |
| Media | FFmpeg nyata: 60→30 fps, zoom110%, orientasi/no mirror, hook <3 detik, H.264/AAC, korelasi audio, progress | Sumber video/audio buatan; download Instagram tidak diuji terhadap akun nyata |
| Drive | ID/folder, ukuran, MD5/SHA1/SHA256, izin tautan, ID berubah ditahan | API fixture; sinkronisasi eksternal dan token operator belum dipasang |
| Telegram/AI | Intake privat, batas admin/backlog, dedup notifikasi, konteks, persona, transkrip argv | Tidak mengirim pesan atau memanggil model eksternal; model ASR nyata belum dipasang |
| Backup/cleanup | Manifest/hash, intent lengkap, restore shadow/paused, retensi, bank/frame/context/reference guards | Backup tidak memuat credential/media; restore live perlu review terpisah |
| Lifecycle | Lock antarproses, start, pause, stop/start worker dengan API tetap hidup, supervisor stop | Native launchd/systemd/Task Scheduler diuji pada definisinya; tidak diregistrasikan saat suite |
| UI | 22 halaman, formulir nyata, chart/tabel, pagination1000fixture, light/dark, HP, keyboard, reduced motion, offline | Browser Chromium; 200% memakai emulasi viewport CSS, bukan seluruh browser/AT |
| Portabilitas | Verifier yang sama pada matriks CI Windows/macOS/Linux Python3.12 | Runner/arsitektur sesuai job; bukan semua versi OS/perangkat |

Perintah utama: `python scripts/verify.py --media`. Tes Python memblokir koneksi provider dan memakai transport suntikan. Tes lifecycle hanya mengakses loopback/runtime sementara. Browser test dan screenshot memakai runtime sendiri; label fixture membedakan angka uji dari aktivitas produksi.

Bukti yang boleh dibagikan berupa laporan tes, manifest preview sintetis, dan wheel dari tab [Actions](https://github.com/ramdanifahmy2023/arker-ap-repliz-worker/actions). Runtime, DB, credential, dan log lokal tidak diunggah. Hash commit serta ID run akhir dicatat di bukti privat publikasi agar tidak membuat commit baru hanya untuk merekam hash dirinya sendiri.

Pengiriman publik, balasan sosial, pesan Telegram nyata, koneksi provider berkredensial, domain web publik, instalasi autostart native, installer/signing desktop, dan cutover produksi tidak dinyatakan lulus dari suite ini. Pengguna meminta menyelesaikan pengujian tanpa publikasi terlebih dahulu.
