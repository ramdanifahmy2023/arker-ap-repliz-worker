# Rancangan visual, chart, dan animasi

Status: konsep. Gambar pada README adalah simulasi, bukan screenshot aplikasi produksi.

## Arah visual

Dashboard modern untuk membaca operasi dengan cepat: latar netral, hierarki tipografi jelas, angka tabular, garis chart tegas, serta aksen untuk tindakan dan tahap aktif. Light/dark mengikuti sistem dengan pilihan pengguna. Usulan konsep memakai slate dan mint untuk aktivitas; warna peringatan/error dipisahkan dari identitas platform.

Identitas produk ditunjukkan melalui satu jalur aset yang bercabang menjadi tiga jalur delivery. Sidebar memakai enam kelompok navigasi. Bagian utama mengutamakan tahap yang menumpuk, progres pekerjaan, dan tindakan yang relevan.

UI UX Pro Max dan antislop digunakan selama perencanaan dan review. Pencarian design-system dua kali menghasilkan pola landing page yang tidak cocok; pola hero/CTA/glass otomatis tidak diadopsi. Panduan chart bar/line, label waktu, feedback formulir dan reduced motion dipilih sesuai kebutuhan. Arah final masih perlu preview bersama pengguna.

## Susunan Ringkasan

1. Header: nama worker, status koneksi, timestamp data, filter waktu/platform, tombol gerak minimal.
2. Ringkasan: aset masuk, delivery terverifikasi, menunggu, perlu perhatian; satuan ditulis.
3. Area utama: tren masuk/selesai dan antrean tiap tahap.
4. Aktivitas: video yang sedang dikerjakan dengan timeline dan tiga status tujuan.
5. Panel perhatian: penyebab dominan, umur pekerjaan tertua, dan tindakan yang aman.
6. Bagian lanjutan: kuota akun, durasi tahap, ruang disk, dan penggunaan AI.

## Kontrak chart

| Chart | Bentuk | Definisi data dan interaksi |
| --- | --- | --- |
| Tren pekerjaan | Line/column dengan satuan terpisah | Aset diterima per interval; delivery published_verified per interval. Tidak memakai keduanya untuk rasio sukses. Klik membuka daftar yang membentuk titik. |
| Hasil per platform | Stacked bar | Jumlah delivery menurut status yang saling eksklusif pada snapshot yang sama. Scheduled terpisah dari published, failed, held dan unknown. |
| Hambatan pipeline | Horizontal bar | Jumlah aset menunggu pada tiap tahap; durasi menunggu terpisah dari waktu proses aktif. |
| Durasi proses | Bar p50/p95 | Sampel tahap selesai pada periode terpilih, jumlah sampel terlihat. Tanpa sampel ditulis belum tersedia. |
| Umur antrean | Histogram | Usia pekerjaan yang belum selesai, batas bucket dan timezone jelas. |
| Kuota akun | Segmented bar | Pemakaian + reservasi + sisa sesuai batas efektif. ID remote yang sama dihitung sekali; pemakaian eksternal diperhitungkan. |
| Penyimpanan | Bar kapasitas | Byte terpakai dan bebas dari volume worker, bukan browser pengguna. |
| Penggunaan AI | Line/bar | Token yang dilaporkan provider. Biaya hanya jika harga, mata uang, tanggal, dan kelengkapan token diketahui; estimasi dilabeli. |
| Pertumbuhan akun | Line | Snapshot ID akun yang sama pada tanggal yang tepat. Gap data tidak diisi nol atau diinterpolasi sebagai fakta. |

Filter waktu memakai Asia/Jakarta sebagai tampilan awal, menyimpan timestamp UTC. Respons mencantumkan cakupan, generated_at, source_updated_at, snapshot/config version, unit dan kualitas data. Angka contoh hanya boleh berada dalam mode demo yang terlihat jelas.

