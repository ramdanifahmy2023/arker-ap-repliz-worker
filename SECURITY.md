# Informasi sensitif dan batas operasional

Repo publik ini hanya menerima source yang memang boleh dipublikasikan, dokumen, dan fixture buatan. Password login, token provider, cookies, ID akun privat, DB, log produksi, backup dan media pengguna tidak boleh masuk Git, issue, PR atau artefak CI.

Credential yang kelak diisi melalui panel disimpan backend pada data directory privat. Frontend hanya menerima status configured dan versi, bukan nilai. Redaksi berlaku pada error, log transport, audit, ekspor dan backup umum.

Jangan menguji kelemahan terhadap akun/media/worker produksi. Gunakan fixture terisolasi. Jika menemukan rahasia dalam repo, jangan menyalinnya ke issue; laporkan secara privat melalui mekanisme keamanan GitHub jika tersedia dan cabut akses yang terdampak melalui pemiliknya.

Repo belum menjalankan layanan, autentikasi atau pengiriman konten. Mode live di implementasi berikutnya memerlukan ownership eksklusif dan validasi adapter. Mengganti token atau nama aplikasi tidak menghilangkan risiko dua pengirim.
