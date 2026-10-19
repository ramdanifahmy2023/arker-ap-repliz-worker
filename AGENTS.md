# Aturan kerja Arker

Baca README, docs/plans/PRODUCT_PLAN.md, docs/plans/ROADMAP.md, docs/architecture/OVERVIEW.md, SECURITY.md dan docs/WORKLOG.md sebelum mengubah proyek.

Repo ini publik dan terpisah dari instalasi produksi lain. Jangan menyalin kode privat, DB, media, token, identitas admin privat atau konfigurasi aktif dari instalasi lain. Pengguna meminta implementasi penuh lalu pengujian tanpa publikasi. Aplikasi tersedia; bedakan tes fixture, media nyata, provider hanya-baca, dan hasil publik terverifikasi. Jangan mengaktifkan publikasi/reply dari permintaan pengujian.

Gunakan UI UX Pro Max serta antislop dan companion UI/human/mobile/copywriting yang terpasang untuk pekerjaan antarmuka. Antislop berlaku selama pekerjaan dan review. Jangan meminta pilihan ini ulang. Semua chart/progress harus memiliki sumber data dan makna satuan; fixture diberi label simulasi.

Implementasi berikutnya memakai branch/worktree terisolasi, runtime dan fixture sendiri. Default shadow, publish nonaktif. Satu pemilik per akun/post; hasil ambiguous tidak diulang buta. Jangan menghubungkan atau me-restart worker produksi tanpa lingkup yang secara eksplisit mencakup tindakan itu.

Jalankan python scripts/verify.py --media sebelum commit. Validator source saja bukan bukti runtime. Pertahankan portabilitas Windows/macOS/Linux. Update worklog dengan permintaan, file, pemeriksaan, batas bukti, branch, publikasi repo, dan pembersihan.

Jangan memasukkan password, token, path pengguna privat, DB, log produksi atau media nyata ke repo publik. Rahasia dikelola backend di data directory privat. Hindari shell string dari input dan action CI yang tidak dipin. Jangan force-push.
