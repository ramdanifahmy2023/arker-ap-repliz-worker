# Informasi sensitif dan batas operasional

Repo publik hanya memuat source, dokumen, font berlisensi, dan fixture buatan. Password, token, cookies, ID akun privat, DB, log produksi, backup, serta media pengguna tidak boleh masuk Git, issue, PR, atau artefak CI.

Login memakai scrypt dengan salt acak; database menyimpan hash sesi. Cookie HttpOnly/SameSite, token CSRF, pemeriksaan Origin/Host, pembatasan percobaan login, dan batas ukuran body melindungi API. Server CLI terikat loopback. HTTPS/origin untuk akses jarak jauh harus dipasang tersendiri.

Credential disimpan sebagai versi terenkripsi pada Credential di direktori privat. Kunci enkripsi berada di host yang sama dengan data: ini melindungi file credential dari pembacaan langsung, bukan dari pihak yang menguasai akun OS/host. Windows membutuhkan ACL privat pada folder pilihan operator. Frontend hanya menerima status dan versi. Nilai credential tidak masuk response GET, event, export umum, atau backup DB/jurnal.

Backup tetap sensitif: hash login, riwayat, caption, dan konteks dapat berada di DB. Simpan backup privat. Jurnal menjaga intent sebelum request provider. Timeout/hasil ambigu ditahan; tombol retry tidak mengulang pengiriman yang memiliki intent. Restore selalu shadow/paused dengan gate rekonsiliasi.

Jangan menguji kelemahan terhadap akun atau worker produksi. Suite memakai fixture terisolasi dan memblokir koneksi provider. Bila menemukan rahasia, jangan menyalinnya ke issue. Laporkan privat melalui mekanisme keamanan GitHub bila tersedia dan cabut akses melalui pemiliknya.

Ownership adalah scope eksplisit pada satu instalasi. Arker tidak menjamin eksklusivitas lintas host dan tidak mematikan native automation provider. Aktivasi live memerlukan akun uji khusus atau cutover yang membuktikan hanya satu pengirim/replier per akun/post.
