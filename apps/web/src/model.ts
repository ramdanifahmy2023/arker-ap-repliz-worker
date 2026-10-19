export type Row = Record<string, any>;
export type Session = {
  authenticated: boolean;
  setup_required?: boolean;
  csrf_token?: string;
  user?: { id: string; email: string };
};
export type Menu = {
  id: string;
  label: string;
  group: string;
  icon: string;
  description: string;
};
export const menus: Menu[] = [
  {
    id: "overview",
    label: "Ringkasan",
    group: "Pemantauan",
    icon: "overview",
    description:
      "Lihat perjalanan konten dan kondisi worker dalam satu pandangan.",
  },
  {
    id: "flow",
    label: "Peta alur",
    group: "Pemantauan",
    icon: "flow",
    description:
      "Telusuri satu aset, dari link masuk hingga tiga tujuan terverifikasi.",
  },
  {
    id: "worker",
    label: "Kendali worker",
    group: "Pemantauan",
    icon: "worker",
    description: "Atur pemrosesan dan periksa apakah worker menerima perintah.",
  },
  {
    id: "attention",
    label: "Perlu perhatian",
    group: "Pemantauan",
    icon: "alert",
    description:
      "Pahami penyebab pekerjaan tertahan sebelum mengambil tindakan.",
  },
  {
    id: "intake",
    label: "Tambah konten",
    group: "Konten",
    icon: "plus",
    description:
      "Masukkan link Reel. Setiap sumber membuat satu aset dan tiga tujuan.",
  },
  {
    id: "queue",
    label: "Batch & antrean",
    group: "Konten",
    icon: "queue",
    description:
      "Cari konten, lihat tahap yang sedang berjalan, dan buka rinciannya.",
  },
  {
    id: "bank",
    label: "Bank konten",
    group: "Konten",
    icon: "folder",
    description: "Arsip sumber, hasil render, dan bukti verifikasi file.",
  },
  {
    id: "detail",
    label: "Detail & preview",
    group: "Konten",
    icon: "play",
    description: "Satu video, seluruh konteks, dan hasil setiap tujuan.",
  },
  {
    id: "accounts",
    label: "Akun sosial",
    group: "Akun & publikasi",
    icon: "users",
    description: "Identitas dan kesiapan akun berdasarkan snapshot provider.",
  },
  {
    id: "quota",
    label: "Rotasi & kuota",
    group: "Akun & publikasi",
    icon: "rotate",
    description: "Lihat pemakaian, reservasi, dan sisa kuota setiap akun.",
  },
  {
    id: "calendar",
    label: "Kalender posting",
    group: "Akun & publikasi",
    icon: "calendar",
    description: "Jadwal yang diterima provider dipisahkan dari rencana lokal.",
  },
  {
    id: "published",
    label: "Hasil publikasi",
    group: "Akun & publikasi",
    icon: "send",
    description:
      "Periksa bukti hasil tiap platform. Terjadwal belum berarti tayang.",
  },
  {
    id: "video",
    label: "Pengolahan video & AI",
    group: "Video, AI & interaksi",
    icon: "film",
    description:
      "Pengaturan proses untuk konten berikutnya, dengan hasil lama tetap tersimpan.",
  },
  {
    id: "personas",
    label: "Persona & caption",
    group: "Video, AI & interaksi",
    icon: "pen",
    description:
      "Gaya bahasa akun tetap mengikuti fakta video dan kredit sumber.",
  },
  {
    id: "comments",
    label: "Komentar & balasan",
    group: "Video, AI & interaksi",
    icon: "message",
    description:
      "Lihat konteks percakapan dan status balasan yang terdeduplikasi.",
  },
  {
    id: "reports",
    label: "Laporan & statistik",
    group: "Video, AI & interaksi",
    icon: "chart",
    description:
      "Analisis snapshot dan kualitas data, tanpa mengisi data hilang dengan nol.",
  },
  {
    id: "connections",
    label: "Koneksi layanan",
    group: "Koneksi & penyimpanan",
    icon: "link",
    description: "Simpan kredensial secara privat dan periksa akses layanan.",
  },
  {
    id: "telegram",
    label: "Telegram & notifikasi",
    group: "Koneksi & penyimpanan",
    icon: "bell",
    description: "Atur bot dan lihat status pengiriman pemberitahuan.",
  },
  {
    id: "storage",
    label: "Penyimpanan & cleanup",
    group: "Koneksi & penyimpanan",
    icon: "drive",
    description: "Pasangkan folder mesin worker dengan folder Google Drive.",
  },
  {
    id: "backups",
    label: "Backup & pemulihan",
    group: "Administrasi",
    icon: "archive",
    description:
      "Backup data dan periksa bukti sebelum pemulihan dalam keadaan nonaktif.",
  },
  {
    id: "activity",
    label: "Riwayat aktivitas",
    group: "Administrasi",
    icon: "history",
    description:
      "Jejak pekerjaan dan perubahan konfigurasi dengan waktu yang jelas.",
  },
  {
    id: "settings",
    label: "Pengaturan & akses",
    group: "Administrasi",
    icon: "settings",
    description:
      "Bandingkan konfigurasi tersimpan dan yang sudah dipakai worker.",
  },
];
export const labels: Record<string, string> = {
  download: "Mengunduh",
  inspect: "Memeriksa media",
  draft: "Menyusun hook",
  render: "Merender",
  drive: "Memverifikasi Drive",
  delivery: "Menyiapkan delivery",
  preview: "Preview siap",
  preview_ready: "Preview siap",
  waiting: "Menunggu prasyarat",
  blocked: "Tertahan",
  replied: "Balasan terkirim",
  tiktok: "TikTok",
  facebook: "Facebook",
  youtube: "YouTube",
  queued: "Menunggu",
  pending: "Menunggu",
  downloading: "Mengunduh",
  downloaded: "Unduhan siap",
  analyzing: "Menganalisis",
  drafting: "Menyusun caption",
  rendering: "Merender",
  rendered: "Render siap",
  banked: "Tersimpan di bank",
  drive_wait: "Menunggu Drive",
  drive_ready: "Drive terverifikasi",
  ready: "Siap",
  scheduled: "Terjadwal",
  published: "Tayang terverifikasi",
  published_verified: "Tayang terverifikasi",
  failed: "Gagal",
  held: "Ditahan",
  submit_unknown: "Hasil belum diketahui",
  unknown: "Hasil belum diketahui",
  completed: "Selesai",
  complete: "Selesai",
  processing: "Diproses",
  accepted: "Diterima",
  running: "Berjalan",
  applied: "Aktif",
  saved: "Tersimpan",
  succeeded: "Selesai",
  rejected: "Ditolak",
  cancelled: "Dibatalkan",
  paused: "Dijeda",
  offline: "Tidak terhubung",
  online: "Terhubung",
  shadow: "Shadow",
  live: "Live",
  unconfigured: "Belum diatur",
  not_configured: "Belum diatur",
  connected: "Terhubung",
  disconnected: "Terputus",
};
export const label = (v: unknown) =>
  labels[String(v)] || String(v ?? "Belum tersedia").replaceAll("_", " ");
