# Berkontribusi

Saat ini kontribusi berfokus pada rencana, kontrak, visual, dan fondasi validasi. Labeli usulan, fixture, implementasi, dan bukti runtime secara berbeda.

1. Buat branch `work/YYYYMMDD-topik` dari main terbaru.
2. Gunakan runtime/fixture sendiri; jangan menghubungkan kredensial produksi.
3. Periksa perubahan dengan `python scripts/validate.py` dan `python -m unittest discover -s tests -v`.
4. Tinjau visual pada ukuran sebenarnya dan layar sempit jika mengubah desain.
5. Tulis PR tentang masalah, perilaku hasil, pemeriksaan, serta batas bukti. Tunggu CI pada SHA yang ditinjau.
6. Perbarui docs/WORKLOG.md dan dokumentasi yang berubah; jangan memasukkan data privat ke issue atau artefak CI.

Lisensi belum ditetapkan; jangan menambahkan kode pihak ketiga tanpa kejelasan asal dan lisensinya.
