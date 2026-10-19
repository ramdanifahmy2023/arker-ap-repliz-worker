"""Generate deterministic, self-contained SVG explanations with synthetic data."""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BG = "#0C1422"
PANEL = "#152235"
BORDER = "#34465E"
TEXT = "#EDF4FC"
MUTED = "#A9BBD1"
MINT = "#64E4BC"
AMBER = "#FFD080"
BLUE = "#8BBDFF"


class Canvas:
    def __init__(self, width, height, title, description):
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
            f'<title id="title">{escape(title)}</title><desc id="description">{escape(description)}</desc>',
            '<style>text{font-family:Arial,Helvetica,sans-serif;font-variant-numeric:tabular-nums}</style>',
        ]
        self.rect(0, 0, width, height, BG, radius=18)

    def rect(self, x, y, width, height, fill=PANEL, stroke="none", radius=12):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def text(self, x, y, value, size=17, color=TEXT, weight=400, anchor="start"):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>')

    def line(self, x1, y1, x2, y2, color=BORDER, width=2):
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>')

    def circle(self, x, y, radius, color):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}"/>')

    def path(self, data, color=MINT, width=3, fill="none"):
        self.parts.append(f'<path d="{data}" fill="{fill}" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')

    def label(self, x, y, text, width, color=MINT):
        self.rect(x, y, width, 30, "#21364A", radius=6)
        self.text(x + 12, y + 20, text, 12, color, 700)

    def arrow(self, x1, y, x2, color=MINT):
        self.line(x1, y, x2, y, color)
        self.path(f"M {x2-7} {y-5} L {x2} {y} L {x2-7} {y+5}", color, 2)

    def output(self):
        return "\n".join(self.parts + ["</svg>", ""])


