# Berkontribusi

1. Buat branch `work/YYYYMMDD-topik` dan worktree dari main terbaru.
2. Gunakan runtime/fixture sendiri. Jangan menghubungkan credential produksi atau menyalin instalasi lain.
3. Pasang dependency lock dan jalankan `python scripts/verify.py --media`. Perubahan UI juga diperiksa melalui browser pada desktop/HP dan kedua tema.
4. Tinjau log kegagalan, keyboard, empty/loading/error/offline, serta reduced motion. Jangan memakai angka buatan tanpa label fixture.
5. Tulis PR yang menjelaskan masalah, perilaku hasil, pengujian, dan batas bukti. Tunggu CI pada SHA yang ditinjau.
6. Perbarui docs/WORKLOG.md dan panduan operasi yang berubah. Jangan unggah DB, credential, media pengguna, atau log privat.

Lisensi source belum ditetapkan. Jangan menambahkan kode pihak ketiga tanpa kejelasan asal/lisensi; font yang dibundel menyertakan OFL. Jangan force-push atau menyamakan fixture PASS dengan publikasi provider terverifikasi.
