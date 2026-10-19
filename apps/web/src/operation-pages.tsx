import { useState, type FormEvent } from "react";
import { put } from "./api";
import {
  ActionButton,
  Badge,
  BarChart,
  DataTable,
  Empty,
  EntityActions,
  Panel,
  Progress,
  Resource,
  useResource,
} from "./components";
import { ConfigEditor, CredentialForm } from "./configuration";
import { EventList, type Navigate } from "./content-pages";
import { Icon } from "./icons";
import {
  bytes,
  label,
  list,
  num,
  safeHref,
  when,
  type Row,
  type Session,
} from "./model";
export function Accounts({
  revision,
  refresh,
  quota = false,
}: {
  revision: number;
  refresh: () => void;
  quota?: boolean;
}) {
  const r = useResource("/accounts", revision);
  return (
    <>
      <div className="toolbar">
        <span className="muted">Snapshot {when(r.data?.snapshot_at)}</span>
        <ActionButton kind="sync_accounts" onDone={refresh}>
          <Icon name="rotate" size={17} />
          Sinkronkan akun
        </ActionButton>
      </div>
      <Panel
        title={quota ? "Pemakaian kuota akun" : "Akun terhubung"}
        note="Snapshot lengkap dan kepemilikan akun diperlukan sebelum akun masuk rotasi."
      >
        <Resource {...r}>
          <DataTable
            rows={list(r.data?.items)}
            empty="Belum ada akun tersinkron"
            columns={[
              {
                key: "name",
                label: "Akun",
                render: (r) => (
                  <div className="account-cell">
                    <span className={`account-avatar ${r.platform}`}>
                      {String(r.name || r.username || "?").slice(0, 2)}
                    </span>
                    <span>
                      <strong>{r.name || r.username || r.id}</strong>
                      <small>{label(r.platform)}</small>
                    </span>
                  </div>
                ),
              },
              {
                key: "connected",
                label: "Koneksi",
                render: (r) => (
                  <Badge state={r.connected ? "connected" : "disconnected"} />
                ),
              },
              {
                key: "enabled",
                label: quota ? "Kuota hari penjadwalan" : "Rotasi",
                render: (r) =>
                  quota ? (
                    <div className="quota-cell">
                      <Progress
                        done={
                          (r.quota_used ?? 0) +
                          (r.quota_reserved ?? r.reserved ?? 0)
                        }
                        total={r.quota_limit}
                        label="Kuota terpakai dan dipesan"
                      />
                      <small>{r.quota_day || "Tanggal belum tercatat"}</small>
                      <small>
                        {num(r.quota_used)} terpakai ·{" "}
                        {num(r.quota_reserved ?? r.reserved ?? 0)} dipesan ·
                        batas {num(r.quota_limit)}
                      </small>
                    </div>
                  ) : (
                    <span>
                      {r.rotation_eligible ? "Siap ikut rotasi" : "Belum siap"}
                      {!r.rotation_eligible &&
                        list(r.readiness_reasons).length > 0 && (
                          <small className="readiness-note">
                            {r.readiness_reasons.join(" · ")}
                          </small>
                        )}
                    </span>
                  ),
              },
              {
                key: "capabilities",
                label: "Kemampuan",
                render: (r) =>
                  Object.entries(r.capabilities || {})
                    .filter(
                      ([k, v]) =>
                        ["post", "reply", "like"].includes(k) && v === true,
                    )
                    .map(([k]) => label(k))
                    .join(", ") || "Belum terverifikasi",
              },
              {
                key: "snapshot_at",
                label: "Diperiksa",
                render: (r) => when(r.snapshot_at),
              },
            ]}
          />
        </Resource>
      </Panel>
      {quota && (
        <ConfigEditor
          section="workflow"
          title="Batas dan jendela penjadwalan"
          revision={revision}
        />
      )}
      <div className="notice">
        <Icon name="shield" />
        <p>
          Koneksi akun dikelola melalui layanan Repliz. Sinkronisasi hanya
          membaca akun. Akun yang terhubung belum otomatis memiliki izin kirim
          pada instalasi ini.
        </p>
      </div>
    </>
  );
}
export function Deliveries({
  revision,
  navigate,
  calendar = false,
  params,
}: {
  revision: number;
  navigate: Navigate;
  calendar?: boolean;
  params: URLSearchParams;
}) {
  const [platform, setPlatform] = useState(params.get("platform") || "");
  const [state, setState] = useState(
    params.get("state") || (calendar ? "scheduled" : ""),
  );
  const [page, setPage] = useState(1);
  const r = useResource(
    `/deliveries?state=${encodeURIComponent(state)}&platform=${encodeURIComponent(platform)}&page=${page}&limit=50`,
    revision,
    true,
  );
  const rows = calendar
    ? [...list(r.data?.items)].sort(
        (a, b) => (a.scheduled_at || Infinity) - (b.scheduled_at || Infinity),
      )
    : list(r.data?.items);
  const groups = rows.reduce<Record<string, Row[]>>((g, r) => {
    const day = r.scheduled_at
      ? new Intl.DateTimeFormat("id-ID", {
          dateStyle: "full",
          timeZone: "Asia/Jakarta",
        }).format(new Date(r.scheduled_at * 1000))
      : "Belum mempunyai jadwal";
    (g[day] ??= []).push(r);
    return g;
  }, {});
  return (
    <>
      <div className="toolbar">
        <label className="compact-field">
          <span>Platform</span>
          <select
            value={platform}
            onChange={(e) => {
              setPlatform(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Semua platform</option>
            {["tiktok", "facebook", "youtube"].map((p) => (
              <option key={p} value={p}>
                {label(p)}
              </option>
            ))}
          </select>
        </label>
        <label className="compact-field">
          <span>Status</span>
          <select
            value={state}
            onChange={(e) => {
              setState(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Semua status</option>
            {[
              "pending",
              "scheduled",
              "published",
              "failed",
              "submit_unknown",
              "held",
            ].map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        </label>
        <span className="subtle-label">Waktu Asia/Jakarta</span>
      </div>
      <Resource {...r}>
        {calendar ? (
          <Panel
            title="Agenda publikasi"
            note="Jadwal ini berasal dari catatan delivery. Perubahan jendela berlaku untuk jadwal berikutnya."
          >
            {rows.length ? (
              Object.entries(groups).map(([day, items]) => (
                <div className="agenda-day" key={day}>
                  <h3>
                    <Icon name="calendar" size={18} />
                    {day}
                  </h3>
                  {items.map((d) => (
                    <button
                      className="agenda-item"
                      key={d.id}
                      onClick={() => navigate("detail", { id: d.asset_id })}
                    >
                      <span>{when(d.scheduled_at)}</span>
                      <strong>{label(d.platform)}</strong>
                      <Badge state={d.state} />
                      <Icon name="arrow" size={16} />
                    </button>
                  ))}
                </div>
              ))
            ) : (
              <Empty title="Belum ada jadwal sesuai filter" icon="calendar" />
            )}
          </Panel>
        ) : (
          <Panel title="Delivery tiap platform">
            <DataTable
              rows={rows}
              empty="Belum ada hasil publikasi"
              columns={[
                {
                  key: "platform",
                  label: "Platform",
                  render: (r) => (
                    <strong className="platform-name">
                      {label(r.platform)}
                    </strong>
                  ),
                },
                {
                  key: "asset_id",
                  label: "Konten",
                  render: (r) => (
                    <button
                      className="text-button"
                      onClick={() => navigate("detail", { id: r.asset_id })}
                    >
                      {String(r.asset_id).slice(0, 10)}{" "}
                      <Icon name="arrow" size={15} />
                    </button>
                  ),
                },
                {
                  key: "state",
                  label: "Status",
                  render: (r) => <Badge state={r.state} />,
                },
                {
                  key: "scheduled_at",
                  label: "Jadwal",
                  render: (r) => when(r.scheduled_at),
                },
                {
                  key: "published_at",
                  label: "Tayang terverifikasi",
                  render: (r) => when(r.published_at),
                },
                {
                  key: "post_url",
                  label: "Hasil",
                  render: (r) =>
                    safeHref(r.post_url) ? (
                      <a
                        href={safeHref(r.post_url)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Buka postingan <Icon name="external" size={15} />
                      </a>
                    ) : (
                      r.error || "Belum ada tautan terverifikasi"
                    ),
                },
              ]}
            />
          </Panel>
        )}
        <div className="pagination">
          <button
            className="button secondary"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Sebelumnya
          </button>
          <span>
            Halaman {page} · {num(r.data?.total ?? 0)} delivery
          </span>
          <button
            className="button secondary"
            disabled={page * 50 >= (r.data?.total ?? 0)}
            onClick={() => setPage((p) => p + 1)}
          >
            Berikutnya
          </button>
        </div>
      </Resource>
      {calendar && (
        <ConfigEditor
          section="workflow"
          title="Atur jadwal berikutnya"
          revision={revision}
        />
      )}
    </>
  );
}
export function Personas({
  revision,
  refresh,
}: {
  revision: number;
  refresh: () => void;
}) {
  const r = useResource("/personas", revision);
  const accounts = useResource("/accounts", revision);
  const [accountId, setAccountId] = useState("");
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [style, setStyle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const x = await put(`/personas/${id || crypto.randomUUID()}`, {
        name,
        style,
        account_id: accountId || null,
      });
      setMessage(
        `Persona disimpan pada versi ${x.version ?? x.persona?.version ?? 1}.`,
      );
      setId("");
      setName("");
      setStyle("");
      setAccountId("");
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="two-columns">
      <Panel title="Persona tersimpan">
        <Resource {...r}>
          {list(r.data?.items).length ? (
            <div className="persona-list">
              {list(r.data?.items).map((p) => (
                <article key={p.id}>
                  <div>
                    <h3>{p.name}</h3>
                    <span className="subtle-label">Versi {p.version}</span>
                  </div>
                  <p>{p.style}</p>
                  {list(p.bindings).length > 0 && (
                    <p className="subtle-label">
                      Terhubung ke {p.bindings.length} akun
                    </p>
                  )}
                  <button
                    className="text-button"
                    onClick={() => {
                      setId(p.id);
                      setName(p.name);
                      setStyle(p.style);
                      setMessage("");
                    }}
                  >
                    Buat versi perubahan <Icon name="pen" size={15} />
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <Empty title="Belum ada persona" icon="pen">
              Buat gaya bahasa yang sesuai karakter akun. Fakta video dan kredit
              sumber tetap dijaga.
            </Empty>
          )}
        </Resource>
      </Panel>
      <Panel title={id ? "Ubah persona sebagai versi baru" : "Buat persona"}>
        <form className="padded-form" onSubmit={(e) => void save(e)}>
          <label className="field">
            <span>Nama persona</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={120}
            />
          </label>
          <label className="field">
            <span>Gaya bahasa</span>
            <textarea
              rows={7}
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              required
              maxLength={4000}
              placeholder="Contoh: santai, kalimat singkat, tetap tenang untuk konten serius."
            />
            <small>
              Persona mengatur gaya tulisan. Jangan meminta model mengarang
              pengalaman atau fakta.
            </small>
          </label>
          <label className="field">
            <span>Terapkan ke akun</span>
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
            >
              <option value="">Simpan tanpa menghubungkan akun</option>
              {list(accounts.data?.items).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name || a.username} · {a.platform}
                </option>
              ))}
            </select>
            <small>
              Caption pekerjaan yang sudah dikunci tetap memakai versi
              sebelumnya.
            </small>
          </label>
          <div className="actions">
            {id && (
              <button
                type="button"
                className="button secondary"
                onClick={() => {
                  setId("");
                  setName("");
                  setStyle("");
                }}
              >
                Batal mengubah
              </button>
            )}
            <button className="button" disabled={busy}>
              Simpan persona
            </button>
          </div>
          {message && (
            <p className="notice success" role="status">
              {message}
            </p>
          )}
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
        </form>
      </Panel>
    </div>
  );
}
export function Comments({
  revision,
  refresh,
}: {
  revision: number;
  refresh: () => void;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const r = useResource(
    `/comments?q=${encodeURIComponent(query)}&page=${page}&limit=50`,
    revision,
  );
  const rows = list(r.data?.items);
  return (
    <>
      <div className="toolbar">
        <label className="search-field">
          <Icon name="search" size={18} />
          <input
            aria-label="Cari komentar"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Cari komentar atau balasan…"
          />
        </label>
        <ActionButton kind="pause_reply" secondary onDone={refresh}>
          Jeda balasan
        </ActionButton>
      </div>
      <Panel title="Percakapan">
        <Resource {...r}>
          {rows.length ? (
            <div className="comment-list">
              {rows.map((c) => (
                <article key={c.id}>
                  <div className="comment-meta">
                    <strong>{c.author || "Pengguna"}</strong>
                    <span>{when(c.created_at)}</span>
                    <Badge state={c.state} />
                  </div>
                  <p>{c.text}</p>
                  {c.reply && (
                    <blockquote>
                      <small>Balasan worker</small>
                      <p>{c.reply}</p>
                    </blockquote>
                  )}
                  <EntityActions row={c} onDone={refresh} />
                </article>
              ))}
            </div>
          ) : (
            <Empty title="Belum ada komentar sesuai filter" icon="message" />
          )}
          <div className="pagination">
            <button
              className="button secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Sebelumnya
            </button>
            <span>
              Halaman {page} · {num(r.data?.total ?? 0)} komentar
            </span>
            <button
              className="button secondary"
              disabled={page * 50 >= (r.data?.total ?? 0)}
              onClick={() => setPage((p) => p + 1)}
            >
              Berikutnya
            </button>
          </div>
        </Resource>
      </Panel>
      <ConfigEditor
        section="reply"
        title="Pengaturan balasan"
        revision={revision}
      />
    </>
  );
}
export function Reports({ revision }: { revision: number }) {
  const r = useResource("/reports", revision);
  const metrics = list(r.data?.metrics?.durations);
  const [account, setAccount] = useState("");
  const rows = list(r.data?.items).filter(
    (m) => !account || m.account_id === account,
  );
  return (
    <>
      <div className="toolbar">
        <label className="compact-field">
          <span>Akun</span>
          <select value={account} onChange={(e) => setAccount(e.target.value)}>
            <option value="">Semua akun</option>
            {[...new Set(list(r.data?.items).map((m) => m.account_id))].map(
              (id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ),
            )}
          </select>
        </label>
        <span className="subtle-label">Maksimal 500 sampel terbaru</span>
      </div>
      <Panel
        title="Data statistik akun"
        note="Snapshot dicatat pada waktu pengambilan. Data yang tidak tersedia tidak dianggap nol."
      >
        <Resource {...r}>
          <DataTable
            rows={rows}
            empty="Belum ada snapshot laporan"
            columns={[
              { key: "account_id", label: "Akun" },
              { key: "kind", label: "Metrik", render: (r) => label(r.kind) },
              { key: "value", label: "Nilai", render: (r) => num(r.value) },
              {
                key: "sampled_at",
                label: "Waktu sampel",
                render: (r) => when(r.sampled_at),
              },
            ]}
          />
          {r.data?.quality && (
            <p className="data-footnote">
              Kualitas data:{" "}
              {typeof r.data.quality === "string"
                ? r.data.quality
                : JSON.stringify(r.data.quality)}
            </p>
          )}
        </Resource>
      </Panel>
      {metrics.length > 0 && (
        <Panel
          title="Durasi rata-rata tahap selesai"
          note="Sampel proses 7 hari terakhir. Rata-rata bukan estimasi sisa waktu."
        >
          <BarChart
            rows={metrics.map((m) => ({
              ...m,
              label: m.stage,
              value: Number(m.seconds.toFixed(1)),
            }))}
            title="Durasi tahap"
            unit="detik"
          />
          <DataTable
            rows={metrics}
            columns={[
              { key: "stage", label: "Tahap", render: (r) => label(r.stage) },
              {
                key: "samples",
                label: "Jumlah sampel",
                render: (r) => num(r.samples),
              },
            ]}
          />
        </Panel>
      )}
      <ConfigEditor
        section="reports"
        title="Pengumpulan laporan"
        revision={revision}
      />
    </>
  );
}
export function Connections({
  revision,
  refresh,
  navigate,
}: {
  revision: number;
  refresh: () => void;
  navigate: Navigate;
}) {
  const r = useResource("/configuration", revision);
  return (
    <Resource {...r}>
      <div className="connection-grid">
        {[
          {
            id: "repliz",
            name: "Repliz",
            note: "Akun, penjadwalan, dan pemeriksaan hasil publikasi.",
            icon: "rotate",
          },
          {
            id: "ai",
            name: "AI",
            note: "Analisis konteks dan penyusunan metadata video.",
            icon: "pen",
          },
          {
            id: "drive",
            name: "Google Drive",
            note: "Akses baca untuk identitas, ukuran, dan checksum file.",
            icon: "drive",
          },
        ].map((p) => (
          <Panel
            key={p.id}
            title={p.name}
            note={p.note}
            action={
              <Badge
                state={
                  r.data?.credentials?.[p.id]?.configured
                    ? "saved"
                    : "unconfigured"
                }
              >
                {r.data?.credentials?.[p.id]?.configured
                  ? "Tersimpan"
                  : "Belum diisi"}
              </Badge>
            }
          >
            <CredentialForm provider={p.id} onSaved={refresh} />
            {p.id === "drive" && (
              <button
                className="text-button connection-link"
                onClick={() => navigate("storage")}
              >
                Atur pasangan folder bank & Drive{" "}
                <Icon name="arrow" size={16} />
              </button>
            )}
          </Panel>
        ))}
      </div>
      <Panel title="Versi konfigurasi koneksi">
        <div className="control-body">
          <p>
            Kredensial yang tersimpan memiliki versi sendiri. Worker memakainya
            setelah konfigurasi diterapkan.
          </p>
          <ActionButton
            kind="apply_configuration"
            payload={{ version: r.data?.desired_version }}
            onDone={refresh}
          >
            Terapkan versi {r.data?.desired_version}
          </ActionButton>
        </div>
      </Panel>
    </Resource>
  );
}
export function Telegram({
  revision,
  refresh,
}: {
  revision: number;
  refresh: () => void;
}) {
  const events = useResource("/events?limit=100", revision);
  const notifications = list(events.data?.items).filter((e) =>
    /telegram|notification|outbox/.test(e.kind),
  );
  return (
    <>
      <div className="two-columns">
        <Panel
          title="Kredensial bot"
          note="Token bot berbeda dari password login panel."
        >
          <CredentialForm provider="telegram" onSaved={refresh} />
        </Panel>
        <ConfigEditor
          section="telegram"
          title="Penerimaan & notifikasi"
          revision={revision}
        />
      </div>
      <Panel title="Aktivitas Telegram">
        <Resource {...events}>
          <EventList rows={notifications} />
        </Resource>
      </Panel>
    </>
  );
}
export function Storage({
  revision,
  refresh,
}: {
  revision: number;
  refresh: () => void;
}) {
  const r = useResource("/storage", revision);
  const c = r.data?.capacity || {};
  return (
    <>
      <Panel
        title="Kapasitas mesin worker"
        note="Ukuran volume lokasi bank, bukan penyimpanan browser."
      >
        <Resource {...r}>
          <div className="capacity">
            <div>
              <span>Terpakai</span>
              <strong>{bytes(c.used)}</strong>
            </div>
            <div className="capacity-bar">
              <Progress
                done={c.used}
                total={c.total}
                label="Kapasitas penyimpanan"
              />
              <span>
                {bytes(c.free)} bebas dari {bytes(c.total)}
              </span>
            </div>
            <Icon name="drive" size={34} />
          </div>
          {r.data?.verification && (
            <p className="data-footnote">
              Verifikasi file:{" "}
              {typeof r.data.verification === "string"
                ? label(r.data.verification)
                : `${num(r.data.verification.verified)} cocok · ${num(r.data.verification.awaiting)} belum diperiksa`}
            </p>
          )}
        </Resource>
      </Panel>
      <ConfigEditor
        section="storage"
        title="Folder bank & Google Drive"
        revision={revision}
      />
      <Panel
        title="Pembersihan file kerja"
        note="Bank konten, konteks, dan histori tetap dilindungi."
      >
        <div className="control-body">
          <p>
            Worker memeriksa seluruh tujuan tayang, retensi, serta referensi
            file sebelum menghapus file kerja yang memenuhi syarat.
          </p>
          <ActionButton kind="cleanup_plan" secondary onDone={refresh}>
            Periksa kandidat cleanup
          </ActionButton>
        </div>
      </Panel>
      <Panel title="Profil penyimpanan tercatat">
        <DataTable
          rows={list(r.data?.profiles)}
          columns={[
            { key: "version", label: "Versi" },
            { key: "bank_directory", label: "Lokasi bank" },
            { key: "folder_url", label: "Folder Drive" },
            {
              key: "active",
              label: "Kondisi",
              render: (r) =>
                r.status === "active"
                  ? "Aktif"
                  : r.status === "pending"
                    ? "Menunggu worker"
                    : "Referensi tersimpan",
            },
          ]}
        />
      </Panel>
    </>
  );
}
export function Backups({
  revision,
  refresh,
}: {
  revision: number;
  refresh: () => void;
}) {
  const r = useResource("/backups", revision);
  return (
    <>
      <div className="toolbar">
        <span className="muted">
          Backup umum tidak menyertakan nilai kredensial.
        </span>
        <ActionButton kind="backup" onDone={refresh}>
          <Icon name="archive" size={17} />
          Buat backup
        </ActionButton>
      </div>
      <Panel title="Backup instalasi">
        <Resource {...r}>
          <DataTable
            rows={list(r.data?.items)}
            empty="Belum ada backup"
            columns={[
              {
                key: "id",
                label: "Bundle",
                render: (r) => <code>{r.id || r.name}</code>,
              },
              {
                key: "created_at",
                label: "Dibuat",
                render: (r) => when(r.created_at),
              },
              {
                key: "verified",
                label: "Pemeriksaan",
                render: (r) => (
                  <Badge state={r.verified ? "ready" : r.status || "pending"} />
                ),
              },
              {
                key: "files",
                label: "Jumlah file",
                render: (r) => num(r.files ?? r.file_count),
              },
              { key: "size", label: "Ukuran", render: (r) => bytes(r.size) },
            ]}
          />
        </Resource>
      </Panel>
      <Panel title="Pemulihan di mesin worker">
        <div className="explanation">
          <p>
            Restore dijalankan melalui CLI saat API dan worker berhenti. Gunakan
            direktori tujuan terpisah agar data aktif tidak tertimpa.
          </p>
          <code className="code-block">python -m arker restore --help</code>
          <p>
            Setelah pemulihan, periksa dengan doctor dan pastikan mode shadow
            sebelum menjalankan worker. Kredensial harus dikonfigurasi kembali
            secara privat.
          </p>
        </div>
      </Panel>
    </>
  );
}
export function Activity({ revision }: { revision: number }) {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(100);
  const [before, setBefore] = useState<number | null>(null);
  const r = useResource(
    `/events?limit=${limit}${before ? `&before=${before}` : ""}`,
    revision,
    true,
  );
  const rows = list(r.data?.items).filter((e) =>
    `${e.kind} ${e.entity_id}`.toLowerCase().includes(query.toLowerCase()),
  );
  function exportData() {
    const blob = new Blob([JSON.stringify(rows, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "arker-activity.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <>
      <div className="toolbar">
        <label className="search-field">
          <Icon name="search" size={18} />
          <input
            aria-label="Cari aktivitas"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Cari peristiwa atau ID…"
          />
        </label>
        <label className="compact-field">
          <span>Jumlah</span>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          >
            <option>100</option>
            <option>250</option>
            <option>500</option>
          </select>
        </label>
        <button
          className="button secondary"
          onClick={exportData}
          disabled={!rows.length}
        >
          <Icon name="download" size={16} />
          Ekspor hasil filter
        </button>
      </div>
      <Panel
        title="Jejak aktivitas"
        note="Rincian berasal dari API yang menyaring informasi rahasia."
      >
        <Resource {...r}>
          <EventList rows={rows} />
          <div className="pagination">
            <button
              className="button secondary"
              disabled={!before}
              onClick={() => setBefore(null)}
            >
              Aktivitas terbaru
            </button>
            <button
              className="button secondary"
              disabled={!r.data?.next_before}
              onClick={() => setBefore(r.data?.next_before)}
            >
              Aktivitas lebih lama
            </button>
          </div>
        </Resource>
      </Panel>
    </>
  );
}
export function Settings({
  session,
  revision,
  refresh,
  onLogout,
}: {
  session: Session;
  revision: number;
  refresh: () => void;
  onLogout: () => void;
}) {
  const r = useResource("/configuration", revision, true);
  return (
    <>
      <div className="two-columns">
        <Panel title="Sesi admin">
          <dl className="facts vertical">
            <div>
              <dt>Email</dt>
              <dd>{session.user?.email}</dd>
            </div>
            <div>
              <dt>Akses</dt>
              <dd>Administrator instalasi</dd>
            </div>
            <div>
              <dt>Autentikasi</dt>
              <dd>Cookie sesi privat · pemeriksaan CSRF</dd>
            </div>
          </dl>
          <div className="panel-bottom">
            <button className="button secondary" onClick={onLogout}>
              <Icon name="logout" size={16} />
              Keluar dari sesi ini
            </button>
          </div>
        </Panel>
        <Panel title="Konfigurasi worker">
          <Resource {...r}>
            <dl className="facts vertical">
              <div>
                <dt>Mode</dt>
                <dd>
                  <Badge state={r.data?.config?.application?.mode} />
                </dd>
              </div>
              <div>
                <dt>Publikasi</dt>
                <dd>
                  {r.data?.config?.application?.publish_enabled
                    ? "Diaktifkan"
                    : "Nonaktif"}
                </dd>
              </div>
              <div>
                <dt>Versi tersimpan / aktif</dt>
                <dd>
                  v{r.data?.desired_version} / v{r.data?.applied_version}
                </dd>
              </div>
            </dl>
            <div className="panel-bottom">
              <ActionButton
                kind="apply_configuration"
                payload={{ version: r.data?.desired_version }}
                onDone={refresh}
              >
                Terapkan konfigurasi tersimpan
              </ActionButton>
            </div>
          </Resource>
        </Panel>
      </div>
      <ConfigEditor
        section="general"
        title="Batas penerimaan konten"
        revision={revision}
      />
      <Panel title="Aktivasi publikasi">
        <div className="explanation">
          <p>
            Instalasi dimulai dalam mode shadow. Aktivasi live memerlukan
            kepemilikan akun eksklusif, kredensial, dan penyimpanan
            terverifikasi. Tidak ada tombol publikasi pada tahap pengujian ini.
          </p>
          <p>
            Pengaturan tema dan animasi tersedia pada tombol di bagian atas
            panel dan disimpan untuk browser ini.
          </p>
        </div>
      </Panel>
    </>
  );
}