export const num = (v: unknown) =>
  typeof v === "number" && Number.isFinite(v)
    ? new Intl.NumberFormat("id-ID").format(v)
    : "—";
export const when = (v: unknown) => {
  if (!v) return "Belum tercatat";
  const d = new Date(
    typeof v === "number" ? v * (v < 1e12 ? 1000 : 1) : String(v),
  );
  return Number.isNaN(d.getTime())
    ? String(v)
    : new Intl.DateTimeFormat("id-ID", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Jakarta",
      }).format(d) + " WIB";
};
export const bytes = (v: unknown) =>
  typeof v !== "number"
    ? "Belum tersedia"
    : `${(v / 1024 ** 3).toLocaleString("id-ID", { maximumFractionDigits: 1 })} GB`;
export const list = (v: unknown): Row[] => (Array.isArray(v) ? v : []);
export const safeHref = (v: unknown) => {
  try {
    const u = new URL(String(v));
    return ["https:", "http:"].includes(u.protocol) ? u.href : undefined;
  } catch {
    return undefined;
  }
};
export const progressValue = (done: unknown, total: unknown) =>
  typeof done === "number" && typeof total === "number" && total > 0
    ? Math.max(0, Math.min(100, (done / total) * 100))
    : null;
export const getPath = (obj: Row, path: string): any =>
  path.split(".").reduce((v, k) => v?.[k], obj);
export const setPath = (obj: Row, path: string, value: unknown): Row => {
  const next = structuredClone(obj);
  const keys = path.split(".");
  let cursor = next;
  keys.slice(0, -1).forEach((k) => {
    cursor[k] ??= {};
    cursor = cursor[k];
  });
  cursor[keys.at(-1)!] = value;
  return next;
};
export const stateTone = (state: unknown) =>
  /failed|error|rejected/.test(String(state))
    ? "danger"
    : /held|unknown|wait|paused|offline|unconfigured/.test(String(state))
      ? "warning"
      : /published|complete|applied|succeeded|connected|online|ready/.test(
            String(state),
          )
        ? "success"
        : "neutral";
