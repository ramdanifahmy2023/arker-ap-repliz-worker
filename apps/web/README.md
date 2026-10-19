# Antarmuka Arker

React + TypeScript dengan build Vite. Ke-22 menu memakai API instalasi yang sama; tidak ada angka operasional demo otomatis pada aplikasi. Dataset contoh hanya dibuat oleh skrip browser pada direktori pengujian privat.

## Menjalankan

Dari root proyek, siapkan API dan admin dengan CLI sesuai README utama. Kemudian:

```sh
npm ci --prefix apps/web
npm run build --prefix apps/web
```

API menyajikan hasil `apps/web/dist` pada alamat layanan. Untuk pengembangan UI, `npm run dev --prefix apps/web` memakai proxy `/api` ke layanan lokal pada port 8765. Akses browser tetap melalui origin dev server sehingga cookie sesi dan pemeriksaan CSRF dapat bekerja.

## Pemeriksaan

```sh
npm run test --prefix apps/web
npm run build --prefix apps/web
npm run format:check --prefix apps/web
```

Tes mencakup 22 tujuan navigasi, formulir kredensial yang hanya menulis, token CSRF, konflik konfigurasi, perintah asinkron, penolakan URL yang tidak aman, dan progres tanpa persentase buatan. Uji browser terhadap API nyata tersedia di `scripts/test_browser.py`; gunakan runtime fixture terpisah, bukan instalasi produksi. Lihat `docs/UX_REVIEW.md` untuk cakupan dan batas buktinya.

## Batas tanggung jawab

- `api.ts` mengelola permintaan same-origin, CSRF dalam memori, dan sesi kedaluwarsa.
- `model.ts` menyimpan navigasi, label status, format WIB, dan helper data.
- `components.tsx` menyediakan tabel, chart dengan data alternatif, progres, dan status perintah.
- `configuration.tsx` mengelola draft, validasi, konflik versi, simpan, dan konfirmasi worker.
- `content-pages.tsx` menampilkan antrean, alur, detail video, dan tiga delivery.
- `operation-pages.tsx` menampilkan akun, kuota, koneksi, penyimpanan, laporan, dan administrasi.
- `service-controls.tsx` mengelola proses melalui supervisor yang memiliki worker. API tetap berjalan ketika worker berhenti.

Rahasia tidak masuk URL, localStorage, log browser, atau bundle. Preferensi tema dan gerak disimpan di localStorage. Nilai kredensial baru tetap di memori formulir sampai berhasil disimpan atau halaman ditutup. Snapshot yang gagal dimuat menampilkan error; progress berhenti bergerak saat heartbeat tidak aktif, tab tersembunyi, atau pengguna memilih gerak minimal.
