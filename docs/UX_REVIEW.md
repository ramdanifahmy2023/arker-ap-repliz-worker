# Pemeriksaan antarmuka Arker

Tanggal: 19 Oktober 2026. Antarmuka ini sudah diimplementasikan; screenshot publik memakai fixture pengujian yang diberi label. Angkanya tidak menunjukkan aktivitas akun atau publikasi nyata.

## Hasil dan bukti

| Pemeriksaan | Hasil | Lingkup |
| --- | --- | --- |
| Navigasi 22 menu | Lulus | Setiap route dibuka pada Chromium dan membaca API terautentikasi |
| Unit dan komponen frontend | 36 tes lulus | Navigasi, CSRF, rahasia, konflik versi, command, format waktu, URL, chart dan progres |
| TypeScript dan build produksi | Lulus | Dependency dikunci dalam package-lock; Node 22 |
| Browser dengan API nyata | 33 pemeriksaan lulus | Login, 22 route, konfigurasi tersimpan, credential write-only, penolakan URL/link, pagination, media preview, offline dan preferensi |
| Lifecycle melalui browser | 5 pemeriksaan lulus | Stop menjaga API aktif, start, restart dengan PID baru, konfigurasi applied, dan jeda pemrosesan terkonfirmasi |
| Aksesibilitas otomatis | 0 pelanggaran pada 6 tampilan | axe-core 4.14, aturan WCAG 2 A/AA dan 2.1 AA; overview light/dark, storage, mobile, detail media |
| Desktop, tablet, HP | Lulus pemeriksaan overflow | 1440, 768, dan 360 CSS px; tabel berubah menjadi baris berlabel pada HP |
| Pembesaran layout | Lulus emulasi viewport | 720 CSS px setara ruang layout dari viewport 1440 pada pembesaran 200%; bukan pengujian kontrol zoom native browser |
| 1.000 aset fixture | Pagination lulus | Daftar tidak merender 1.000 item sekaligus; setiap halaman aset memuat maksimal 25 |
| Preview video | Lulus | Pemutar mengambil video FFmpeg sintetis melalui endpoint media terautentikasi |

Laporan mesin dan screenshot lengkap disimpan lokal di `.artifacts/browser-review/`. `report.json` membedakan fixture, jumlah pemeriksaan, screenshot, dan hasil axe. Screenshot folder penyimpanan tidak dipublikasikan karena memuat lokasi lokal. [Screenshot dashboard publik](assets/dashboard-preview.png) hanya menampilkan data buatan dan banner fixture.

## Keputusan desain yang diterapkan

UI UX Pro Max dan antislop core/UI/human/mobile/copywriting digunakan selama implementasi dan review. Pencarian design-system menghasilkan rekomendasi halaman pemasaran yang tidak cocok; pola itu tidak digunakan. Panduan dashboard padat, label chart, keyboard, kontras, dan gerak minimal dipakai sesuai konteks operasi.

Sidebar mengelompokkan 22 menu dalam enam bagian yang bisa dilipat dan dicari. Tampilan terang dan gelap memakai aksen hijau untuk tindakan; peringatan dan kegagalan mempunyai label serta warna sendiri. Ukuran dasar teks 16 px. SVG chart mengikuti lebar kontainer agar sumbu tetap terbaca pada HP. Tabel panjang berubah menjadi pasangan label dan nilai pada layar sempit.

Animasi progress dan bar mengikuti nilai API dengan interpolasi CSS. Tahap tanpa total tidak mendapat angka persentase. Data chart mempunyai satuan terpisah untuk aset dan delivery, tabel alternatif, label waktu WIB, dan tautan ke filter yang sesuai. Reduced motion menghentikan animasi; keadaan offline dan tab tersembunyi menghentikan gerak progress. Tidak ada timer yang menaikkan progres atau angka statistik secara buatan.

Form konfigurasi memisahkan versi tersimpan dan aktif. Penyimpanan mencatat perintah penerapan; UI menunggu acknowledgment worker. Konflik versi tidak mengganti draft pengguna. Credential memakai input password yang tidak diisi ulang dari server dan dibersihkan setelah respons berhasil. Status credential yang tersimpan tidak dilabeli sebagai koneksi tervalidasi.

## Menjalankan ulang uji browser

Siapkan runtime fixture dan admin privat terlebih dahulu. File JSON kredensial hanya memuat akun fixture; jangan memasukkannya ke Git atau artefak CI publik. Browser harness membaca file ke memori, tidak menulis nilai password ke laporan.

```sh
python scripts/test_browser.py \
  --base-url http://127.0.0.1:18765 \
  --credentials .artifacts/browser-login.json \
  --output .artifacts/browser-review \
  --seed-data-dir .artifacts/browser-runtime \
  --preview-video .artifacts/media-preview-v1/preview.mp4
```

`--seed-data-dir` hanya menerima direktori di bawah `.artifacts`, mewajibkan publikasi nonaktif, dan membuat 1.000 aset fixture dengan status held/preview/published simulasi. Worker fixture ini tidak dijalankan. Opsi `--preview-video` menerima media sintetis milik pengujian. Tidak ada pengunduhan sumber atau request publikasi dalam harness.

Uji lifecycle memakai runtime lain yang kosong, tanpa kredensial provider atau antrean konten, melalui supervisor Arker:

```sh
python scripts/test_browser.py \
  --base-url http://127.0.0.1:18766 \
  --credentials .artifacts/browser-lifecycle-login.json \
  --output .artifacts/browser-review \
  --lifecycle-only
```

Harness axe memakai opsi bypass CSP pada browser pengujian agar library pemeriksaan lokal dapat disisipkan. CSP aplikasi tidak dilonggarkan. Pengujian login dan pemuatan aplikasi biasa juga dijalankan dengan CSP tetap berlaku.

## Batas bukti

Hasil browser berasal dari Chromium pada macOS, bukan bukti interaksi Safari, Firefox, atau pembungkus desktop native. Pemeriksaan otomatis tidak menggantikan uji pembaca layar manual. Layout zoom memakai emulasi viewport sebagaimana dijelaskan di tabel. Perilaku sinkronisasi Drive dan keberhasilan publikasi/reply provider tidak dibuktikan oleh pemeriksaan UI ini. Tidak ada pesan, postingan, atau balasan nyata yang dibuat.
