# Rencana Windows, macOS, dan Linux

Target produk adalah tiga OS. Fondasi yang tersedia sekarang hanya dokumentasi, spesifikasi, visual, serta validator Python. Kelulusan CI fondasi tidak membuktikan worker, login, atau integrasi media berfungsi.

## Lapisan portabilitas

| Area | Windows | macOS | Linux |
| --- | --- | --- | --- |
| Data privat, usulan default | LOCALAPPDATA / Arker | Library/Application Support/Arker | XDG_DATA_HOME / arker |
| Service adapter, rencana | Windows service | launchd | systemd |
| Tool media | Temukan binary di PATH/config | Temukan binary di PATH/config | Temukan binary di PATH/config |
| Path dan permission | Drive letter, UNC policy, ACL, reparse point | Volume, permission, symlink | Mount, permission, symlink |
| Sinkronisasi Google Drive | Drive Desktop atau adapter teruji | Drive Desktop atau adapter teruji | Adapter eksternal teruji diperlukan |
| UI | Browser responsif | Browser responsif | Browser responsif |

Default akhir dikonfirmasi pada bootstrap. CLI inti memakai Python dan subprocess dengan daftar argumen, bukan shell string. Tidak hardcode direktori Homebrew, executable Docker, user home, atau separator path. File lock, atomic rename, shutdown, dan izin file harus mempunyai implementasi/tes sesuai OS.

SQLite dan jurnal berada pada disk lokal yang mendukung locking. Bank content dan Drive profile dipisahkan dari database. Path dengan spasi, Unicode, case sensitivity, drive letter dan volume lepas masuk matriks tes.

## Drive di Linux

[Google Drive for desktop tidak tersedia di Linux](https://support.google.com/drive/answer/2375082?hl=en). Karena itu, sinkronisasi menjadi adapter dengan kontrak: penulis tunggal, ID stabil, file lengkap, pemeriksaan ukuran/checksum, retry tahan crash, dan tidak menghapus referensi yang masih digunakan.

Pemilihan adapter Linux belum dilakukan. Rilis worker Linux yang memerlukan Drive ditahan sampai adapter dan preview nyata lulus. Repo tidak menginstal uploader baru atau menyentuh sinkronisasi instalasi lama.

## Tahap pembuktian

1. CI dokumentasi/validator pada ubuntu-latest, macos-latest, windows-latest.
2. Tes unit/integrasi worker dengan jaringan dimatikan pada tiga OS setelah kode tersedia.
3. Preview media nyata: probe, FFmpeg, transkrip, render, storage dan checksum Drive; tanpa publikasi.
4. Uji lifecycle: start, pause, restart, crash, recovery, update config dan permission.
5. Packaging, installer, signing bila diperlukan, dan smoke test pada versi OS/arsitektur yang diumumkan.

Tidak mengklaim seluruh distribusi Linux, Windows ARM, atau macOS Intel/ARM sudah didukung dari satu runner. Matriks versi/arsitektur rilis ditetapkan bersama hasil pengujian.

CI mengacu pada [panduan GitHub Actions untuk Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python). Action dipin ke commit rilis yang diperiksa dan token workflow hanya mendapat contents: read.
