# Generator Konsep Kandang Close House

Aplikasi Streamlit berbahasa Indonesia untuk membuat gambar konsep kandang peternakan melalui API gambar Trust, dengan fallback opsional Bynara. Ukuran bawaan 32 × 8 meter menekankan bentuk memanjang, tetapi dimensi dapat diubah dalam rentang 1–200 meter.

> **Batasan:** hasil adalah konsep visual, bukan gambar kerja konstruksi, perhitungan struktur, estimasi kapasitas ternak, rekomendasi teknis, atau bukti kepatuhan standar kesejahteraan hewan. Tulisan dan label dimensi yang dibuat model gambar dapat keliru; verifikasi selalu terhadap angka luas di aplikasi. Kebutuhan ruang, perilaku spesies, kualitas udara, suhu, cahaya, air, pakan, dan kesehatan hewan harus dinilai oleh pihak kompeten berdasarkan standar yang berlaku di lokasi dan kondisi usaha; gambar tidak dapat memastikannya.

## Fitur

- Dimensi, jenis ternak (ayam broiler, ayam petelur, bebek pedaging, sapi, kambing, domba, atau nama ternak lain), fitur kandang, dan gaya visual dapat dipilih. Untuk ternak lain, isi nama pada kolom yang muncul. Pilihan awal fitur menyesuaikan unggas atau ternak lain; jalur pakan menggunakan palung alih-alih pan feeder untuk ternak non-unggas, dan tersedia tempat minum otomatis.
- Luas dihitung langsung dari panjang × lebar.
- Brief **Rencana awal yang realistis** merangkum keputusan desain saat ini, urutan kerja dari validasi kebutuhan hingga commissioning, asumsi yang belum diketahui, serta risiko yang harus diperiksa sebelum desain dikunci. Brief tidak mengarang kapasitas, kebutuhan ventilasi, atau ukuran utilitas yang belum dihitung.
- Gaya visual diperlakukan sebagai arahan komposisi yang nyata: sketsa memakai garis dan arsiran grafit, render realistis memakai material serta cahaya alami, ilustrasi isometrik teknis memakai proyeksi dan garis teknis yang mudah dibaca, sedangkan render hiperrealistis memakai tekstur dan pencahayaan seperti foto arsitektur. Semua gaya tetap tunduk pada dimensi, tata letak, fitur terpilih, dan kesejahteraan hewan.
- Prompt menyertakan prinsip kesejahteraan hewan: akses pakan dan air bersih, ruang gerak dan istirahat, alas bersih dan aman, ventilasi, kenyamanan suhu, pencahayaan, perilaku alami, pengurangan takut dan stres, pemeriksaan ternak, serta area terpisah bagi ternak sakit. Rincian visual menyesuaikan jenis ternak: litter untuk broiler, tenggeran dan sarang untuk petelur, akses air untuk membersihkan kepala bagi bebek, lantai tidak licin dan ruang berbaring bagi sapi, serta area kering dan interaksi sosial bagi kambing dan domba. Untuk "Lainnya", prompt hanya memuat prinsip umum dan meminta penyesuaian sesuai spesies.
- Prompt positif dihasilkan otomatis dari pilihan, lalu dapat disunting di kolom **Prompt gambar**. Kolom **Negative prompt** dapat disunting untuk menyebut anatomi keliru, fitur tak dipilih, artefak, dan hal lain yang harus dihindari; kolom ini boleh dikosongkan. Pilihan **Render hiperrealistis** meminta tekstur, cahaya, dan skala seperti foto arsitektur, tetapi tetap mengutamakan dimensi, spesies, tata letak, serta kesejahteraan hewan. Untuk Trust kedua kolom digabung sebagai satu prompt; untuk fallback Bynara kedua kolom dikirim terpisah. Prompt gabungan Trust ditampilkan setelah tombol ditekan. Mengubah pilihan ukuran, jenis ternak, fitur, atau gaya menyusun ulang kedua kolom dan mengganti suntingan sebelumnya; prompt gabungan kosong atau lebih dari 8000 karakter ditolak. Prompt lengkap mencakup: cooling pad dan exhaust fan pada ujung berlawanan, jalur pakan dan nipple drinker terpisah di area ternak, serta zona biosekuriti berupa ruang transisi di luar dinding samping sebelum pintu masuk pekerja. Sudut pandang potongan atap meminta semua fitur pilihan terlihat tanpa memindahkan peralatan luar ke area ternak; detail lantai dan sarang disesuaikan dengan jenis ternak. Cooling pad digambarkan sebagai panel selulosa berbingkai dengan talang di bawahnya; exhaust fan sebagai kipas aksial yang menembus dinding, bukan pintu atau peralatan berdiri bebas. Potongan atap hanya untuk visualisasi, bukan lubang pada bangunan jadi. Penanda cooling pad diminta menunjuk tepat ke panel inlet, atau dihilangkan bila tidak akurat. Hasil tetap perlu diperiksa karena model gambar dapat mengabaikan instruksi tata letak dan penanda.
- Menggunakan layanan Trust untuk menghasilkan gambar, dengan Bynara sebagai penyedia cadangan opsional.
- Mendukung respons gambar `b64_json` maupun URL.
- Preview dan unduhan PNG.
- Pesan kesalahan aman untuk konfigurasi, autentikasi, kredit, rate limit, jaringan, respons rusak, dan gambar invalid.

## Persyaratan

- Python 3.11 atau lebih baru
- Akses ke layanan gambar yang digunakan (permintaan dapat dikenai biaya)

## Instalasi dan menjalankan

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Untuk deploy online, pilih `app.py` sebagai berkas utama di Streamlit Community Cloud. Konfigurasi rahasia aplikasi dikelola melalui pengaturan **Secrets** pada aplikasi yang di-deploy; berkas rahasia lokal tidak ikut diunggah ke repositori.

## Pengujian

Pengujian menggunakan mock dan tidak memanggil API berbayar:

```bash
python -m pytest -q
```

Uji startup headless:

```bash
streamlit run app.py --server.headless true --server.port 8501
```

Lalu buka `http://localhost:8501`.

## Pengolahan gambar

Gambar hasil dibatasi maksimum 20 MiB; JPEG/WebP dikonversi menjadi PNG yang valid. Aplikasi membatasi ukuran respons dan hanya mengunduh gambar dari alamat HTTPS publik.

## Isi paket

Jalankan `python build_zip.py` untuk membuat `dist/streamlit-kandang.zip`. Paket distribusi hanya berisi source, konfigurasi non-rahasia, dokumentasi, dan tests. Berkas rahasia, virtualenv, cache, serta gambar hasil tidak disertakan.