Semua chart memiliki label angka, ringkasan teks, tabel data alternatif, fokus keyboard, serta tooltip yang juga dapat dibuka dengan sentuhan. Status tidak hanya dibedakan lewat warna. Klik chart membawa filter yang sama ke tabel detail. Chart kosong tetap menyebutkan alasannya.

## Progress tanpa angka buatan

| Lapisan | Informasi |
| --- | --- |
| Batch | Sumber lengkap / total sumber diterima; ditahan dan gagal ditampilkan terpisah. Sumber lengkap berarti semua tujuan wajib terverifikasi. |
| Aset bersama | Tahap unduh → analisis → hook → render → bank → verifikasi Drive; checkpoint tercatat. |
| Proses terukur | Persentase byte unduh atau timestamp render hanya jika telemetry/total valid tersedia. Telemetry ini masih perlu diimplementasikan. |
| Proses tidak terukur | “Menyusun caption · berjalan 18 detik” dengan indikator aktivitas tanpa persen. |
| Delivery | Status per TikTok/FB/YouTube; “2 dari 3 tujuan tayang” boleh, tetapi bukan klaim 67% waktu pengerjaan. |

Persen render tidak berarti aset sudah diverifikasi, dan aset selesai render tidak berarti sudah published. 100% suatu tahap baru muncul setelah hasil tahap itu tervalidasi. Retry memiliki nomor percobaan dan dapat mengulang progres tahap dengan penjelasan, bukan lonjakan angka tanpa konteks. ETA hanya muncul dari model estimasi yang memiliki cukup sampel, rentang, dan label perkiraan.

## Perilaku animasi

| Elemen | Usulan gerak | Makna |
| --- | --- | --- |
| Progress terukur | Interpolasi menuju nilai terakhir, sekitar 200–400 ms | Memperlihatkan perubahan nyata tanpa melewati angka backend |
| Peta alur | Penanda bergerak singkat pada edge yang menerima event | Menunjukkan perpindahan tahap, bukan aktivitas tanpa bukti |
| Chart | Transisi data 250–450 ms; tidak mengulang entrance setiap refresh | Membantu membandingkan nilai lama dan baru |
| Status | Perubahan label dan highlight singkat | Menunjukkan worker menerima, menerapkan, atau menolak perintah |
| Detail panel | Transisi 150–250 ms dengan fokus terkelola | Mempertahankan orientasi pengguna |

Maksimal satu atau dua fokus animasi aktif dalam satu viewport. Animasi berhenti saat tab tersembunyi, worker offline, atau data stale; tulisan status tetap diperbarui secara jujur. `prefers-reduced-motion` dan kontrol aplikasi menghasilkan tampilan statis yang tetap lengkap. Tidak ada kedipan, parallax, atau pergerakan layout yang mengganggu klik. Pembaca layar menerima perubahan tahap penting, bukan tiap frame angka.

## State dan aksesibilitas

- Loading, kosong, gagal, parsial, stale, reconnecting, paused, applying, dan applied mempunyai teks serta tindakan berbeda.
- Kontras teks normal minimal 4.5:1; kontrol/fokus dan teks besar minimal 3:1, diukur pada kedua tema saat implementasi.
- Sasaran sentuh sekitar 44×44 CSS px, fokus terlihat, label form permanen, error di dekat kolom.
- Layout diperiksa pada 360, 768, dan 1440 CSS px serta zoom 200%. Filter tidak hilang ketika halaman diperbarui.
- Refresh data tidak memindahkan fokus, mengganti baris yang sedang dibaca secara mendadak, atau mengaktifkan tombol dua kali.

## Bukti sebelum dinyatakan selesai

Preview desktop/mobile kedua tema, rekaman animasi normal/reduced, navigasi keyboard, tabel alternatif chart, fixture koneksi putus, sumber telemetry, dan profil performa dengan 1.000 item. Preview fixture harus dibedakan dari koneksi worker nyata.