def dashboard():
    c = Canvas(1440, 1030, "Arker — konsep dashboard, data simulasi", "Konsep statis dashboard dengan tren publikasi, antrean per tahap, progress render, serta tiga jalur delivery. Tidak terhubung ke worker.")
    c.rect(0, 0, 230, 1030, "#0A101B", radius=18)
    c.text(30, 58, "ARKER", 29, TEXT, 700)
    c.text(30, 84, "REPLIZ WORKER", 11, MUTED, 700)
    c.line(28, 108, 202, 108)
    c.text(30, 146, "PEMANTAUAN", 11, MUTED, 700)
    for i, name in enumerate(["Ringkasan", "Peta alur", "Kendali worker", "Perlu perhatian"]):
        y = 164 + i * 46
        if not i:
            c.rect(18, y, 194, 38, "#203D40", radius=7)
            c.rect(18, y + 8, 3, 22, MINT, radius=1)
        c.circle(38, y + 19, 3, MINT if not i else MUTED)
        c.text(54, y + 25, name, 14, MINT if not i else MUTED, 600 if not i else 400)
    groups = [("Konten", "4"), ("Akun & publikasi", "4"), ("Video, AI & interaksi", "4"), ("Koneksi & storage", "3"), ("Administrasi", "3")]
    for i, (name, count) in enumerate(groups):
        y = 398 + i * 60
        c.text(30, y, name, 14, TEXT, 600)
        c.text(200, y, count, 12, MUTED, anchor="end")
        c.line(30, y + 20, 200, y + 20, "#1D2C40", 1)
    c.rect(20, 874, 190, 122, "#18273A", radius=10)
    c.label(34, 889, "KONSEP DESAIN", 160, AMBER)
    c.text(34, 944, "Data simulasi", 16, TEXT, 600)
    c.text(34, 970, "Belum terhubung", 13, MUTED)

    c.text(266, 48, "OPERASI / RINGKASAN", 12, MUTED, 700)
    c.text(266, 91, "Ruang kendali", 34, TEXT, 700)
    c.text(266, 121, "Baca progres. Temukan hambatan. Atur pekerjaan berikutnya.", 16, MUTED)
    c.label(1148, 38, "SIMULASI · BUKAN LIVE", 250, AMBER)
    c.text(1396, 104, "7 hari contoh  /  WIB", 14, MUTED, anchor="end")

    metrics = [("Aset diterima", "120", "sumber · periode contoh", BLUE), ("Sudah tayang", "264", "delivery terverifikasi", MINT), ("Terjadwal", "48", "delivery · belum tayang", BLUE), ("Perlu perhatian", "24", "delivery · lihat penyebab", AMBER)]
    for i, (label, number, sub, color) in enumerate(metrics):
        x = 266 + i * 288
        c.rect(x, 153, 266, 130, PANEL, BORDER)
        c.text(x + 20, 182, label, 14, MUTED)
        c.text(x + 20, 231, number, 39, color, 700)
        c.text(x + 20, 258, sub, 12, MUTED)

    c.rect(266, 305, 664, 318, PANEL, BORDER)
    c.text(288, 339, "Publikasi terverifikasi", 20, TEXT, 600)
    c.text(288, 364, "Delivery per hari · total 264 · data simulasi", 13, MUTED)
    for tick, y in [(60, 399), (40, 454), (20, 509), (0, 564)]:
        c.line(334, y, 904, y, "#2B3A50", 1)
        c.text(316, y + 4, tick, 11, MUTED, anchor="end")
    values = [24, 31, 27, 42, 36, 48, 56]
    for i, (day, value) in enumerate(zip(["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"], values)):
        x = 352 + i * 80
        height = value * 2.65
        c.rect(x, 564 - height, 42, height, MINT if i == 6 else "#428D80", radius=4)
        c.text(x + 21, 554 - height, value, 12, TEXT, 600, "middle")
        c.text(x + 21, 588, day, 12, MUTED, anchor="middle")

    c.rect(952, 305, 444, 318, PANEL, BORDER)
    c.text(974, 339, "Antrean per tahap", 20, TEXT, 600)
    c.text(974, 364, "Jumlah aset menunggu · snapshot simulasi", 13, MUTED)
    for i, (stage, value) in enumerate([("Unduh", 6), ("Analisis", 4), ("Render", 8), ("Drive", 2), ("Jadwal", 10)]):
        y = 395 + i * 40
        c.text(974, y + 15, stage, 14, TEXT)
        c.rect(1058, y + 2, 268, 15, "#26364D", radius=4)
        c.rect(1058, y + 2, value * 24, 15, AMBER if stage == "Render" else BLUE, radius=4)
        c.text(1370, y + 16, value, 14, AMBER if stage == "Render" else TEXT, 600, "end")

    c.rect(266, 646, 1130, 170, PANEL, BORDER)
    c.text(288, 678, "Proses aktif", 20, TEXT, 600)
    c.label(1150, 660, "CONTOH TELEMETRY", 224, BLUE)
    c.text(288, 716, "ASET DEMO-17", 12, MUTED, 700)
    c.text(448, 716, "Render video", 16, TEXT, 600)
    c.text(1368, 716, "63%", 22, MINT, 700, "end")
    c.rect(288, 738, 1084, 12, "#293C52", radius=6)
    c.rect(288, 738, 683, 12, MINT, radius=6)
    c.text(288, 784, "Persen dari proses terukur. Angka tidak naik sendiri saat data berhenti.", 13, MUTED)

    c.rect(266, 838, 1130, 151, PANEL, BORDER)
    c.text(288, 871, "ASET DEMO-12", 12, MUTED, 700)
    c.text(448, 871, "Drive terverifikasi · tiga tujuan, tiga status", 16, TEXT, 600)
    for x, platform, state, color in [(288, "TikTok", "Sudah tayang", MINT), (650, "Facebook", "Terjadwal", BLUE), (1012, "YouTube", "Hasil belum pasti", AMBER)]:
        c.line(x, 893, x + 330, 893, color, 3)
        c.text(x, 921, platform, 14, MUTED)
        c.text(x, 950, state, 18, color, 600)
    c.text(266, 1014, "KONSEP STATIS  ·  Animasi, koneksi, dan kontrol akan dibangun setelah kontrak data disepakati.", 12, MUTED)
    return c.output()


def architecture():
    c = Canvas(1440, 770, "Arsitektur Arker yang direncanakan", "Web, API kontrol dan worker dipisahkan. Provider berada di belakang adapter. Data privat tidak berada di repo publik.")
    c.text(48, 56, "ARKER / ARSITEKTUR", 13, MINT, 700)
    c.text(48, 103, "Satu pusat kendali. Eksekusi tetap terjaga.", 34, TEXT, 700)
    c.text(48, 135, "Rancangan terpisah dari instalasi worker yang sudah berjalan.", 18, MUTED)
    c.label(1170, 42, "RENCANA · BELUM AKTIF", 226, AMBER)
    boxes = [
        (48, "01", "Web app", ["Dashboard & 22 menu", "Chart + progress", "Form konfigurasi"], BLUE),
        (396, "02", "Control API", ["Login & validasi", "Config version", "Perintah durable"], MINT),
        (744, "03", "Worker", ["Antrean & ownership", "Jurnal & rekonsiliasi", "Telemetry tahap"], MINT),
        (1092, "04", "Adapter", ["Repliz / AI / media", "Drive / Telegram", "Service manager OS"], BLUE),
    ]
    for x, number, title, lines, color in boxes:
        c.rect(x, 196, 300, 230, PANEL, BORDER)
        c.text(x + 24, 235, number, 14, color, 700)
        c.text(x + 24, 276, title, 26, TEXT, 700)
        for j, line in enumerate(lines):
            c.text(x + 24, 318 + j * 29, line, 16, MUTED)
    for x in (348, 696, 1044):
        c.arrow(x + 8, 306, x + 39)
    c.path("M 894 426 L 894 462 L 198 462 L 198 426", BLUE, 2)
    c.text(548, 487, "Status, hasil, event, dan konfirmasi konfigurasi", 15, BLUE, anchor="middle")
    c.rect(48, 526, 630, 170, "#152D2E", "#3D6B61")
    c.text(72, 562, "DATA PRIVAT / DI LUAR GIT", 13, MINT, 700)
    c.text(72, 602, "Credential · database · jurnal · bank konten", 22, TEXT, 600)
    c.text(72, 638, "Browser hanya menerima status dan referensi yang diizinkan.", 16, MUTED)
    c.text(72, 668, "Default shadow. Tidak ada publikasi otomatis dari instalasi baru.", 15, MUTED)
    c.rect(706, 526, 686, 170, PANEL, BORDER)
    c.text(730, 562, "TARGET LINTAS PLATFORM", 13, BLUE, 700)
    c.text(730, 602, "Windows  /  macOS  /  Linux", 25, TEXT, 600)
    c.text(730, 638, "Path, service, permission dan sinkronisasi melalui adapter.", 16, MUTED)
    c.text(730, 668, "Dukungan runtime dibuktikan per OS sebelum rilis.", 15, MUTED)
    c.text(48, 740, "REPO PUBLIK: source dan spesifikasi  ·  OPERASI: data privat dan satu pemilik pengiriman", 13, MUTED)
    return c.output()


