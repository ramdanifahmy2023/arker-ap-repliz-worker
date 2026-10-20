# Hook dan caption yang lebih natural

Perubahan 20 Oktober 2026 berlaku untuk draft dan render baru. Publikasi tetap mengikuti mode aplikasi; pekerjaan ini diuji tanpa posting atau balasan nyata.

## Tulisan

Hook mengambil satu detail konkret yang bisa dibaca sekilas: maksimal sembilan kata dan 68 karakter. Caption memakai satu sampai tiga kalimat singkat, dengan batas 700 karakter untuk hasil AI. Bahasa bawaan santai, dengan singkatan yang wajar. Emoji boleh di caption jika cocok; hook memakai teks tanpa emoji agar font tetap terbaca. Konten serius memakai bahasa tenang.

Contoh berikut ditulis untuk menunjukkan arah gaya, bukan hasil pengujian model eksternal:

| Konteks buatan | Hook | Caption |
| --- | --- | --- |
| Kucing mendorong pintu hingga terbuka | Pintunya dibukain si kucing | Pintunya kebuka didorong kucing. |
| Adonan melewati tepi cetakan saat dituang | Adonannya kebanyakan, deh | Pas dituang, adonannya lewat pinggir cetakan. |
| Petugas menuntun warga melewati genangan | Warga dibantu melewati genangan | Petugas menuntun warga melewati jalan yang tergenang. |

Generator menghindari pancingan umum, ajakan like/follow, hashtag generik, dan pembuka seperti kuliah. Pertanyaan tetap boleh jika membahas detail video. Gaya akun mengubah pilihan kata; nama, lokasi, penyebab, perasaan, dan hasil kejadian tidak boleh ditebak. Aplikasi menambahkan `source: @username` dari identitas sumber terverifikasi setelah draft diperiksa.

Respons AI diperiksa bentuk, panjang, dan beberapa pola gaya yang jelas. Jika gagal, ada paling banyak satu permintaan perbaikan. Timeout atau HTTP gagal tidak diulang otomatis. Draft yang masih gagal ditahan. Pemeriksaan ini tidak membuktikan kebenaran fakta maupun menjamin semua hasil terasa natural; preview manusia tetap diperlukan.

Jika AI mati, caption berasal dari keterangan sumber. Kalimat sumber yang cukup pendek dapat menjadi hook; jika tidak ada kalimat yang pas, hook memakai “Cuplikan dari sumber”. Metadata kosong atau teks sumber yang tidak layak ditahan. Halaman detail menjelaskan asal tulisan agar salinan sumber tidak dikira hasil penulisan ulang AI.

Caption persona menerima hook yang sudah dirender, caption awal, dan catatan fakta sebelumnya. Hook dan daftar fakta asal dipertahankan; model menyesuaikan caption saja. Catatan fakta sebelumnya tetap merupakan keluaran draft, bukan verifikasi independen.

Caption akun yang gagal ditahan secara tersimpan, sehingga worker tidak memanggil AI lagi setiap siklus. Setelah memeriksa pengaturan/konteks, operator dapat memilih **Ulangi caption & lanjutkan** pada tujuan tersebut. Tindakan ini dapat melanjutkan pengiriman jika semua syarat live terpenuhi; tidak tersedia bila sudah ada intent atau hasil remote. Tujuan lain yang sudah terjadwal tidak disentuh.

## Tampilan tiga detik pertama

Gaya `barlow-compact-v2` memakai Barlow Semi Condensed putih, ukuran lebih besar, susunan baris seimbang, dan latar arang transparan yang mengikuti ukuran teks. Jarak dari tepi serta batas huruf diukur dalam piksel. Hook baru dibatasi dua baris; teks lama yang lebih panjang dapat memakai tiga baris dengan batas ukuran minimum. Teks yang tidak muat ditahan untuk diperpendek, bukan dipotong atau diperkecil tanpa batas.

Tulisan terlihat sejak frame pertama. Pada hasil 30 fps, frame 89 masih menampilkan hook dan frame 90 sudah bersih. Tidak ada karaoke atau animasi masuk yang menghabiskan waktu baca. Zoom 110%, orientasi sumber, tanpa mirror, H.264/AAC, dan audio sumber dipertahankan.

Render yang sudah tercatat dan hash-nya cocok dipakai kembali jika penyalinan ke bank perlu diulang. Perubahan gaya tidak merender ulang aset selesai atau mengganti payload pengiriman yang sudah tercatat. Render yang berubah di luar aplikasi ditahan untuk pemeriksaan.

## Bukti pemeriksaan

`python scripts/verify.py --media` menjalankan suite offline dan FFmpeg nyata pada video sintetis. Preview memeriksa frame 0/89/90, codec, audio, orientasi, zoom, serta alur worker. Tes copy memakai respons provider buatan, termasuk satu perbaikan, kegagalan berulang, konten serius, persona, dan sumber tanpa AI. Kredensial atau model AI eksternal tidak dipakai pada pengujian ini.
