# Windows, macOS, dan Linux

Web/API/worker menggunakan Python dan TypeScript. Verifier aplikasi, subprocess lifecycle, serta preview FFmpeg dijalankan oleh CI pada ketiga OS. Detail bukti ada di [penerimaan](../ACCEPTANCE.md); hasil job pada SHA tertentu menjadi acuan kelulusan.

| Area | Windows | macOS | Linux |
| --- | --- | --- | --- |
| Data privat | LOCALAPPDATA/Arker | Library/Application Support/Arker | XDG_DATA_HOME/arker |
| File lock | msvcrt byte lock | flock | flock |
| Autostart user | Task Scheduler saat login | launchd LaunchAgent | systemd user unit |
| Media | FFmpeg/ffprobe dari PATH | FFmpeg/ffprobe dari PATH | FFmpeg/ffprobe dari PATH |
| UI utama | Browser | Browser | Browser |
| Desktop opsional | pywebview + WebView2 | pywebview + Cocoa/WebKit | pywebview + Qt/GTK |
| Drive sync | Aplikasi sinkronisasi eksternal | Aplikasi sinkronisasi eksternal | Aplikasi sinkronisasi eksternal |

Database dan jurnal harus berada pada disk lokal yang mendukung locking/atomic rename. Path dengan spasi dan argumen service per OS diuji. CLI memakai subprocess argv, bukan shell string dari pengguna. Binary pendukung harus berupa binary lokal bernama sesuai tool; UNC dan script batch tidak diterima melalui formulir konfigurasi.

[Google Drive Desktop tidak tersedia di Linux](https://support.google.com/drive/answer/2375082?hl=en). Operator Linux memilih satu sinkronisator eksternal. Arker hanya memeriksa file yang sudah ada melalui API Drive, tidak memasang uploader baru. Integrasi sinkronisator pada host operator belum dibuktikan oleh fixture CI.

Permission POSIX memakai 0700/0600. Windows menggunakan direktori profil pengguna; `chmod` Python bukan pengganti ACL Windows. Jika memilih folder bersama melalui `--data-dir`, operator harus membatasi ACL secara eksplisit. Jangan menyatakan folder bersama aman hanya karena file credential terenkripsi.

Extra `desktop` menyediakan perintah `arker desktop` untuk membuka API lokal. [Prasyarat pywebview](https://pywebview.flowrl.com/guide/installation.html) berbeda per OS. Paket installer, signing, auto-update, dan pengujian native WebView lintas OS belum termasuk bukti rilis web ini.

CI menguji Python3.12 pada runner `ubuntu-latest`, `macos-latest`, dan `windows-latest`. Tes lokal tambahan memakai macOS ARM dan Python3.14. Versi OS/arsitektur aktual tercatat dalam metadata run; tidak mengklaim semua distro Linux, Windows ARM, atau semua versi macOS.