def configuration():
    c = Canvas(1440, 660, "Alur konfigurasi Arker yang direncanakan", "Repliz, bank konten dan folder Drive divalidasi sebelum apply. Worker harus mengonfirmasi versi sebelum panel menyatakan aktif.")
    c.text(48, 55, "ARKER / KONFIGURASI", 13, MINT, 700)
    c.text(48, 103, "Tersimpan belum berarti sudah dipakai worker.", 32, TEXT, 700)
    c.text(48, 137, "Setiap perubahan punya pemeriksaan, dampak yang jelas, dan konfirmasi.", 18, MUTED)
    stages = [
        (48, "01", "Isi perubahan", "Repliz / bank / Drive"),
        (326, "02", "Periksa", "Koneksi, izin, file"),
        (604, "03", "Tinjau dampak", "Job baru atau restart"),
        (882, "04", "Terapkan", "Kirim versi ke worker"),
        (1160, "05", "Aktif", "Worker mengonfirmasi"),
    ]
    for x, number, title, subtitle in stages:
        c.rect(x, 192, 230, 150, PANEL, BORDER)
        c.text(x + 18, 225, number, 13, MINT, 700)
        c.text(x + 18, 269, title, 22, TEXT, 600)
        c.text(x + 18, 306, subtitle, 14, MUTED)
        if x < 1160:
            c.arrow(x + 240, 268, x + 266)
    items = [
        (48, "REPLIZ", "Kredensial tetap privat", ["Tes hanya-baca sebelum apply.", "Nilai lama tidak dikirim ke browser.", "Kegagalan tidak mereset kuota."], MINT),
        (506, "BANK KONTEN", "Pilih folder mesin worker", ["Periksa volume, izin, dan ruang.", "Aset lama menjaga referensinya.", "Tidak memindah file otomatis."], BLUE),
        (964, "GOOGLE DRIVE", "Buktikan pasangan file", ["Baca folder ID dari link yang valid.", "Cocokkan ukuran dan checksum.", "Satu penulis sinkronisasi."], AMBER),
    ]
    for x, label, title, lines, color in items:
        c.rect(x, 384, 428, 208, PANEL, BORDER)
        c.text(x + 20, 419, label, 12, color, 700)
        c.text(x + 20, 455, title, 22, TEXT, 600)
        for j, line in enumerate(lines):
            c.text(x + 20, 492 + j * 29, line, 16, MUTED)
    c.text(48, 634, "RENCANA FITUR  ·  Belum ada form aktif, kredensial tersimpan, atau perubahan pada worker produksi.", 13, MUTED)
    return c.output()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    directory = ROOT / "docs/assets"
    images = {"dashboard-concept.svg": dashboard(), "architecture.svg": architecture(), "configuration-flow.svg": configuration()}
    if args.check:
        failed = [name for name, source in images.items() if not (directory / name).exists() or (directory / name).read_text(encoding="utf-8") != source]
        for name in failed:
            print("OUTDATED " + name)
        print("PASS: deterministic diagrams" if not failed else "FAIL: regenerate diagrams")
        return bool(failed)
    directory.mkdir(parents=True, exist_ok=True)
    for name, source in images.items():
        (directory / name).write_text(source, encoding="utf-8", newline="\n")
    print("Generated 3 SVG explanations; all dashboard data is synthetic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
