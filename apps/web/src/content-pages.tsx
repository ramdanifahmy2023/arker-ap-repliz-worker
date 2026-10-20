import { useState, type FormEvent } from "react";
import { post } from "./api";
import {
  ActionButton,
  Badge,
  BarChart,
  DataTable,
  EntityActions,
  Panel,
  Progress,
  Resource,
  TrendChart,
  useResource,
} from "./components";
import { Icon } from "./icons";
import { ServiceControls } from "./service-controls";
import { label, list, num, safeHref, when, type Row } from "./model";
export type Navigate = (page: string, params?: Record<string, string>) => void;
export function AssetList({
  rows,
  navigate,
}: {
  rows: Row[];
  navigate: Navigate;
}) {
  return (
    <DataTable
      rows={rows}
      empty="Belum ada konten"
      columns={[
        {
          key: "source",
          label: "Konten",
          render: (r) => (
            <button
              className="text-button asset-title"
              onClick={() => navigate("detail", { id: r.id })}
            >
              <span className="mini-media">
                <Icon name="film" />
              </span>
              <span>
                <strong>
                  {r.hook ||
                    (r.source_username && `@${r.source_username}`) ||
                    `Konten ${String(r.id).slice(0, 8)}`}
                </strong>
                <small>{r.source_url}</small>
              </span>
            </button>
          ),
        },
        {
          key: "stage",
          label: "Tahap",
          render: (r) => <Badge state={r.stage || r.state} />,
        },
        {
          key: "progress",
          label: "Progres",
          render: (r) => (
            <div className="table-progress">
              <Progress
                done={r.progress}
                total={r.total}
                label="Progres tahap"
                active={r.state === "processing"}
              />
              <small>
                {r.total
                  ? `${num(r.progress)} / ${num(r.total)}${r.stage === "render" ? " detik video" : " unit"}`
                  : "Menunggu ukuran proses"}
              </small>
            </div>
          ),
        },
        {
          key: "updated_at",
          label: "Diperbarui",
          render: (r) => when(r.updated_at),
        },
      ]}
    />
  );
}
export function Overview({
  navigate,
  revision,
}: {
  navigate: Navigate;
  revision: number;
}) {
  const r = useResource("/overview", revision, true);
  const d = r.data || {};
  const s = d.summary || {};
  const charts = d.charts || {};
  return (
    <Resource {...r}>
      <div className="overview-top">
        <div className="worker-strip">
          <span
            className={`connection-dot ${d.health?.connected ? "connected" : ""}`}
          />
          <strong>
            {d.health?.connected
              ? "Worker terhubung"
              : "Worker belum terhubung"}
          </strong>
          <span>Heartbeat {when(d.health?.heartbeat_at)}</span>
          <button className="text-button" onClick={() => navigate("worker")}>
            Buka kendali <Icon name="arrow" size={16} />
          </button>
        </div>
      </div>
      <div className="metrics">
        {[
          {
            title: "Aset masuk",
            value: s.assets_total,
            unit: "sumber konten",
            page: "queue",
            icon: "folder",
          },
          {
            title: "Tayang terverifikasi",
            value: s.deliveries_published,
            unit: "delivery, semua platform",
            page: "published",
            icon: "send",
          },
          {
            title: "Di alur kerja",
            value: s.assets_active,
            unit: "aset dalam alur",
            page: "queue",
            icon: "rotate",
          },
          {
            title: "Perlu perhatian",
            value: s.attention_count,
            unit: "pekerjaan ditahan / gagal",
            page: "attention",
            icon: "alert",
          },
        ].map((m) => (
          <button
            className={`metric ${m.page === "attention" ? "attention-metric" : ""}`}
            key={m.title}
            onClick={() =>
              navigate(
                m.page,
                m.title === "Di alur kerja"
                  ? { scope: "active" }
                  : m.page === "published"
                    ? { state: "published" }
                    : undefined,
              )
            }
          >
            <span>
              {m.title}
              <Icon name={m.icon} size={18} />
            </span>
            <strong>{num(m.value)}</strong>
            <small>
              {m.unit}
              <Icon name="arrow" size={15} />
            </small>
          </button>
        ))}
      </div>
      <div className="analysis-grid">
        <Panel
          title="Aktivitas konten"
          note="Jumlah per hari · Asia/Jakarta"
          action={<span className="subtle-label">7 hari terakhir</span>}
        >
          <TrendChart
            rows={list(charts.throughput)}
            onSelect={(point) =>
              navigate("queue", { date: String(point.date) })
            }
          />
        </Panel>
        <Panel
          title="Antrean per tahap"
          note="Aset menunggu atau sedang diproses"
        >
          <BarChart
            title="Aset per tahap"
            rows={list(charts.stages)}
            onSelect={(point) =>
              navigate("queue", { stage: String(point.stage), scope: "active" })
            }
          />
        </Panel>
      </div>
      <div className="analysis-grid lower-grid">
        <Panel
          title="Konten dalam proses"
          note="Klik konten untuk mengikuti ketiga tujuannya."
          action={
            <button className="text-button" onClick={() => navigate("queue")}>
              Semua antrean <Icon name="arrow" size={16} />
            </button>
          }
        >
          <AssetList
            rows={list(d.active_assets).slice(0, 5)}
            navigate={navigate}
          />
        </Panel>
        <Panel
          title="Perlu perhatian"
          action={<span className="count">{num(s.attention_count)}</span>}
        >
          {list(d.attention).length ? (
            <div className="attention-list">
              {list(d.attention)
                .slice(0, 4)
                .map((a, i) => (
                  <button key={a.id || i} onClick={() => navigate("attention")}>
                    <Icon name="alert" size={18} />
                    <span>
                      <strong>{label(a.state)}</strong>
                      <small>
                        {a.error ||
                          a.reason ||
                          "Buka rincian untuk melihat tindakan yang tersedia."}
                      </small>
                    </span>
                    <Icon name="chevron" size={16} />
                  </button>
                ))}
            </div>
          ) : (
            <div className="quiet-state">
              <span>
                <Icon name="check" size={24} />
              </span>
              <h3>Tidak ada kendala tercatat</h3>
              <p>
                Status ini mengikuti pekerjaan yang sudah tercatat di instalasi
                ini.
              </p>
            </div>
          )}
        </Panel>
      </div>
      <Panel
        title="Hasil tiap platform"
        note="Satuan delivery. Jadwal diterima tetap dipisahkan dari hasil tayang."
      >
        <DataTable
          rows={list(charts.platforms)}
          columns={[
            {
              key: "platform",
              label: "Platform",
              render: (r) => (
                <span className="platform-name">{label(r.platform)}</span>
              ),
            },
            {
              key: "published",
              label: "Tayang terverifikasi",
              render: (r) => num(r.published),
            },
            {
              key: "scheduled",
              label: "Terjadwal",
              render: (r) => num(r.scheduled),
            },
            { key: "failed", label: "Gagal", render: (r) => num(r.failed) },
            {
              key: "unknown",
              label: "Belum diketahui",
              render: (r) => num(r.unknown),
            },
          ]}
        />
      </Panel>
      <p className="data-footnote">
        Sumber: catatan instalasi Arker · Diperbarui {when(d.generated_at)} ·
        Aset dan delivery memakai satuan berbeda.
      </p>
    </Resource>
  );
}
const pipeline = [
  ["queued", "Link diterima", "Validasi & deduplikasi"],
  ["download", "Unduh sumber", "Satu sumber, satu aset"],
  ["inspect", "Periksa media", "Frame, transkrip, dan pemilik sumber"],
  ["draft", "Analisis & hook", "Susun fakta, hook, dan caption"],
  ["render", "Render video", "Profil video bersama"],
  ["drive", "Bank & Drive", "Ukuran dan checksum cocok"],
  ["delivery", "Siap dijadwalkan", "Rotasi akun dan reservasi kuota"],
];
export function Flow({
  navigate,
  revision,
}: {
  navigate: Navigate;
  revision: number;
}) {
  const r = useResource("/overview", revision, true);
  const rows = list(r.data?.charts?.stages);
  return (
    <Resource {...r}>
      <Panel
        title="Perjalanan satu konten"
        note="Angka menunjukkan aset pada tahap tersebut. Klik tahap untuk membuka antrean."
      >
        <div className="flow-map">
          {pipeline.map(([stage, title, note], i) => {
            const count = rows.find((v) => v.stage === stage)?.count ?? 0;
            return (
              <button
                key={stage}
                className={`flow-step ${count ? "has-work" : ""}`}
                onClick={() => navigate("queue", { stage, scope: "active" })}
              >
                <span className="step-number">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span>
                  <strong>{title}</strong>
                  <small>{note}</small>
                </span>
                <b>
                  {num(count)}
                  <small>aset</small>
                </b>
                <Icon name="arrow" size={18} />
              </button>
            );
          })}
          <div className="flow-branch">
            <span>Satu aset bercabang menjadi tiga tujuan wajib</span>
            <div>
              {["TikTok", "Facebook Page", "YouTube Shorts"].map((p) => (
                <button
                  key={p}
                  onClick={() =>
                    navigate("published", {
                      platform:
                        p === "TikTok"
                          ? "tiktok"
                          : p === "Facebook Page"
                            ? "facebook"
                            : "youtube",
                    })
                  }
                >
                  <Icon name="send" />
                  <strong>{p}</strong>
                  <small>Jadwal → verifikasi tayang</small>
                </button>
              ))}
            </div>
          </div>
        </div>
      </Panel>
      <div className="two-columns">
        <Panel title="Sesudah tayang">
          <div className="explanation">
            <p>
              Balasan komentar memakai konteks video dan percakapan. Setiap
              tujuan menyimpan bukti hasilnya sendiri.
            </p>
            <button
              className="button secondary"
              onClick={() => navigate("comments")}
            >
              Buka komentar <Icon name="arrow" size={16} />
            </button>
          </div>
        </Panel>
        <Panel title="File kerja dan arsip">
          <div className="explanation">
            <p>
              Cleanup menunggu seluruh tujuan terverifikasi dan retensi minimum.
              Bank, konteks, serta histori tetap disimpan.
            </p>
            <button
              className="button secondary"
              onClick={() => navigate("storage")}
            >
              Lihat penyimpanan <Icon name="arrow" size={16} />
            </button>
          </div>
        </Panel>
      </div>
    </Resource>
  );
}
export function WorkerPage({
  revision,
  refresh,
}: {
  revision: number;
  refresh: () => void;
}) {
  const r = useResource("/health", revision, true);
  const d = r.data || {};
  return (
    <Resource {...r}>
      {d.restore_requires_reconciliation && (
        <div className="notice warning" role="status">
          <Icon name="shield" />
          <p>
            Instalasi hasil pemulihan sedang ditahan. Rekonsiliasi bukti
            pengiriman dan kepemilikan akun melalui CLI sebelum melanjutkan
            pemrosesan atau balasan.
          </p>
        </div>
      )}
      <ServiceControls revision={revision} />
      <Panel
        title="Kondisi mesin"
        action={<Badge state={d.connected ? "connected" : "offline"} />}
      >
        <dl className="facts">
          <div>
            <dt>Status</dt>
            <dd>{label(d.state)}</dd>
          </div>
          <div>
            <dt>Heartbeat terakhir</dt>
            <dd>{when(d.heartbeat_at)}</dd>
          </div>
          <div>
            <dt>Usia heartbeat</dt>
            <dd>
              {d.age_seconds === null || d.age_seconds === undefined
                ? "Belum ada"
                : `${Math.round(d.age_seconds)} detik`}
            </dd>
          </div>
          <div>
            <dt>Konfigurasi aktif</dt>
            <dd>Versi {d.applied_version ?? 0}</dd>
          </div>
        </dl>
      </Panel>
      <div className="two-columns">
        <Panel
          title="Pemrosesan video"
          note="Jeda tidak membatalkan jadwal yang sudah diterima provider."
        >
          <div className="control-body">
            <p>
              Perintah dicatat dulu, kemudian worker mengonfirmasi pada batas
              operasi yang aman.
            </p>
            <div className="actions">
              <ActionButton kind="pause_processing" secondary onDone={refresh}>
                <Icon name="pause" size={17} />
                Jeda pemrosesan
              </ActionButton>
              <ActionButton kind="resume_processing" onDone={refresh}>
                <Icon name="play" size={17} />
                Lanjutkan
              </ActionButton>
            </div>
          </div>
        </Panel>
        <Panel
          title="Balasan komentar"
          note="Kontrol terpisah dari pemrosesan video."
        >
          <div className="control-body">
            <p>
              Perubahan ini tidak mengirim ulang balasan yang sudah tercatat.
            </p>
            <div className="actions">
              <ActionButton kind="pause_reply" secondary onDone={refresh}>
                Jeda balasan
              </ActionButton>
              <ActionButton kind="resume_reply" onDone={refresh}>
                Lanjutkan balasan
              </ActionButton>
            </div>
          </div>
        </Panel>
      </div>
      <Panel title="Komponen worker">
        <DataTable
          rows={
            Array.isArray(d.components)
              ? d.components
              : Object.entries(d.components || {}).map(([name, value]) => ({
                  name,
                  ...(typeof value === "object"
                    ? (value as Row)
                    : { state: value }),
                }))
          }
          columns={[
            { key: "name", label: "Komponen" },
            {
              key: "state",
              label: "Kondisi",
              render: (r) => <Badge state={r.state || r.status} />,
            },
            {
              key: "message",
              label: "Keterangan",
              render: (r) =>
                r.message || r.detail || "Tidak ada keterangan tambahan",
            },
          ]}
        />
      </Panel>
      <div className="notice">
        <Icon name="worker" />
        <p>
          Jika proses worker berhenti, jalankan kembali layanan Arker pada mesin
          worker. Menutup panel tidak menghentikan proses yang berjalan
          terpisah.
        </p>
      </div>
    </Resource>
  );
}
export function Attention({
  revision,
  refresh,
  navigate,
}: {
  revision: number;
  refresh: () => void;
  navigate: Navigate;
}) {
  const r = useResource("/overview", revision, true);
  return (
    <Resource {...r}>
      <div className="notice warning">
        <Icon name="shield" />
        <p>
          Hasil yang belum diketahui diperiksa terlebih dahulu. Tombol pemulihan
          hanya muncul jika layanan menyatakan tindakan tersebut aman.
        </p>
      </div>
      <Panel title="Pekerjaan yang membutuhkan tindakan">
        <DataTable
          rows={list(r.data?.attention)}
          empty="Tidak ada pekerjaan yang perlu perhatian"
          columns={[
            {
              key: "state",
              label: "Status",
              render: (r) => <Badge state={r.state} />,
            },
            {
              key: "error",
              label: "Penyebab",
              render: (r) => r.error || r.reason || "Buka detail pekerjaan.",
            },
            {
              key: "updated_at",
              label: "Diperbarui",
              render: (r) => when(r.updated_at),
            },
            {
              key: "actions",
              label: "Tindakan",
              render: (r) => (
                <>
                  <EntityActions row={r} onDone={refresh} />
                  {(r.asset_id || r.entity_type === "asset") && (
                    <button
                      className="text-button"
                      onClick={() =>
                        navigate("detail", { id: r.asset_id || r.id })
                      }
                    >
                      Buka konten
                    </button>
                  )}
                </>
              ),
            },
          ]}
        />
      </Panel>
    </Resource>
  );
}
export function Intake({ navigate }: { navigate: Navigate }) {
  const [urls, setUrls] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Row | null>(null);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await post("/intake", {
        urls: urls
          .split(/\s+/)
          .map((v) => v.trim())
          .filter(Boolean),
      });
      setResult(r);
      if (
        r.accepted?.length ||
        (typeof r.accepted === "number" && r.accepted > 0)
      )
        setUrls("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="intake-grid">
      <Panel
        title="Masukkan link Reel"
        note="Satu link per baris. Link yang sudah diterima akan ditandai sebagai duplikat."
      >
        <form onSubmit={(e) => void submit(e)} className="padded-form">
          <label className="field">
            <span>Link sumber</span>
            <textarea
              aria-label="Link sumber"
              rows={9}
              value={urls}
              required
              onChange={(e) => setUrls(e.target.value)}
              placeholder="https://www.instagram.com/reel/..."
              spellCheck={false}
            />
            <small>
              {urls.trim() ? urls.trim().split(/\s+/).length : 0} link dalam
              formulir
            </small>
          </label>
          <button className="button" disabled={busy || !urls.trim()}>
            {busy ? <span className="loader" /> : <Icon name="plus" />}Periksa &
            masukkan antrean
          </button>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
        </form>
        {result && (
          <div className="intake-result" role="status">
            <h3>Hasil penerimaan</h3>
            <dl>
              <div>
                <dt>Diterima</dt>
                <dd>
                  {Array.isArray(result.accepted)
                    ? result.accepted.length
                    : (result.accepted ?? 0)}
                </dd>
              </div>
              <div>
                <dt>Duplikat</dt>
                <dd>
                  {Array.isArray(result.duplicates)
                    ? result.duplicates.length
                    : (result.duplicates ?? 0)}
                </dd>
              </div>
              <div>
                <dt>Ditolak</dt>
                <dd>
                  {Array.isArray(result.rejected)
                    ? result.rejected.length
                    : (result.rejected ?? 0)}
                </dd>
              </div>
            </dl>
            {list(result.rejected).map((x, i) => (
              <p key={i}>
                {x.url}: {x.reason || x.error}
              </p>
            ))}
            <button className="text-button" onClick={() => navigate("queue")}>
              Lihat antrean <Icon name="arrow" size={16} />
            </button>
          </div>
        )}
      </Panel>
      <aside className="intake-guide">
        <span className="guide-symbol">
          <Icon name="flow" size={30} />
        </span>
        <h2>
          Satu sumber.
          <br />
          Tiga tujuan.
        </h2>
        <p>
          Worker mengunduh dan mengolah video sekali. TikTok, Facebook Page, dan
          YouTube Shorts mempunyai status pengiriman terpisah.
        </p>
        <ul>
          <li>Pemilik sumber diverifikasi untuk kredit caption.</li>
          <li>Hasil yang belum pasti ditahan untuk pemeriksaan.</li>
          <li>Mode shadow memproses tanpa publikasi.</li>
        </ul>
      </aside>
    </div>
  );
}
export function Queue({
  params,
  navigate,
  revision,
  bank = false,
}: {
  params: URLSearchParams;
  navigate: Navigate;
  revision: number;
  bank?: boolean;
}) {
  const [query, setQuery] = useState(params.get("q") || "");
  const [state, setState] = useState(params.get("state") || "");
  const [page, setPage] = useState(1);
  const r = useResource(
    `/assets?q=${encodeURIComponent(query)}&state=${encodeURIComponent(state)}&stage=${encodeURIComponent(params.get("stage") || "")}&date=${encodeURIComponent(params.get("date") || "")}&scope=${encodeURIComponent(params.get("scope") || "")}&batch_id=${encodeURIComponent(params.get("batch_id") || "")}&page=${page}&limit=25`,
    revision,
  );
  const [batchPage, setBatchPage] = useState(1);
  const batches = useResource(`/batches?page=${batchPage}&limit=25`, revision);
  return (
    <>
      <div className="toolbar">
        <label className="search-field">
          <Icon name="search" size={18} />
          <input
            aria-label="Cari konten"
            placeholder="Cari link atau akun sumber…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="compact-field">
          <span>Tahap</span>
          <select
            value={state}
            onChange={(e) => {
              setState(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Semua tahap</option>
            {[
              "queued",
              "processing",
              "waiting",
              "ready",
              "preview_ready",
              "published",
              "completed",
              "failed",
              "held",
            ].map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        </label>
        {(params.get("date") ||
          params.get("stage") ||
          params.get("scope") ||
          params.get("batch_id")) && (
          <button
            className="button secondary"
            onClick={() => navigate(bank ? "bank" : "queue")}
          >
            Hapus filter{" "}
            {params.get("date") ||
              (params.get("stage")
                ? label(params.get("stage"))
                : "antrean aktif")}
          </button>
        )}
        {bank && (
          <button
            className="button secondary"
            onClick={() => navigate("storage")}
          >
            Atur folder bank
          </button>
        )}
      </div>
      <Panel
        title={bank ? "Konten dan referensi bank" : "Antrean konten"}
        note={`${num(r.data?.total ?? 0)} aset sesuai filter`}
      >
        <Resource {...r}>
          <AssetList rows={list(r.data?.items)} navigate={navigate} />
          <div className="pagination">
            <button
              className="button secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Sebelumnya
            </button>
            <span>Halaman {page}</span>
            <button
              className="button secondary"
              disabled={page * 25 >= (r.data?.total ?? 0)}
              onClick={() => setPage((p) => p + 1)}
            >
              Berikutnya
            </button>
          </div>
        </Resource>
      </Panel>
      {!bank && (
        <Panel title="Batch penerimaan">
          <Resource {...batches}>
            <DataTable
              rows={list(batches.data?.items)}
              empty="Belum ada batch"
              columns={[
                {
                  key: "id",
                  label: "Batch",
                  render: (r) => (
                    <button
                      className="text-button"
                      onClick={() => navigate("queue", { batch_id: r.id })}
                    >
                      <code>{String(r.id).slice(0, 12)}</code>
                      <Icon name="arrow" size={15} />
                    </button>
                  ),
                },
                { key: "source", label: "Sumber input" },
                {
                  key: "accepted",
                  label: "Link diterima",
                  render: (r) => num(r.accepted),
                },
                {
                  key: "completed",
                  label: "Sumber lengkap",
                  render: (r) => (
                    <div className="table-progress">
                      <Progress
                        done={r.completed}
                        total={r.accepted}
                        label="Sumber lengkap dalam batch"
                      />
                      <small>
                        {num(r.completed)} dari {num(r.accepted)} sumber
                      </small>
                    </div>
                  ),
                },
                {
                  key: "created_at",
                  label: "Waktu masuk",
                  render: (r) => when(r.created_at),
                },
              ]}
            />
            <div className="pagination">
              <button
                className="button secondary"
                disabled={batchPage <= 1}
                onClick={() => setBatchPage((p) => p - 1)}
              >
                Batch sebelumnya
              </button>
              <span>
                Halaman {batchPage} · {num(batches.data?.total ?? 0)} batch
              </span>
              <button
                className="button secondary"
                disabled={batchPage * 25 >= (batches.data?.total ?? 0)}
                onClick={() => setBatchPage((p) => p + 1)}
              >
                Batch berikutnya
              </button>
            </div>
          </Resource>
        </Panel>
      )}
    </>
  );
}
export function AssetDetail({
  id,
  navigate,
  revision,
  refresh,
}: {
  id: string | null;
  navigate: Navigate;
  revision: number;
  refresh: () => void;
}) {
  const r = useResource(
    id ? `/assets/${encodeURIComponent(id)}` : "/assets?limit=12",
    revision,
    true,
  );
  if (!id)
    return (
      <Panel title="Pilih konten untuk melihat detail">
        <Resource {...r}>
          <AssetList rows={list(r.data?.items)} navigate={navigate} />
        </Resource>
      </Panel>
    );
  const d = r.data || {},
    asset = d.asset || {},
    deliveries = list(d.deliveries),
    artifacts = list(d.artifacts);
  const video = artifacts.find((a) =>
    ["render", "rendered", "video", "final"].includes(a.kind),
  );
  return (
    <Resource {...r}>
      <div className="detail-heading">
        <div>
          <button className="text-button" onClick={() => navigate("queue")}>
            ← Kembali ke antrean
          </button>
          <h2>
            {asset.hook ||
              (asset.source_username && `Video @${asset.source_username}`) ||
              `Konten ${id.slice(0, 8)}`}
          </h2>
          <span className="muted">
            Masuk {when(asset.created_at)} · Konfigurasi v{asset.config_version}
          </span>
        </div>
        <Badge state={asset.state} />
      </div>
      <div className="detail-grid">
        <Panel className="preview-panel">
          <div className="video-preview">
            {video ? (
              <video
                controls
                preload="metadata"
                src={`/api/media/${encodeURIComponent(id)}/${encodeURIComponent(video.kind)}`}
                aria-label="Preview video hasil render"
              />
            ) : (
              <div>
                <Icon name="film" size={42} />
                <h3>Preview belum tersedia</h3>
                <p>
                  Hasil video muncul setelah render selesai dan artefak
                  tercatat.
                </p>
              </div>
            )}
          </div>
          {safeHref(asset.source_url) && (
            <a
              className="source-link"
              href={safeHref(asset.source_url)}
              target="_blank"
              rel="noreferrer"
            >
              Buka sumber asli <Icon name="external" size={16} />
            </a>
          )}
        </Panel>
        <div>
          <Panel title="Tahap sekarang" action={<Badge state={asset.stage} />}>
            <div className="stage-detail">
              <Progress
                done={asset.progress}
                total={asset.total}
                label="Progres tahap aset"
                active={asset.state === "processing"}
              />
              <p>
                {asset.total
                  ? `${num(asset.progress)} dari ${num(asset.total)} ${asset.stage === "render" ? "detik video diproses" : "unit proses"}`
                  : "Tahap ini belum mempunyai total terukur."}
              </p>
              {asset.error && (
                <div className="notice warning">{asset.error}</div>
              )}
              <EntityActions row={asset} onDone={refresh} />
            </div>
          </Panel>
          <Panel title="Metadata & konteks">
            {asset.context?.copy_origin && (
              <p className="muted">
                {asset.context.copy_origin === "ai"
                  ? "Hook dan caption disusun AI. Periksa kembali kecocokannya dengan video."
                  : asset.context.copy_origin === "source_excerpt"
                    ? "Tulisan diambil dari keterangan sumber. AI belum menyusun ulang caption."
                    : "Hook memakai teks netral karena keterangan sumber belum cukup singkat. AI belum menyusun ulang caption."}
              </p>
            )}
            <dl className="facts vertical">
              <div>
                <dt>Hook</dt>
                <dd>{asset.hook || "Belum disusun"}</dd>
              </div>
              <div>
                <dt>Caption</dt>
                <dd className="pre-wrap">{asset.caption || "Belum disusun"}</dd>
              </div>
              <div>
                <dt>Pemilik sumber</dt>
                <dd>
                  {asset.source_verified
                    ? `@${asset.source_username} · terverifikasi`
                    : "Belum terverifikasi"}
                </dd>
              </div>
            </dl>
            {asset.context && (
              <details className="context-detail">
                <summary>Lihat konteks video</summary>
                <pre>
                  {typeof asset.context === "object"
                    ? JSON.stringify(asset.context, null, 2)
                    : asset.context}
                </pre>
              </details>
            )}
          </Panel>
        </div>
      </div>
      <Panel
        title="Tiga tujuan publikasi"
        note={`${deliveries.filter((d) => ["published", "published_verified"].includes(d.state)).length} dari ${deliveries.length} tujuan terverifikasi. Ini jumlah tujuan, bukan estimasi waktu.`}
      >
        <div className="delivery-grid">
          {deliveries.map((d) => (
            <article key={d.id}>
              <span className={`platform-mark ${d.platform}`}>
                {d.platform === "tiktok"
                  ? "Tk"
                  : d.platform === "facebook"
                    ? "f"
                    : "▶"}
              </span>
              <h3>
                {d.platform === "tiktok"
                  ? "TikTok"
                  : d.platform === "facebook"
                    ? "Facebook Page"
                    : "YouTube Shorts"}
              </h3>
              <Badge state={d.state} />
              <p>
                {d.published_at
                  ? `Terverifikasi ${when(d.published_at)}`
                  : d.scheduled_at
                    ? `Jadwal ${when(d.scheduled_at)}`
                    : "Belum ada jadwal diterima"}
              </p>
              {d.error && <p className="field-error">{d.error}</p>}
              {safeHref(d.post_url) && (
                <a href={safeHref(d.post_url)} target="_blank" rel="noreferrer">
                  Buka hasil <Icon name="external" size={15} />
                </a>
              )}
              <EntityActions row={d} onDone={refresh} />
            </article>
          ))}
        </div>
      </Panel>
      <Panel title="Artefak dan verifikasi">
        <DataTable
          rows={artifacts}
          columns={[
            { key: "kind", label: "Berkas", render: (r) => label(r.kind) },
            { key: "size", label: "Ukuran (byte)", render: (r) => num(r.size) },
            {
              key: "sha256",
              label: "SHA-256",
              render: (r) => (
                <code className="checksum">{r.sha256 || "Belum tercatat"}</code>
              ),
            },
            {
              key: "verified_at",
              label: "Verifikasi Drive",
              render: (r) => when(r.verified_at),
            },
          ]}
        />
      </Panel>
      <Panel title="Riwayat konten">
        <EventList rows={list(d.events)} />
      </Panel>
    </Resource>
  );
}
export function EventList({ rows }: { rows: Row[] }) {
  return (
    <DataTable
      rows={rows}
      empty="Belum ada aktivitas tercatat"
      columns={[
        {
          key: "created_at",
          label: "Waktu",
          render: (r) => when(r.created_at),
        },
        { key: "kind", label: "Peristiwa", render: (r) => label(r.kind) },
        {
          key: "entity_id",
          label: "Objek",
          render: (r) => <code>{r.entity_id || "Sistem"}</code>,
        },
        {
          key: "payload",
          label: "Rincian",
          render: (r) => (
            <details>
              <summary>Lihat rincian</summary>
              <pre>{JSON.stringify(r.payload, null, 2)}</pre>
            </details>
          ),
        },
      ]}
    />
  );
}
