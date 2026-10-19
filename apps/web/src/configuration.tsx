import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api, post, put } from "./api";
import { Badge, Panel, Resource, useResource } from "./components";
import { Icon } from "./icons";
import { getPath, list, setPath, type Row } from "./model";
type Field = {
  path: string;
  label: string;
  type?: string;
  help?: string;
  min?: number;
  max?: number;
  options?: { value: string; label: string }[];
};
const fields: Record<string, Field[]> = {
  workflow: [
    {
      path: "workflow.daily_video_limit",
      label: "Batas video per akun / hari",
      type: "number",
      min: 1,
      max: 20,
      help: "Kuota berlaku pada hari Asia/Jakarta. Batas provider yang lebih rendah tetap dihormati.",
    },
    {
      path: "workflow.window_start",
      label: "Jam mulai posting (WIB)",
      type: "number",
      min: 0,
      max: 23,
    },
    {
      path: "workflow.window_end",
      label: "Jam akhir posting (WIB)",
      type: "number",
      min: 1,
      max: 24,
    },
    {
      path: "workflow.max_batch_links",
      label: "Maksimal link per batch",
      type: "number",
      min: 1,
      max: 100,
    },
    {
      path: "workflow.max_pending_assets",
      label: "Batas aset yang belum selesai",
      type: "number",
      min: 1,
      max: 10000,
    },
  ],
  video: [
    {
      path: "video.min_duration",
      label: "Durasi minimum (detik)",
      type: "number",
      min: 3,
      max: 90,
    },
    {
      path: "video.max_duration",
      label: "Durasi maksimum (detik)",
      type: "number",
      min: 3,
      max: 90,
    },
    {
      path: "video.ffmpeg",
      label: "Program FFmpeg",
      help: "Nama executable atau lokasi program pada mesin worker.",
    },
    { path: "video.ffprobe", label: "Program FFprobe" },
    { path: "ai.enabled", label: "Aktifkan analisis AI", type: "checkbox" },
    {
      path: "ai.transcription_enabled",
      label: "Aktifkan transkripsi lokal",
      type: "checkbox",
      help: "Transkrip memakai program Whisper lokal; audio tidak dikirim ke layanan transkripsi.",
    },
    {
      path: "ai.whisper_executable",
      label: "Program Whisper lokal",
      help: "Nama atau lokasi executable whisper-cli pada mesin worker.",
    },
    {
      path: "ai.whisper_model",
      label: "File model Whisper",
      help: "Lokasi model yang sudah tersedia pada mesin worker.",
    },
    {
      path: "ai.base_url",
      label: "Endpoint AI",
      options: [
        { value: "https://api.openai.com/v1", label: "OpenAI" },
        { value: "https://openrouter.ai/api/v1", label: "OpenRouter" },
      ],
    },
    {
      path: "ai.model",
      label: "Model AI",
      help: "Gunakan ID model yang tersedia pada koneksi kamu.",
    },
  ],
  reply: [
    {
      path: "reply.enabled",
      label: "Aktifkan modul balasan",
      type: "checkbox",
    },
    {
      path: "reply.daily_limit",
      label: "Maksimal balasan per akun / hari",
      type: "number",
      min: 1,
      max: 100,
      help: "Kuota balasan terpisah dari kuota video.",
    },
  ],
  telegram: [
    {
      path: "telegram.enabled",
      label: "Aktifkan bot Telegram",
      type: "checkbox",
    },
    {
      path: "telegram.public_ingest",
      label: "Terima link dari pengguna publik",
      type: "checkbox",
    },
    {
      path: "telegram.admin_id",
      label: "ID admin Telegram",
      help: "Notifikasi admin mengikuti ID ini. Rincian batch tetap privat.",
    },
  ],
  reports: [
    {
      path: "reports.enabled",
      label: "Aktifkan pengumpulan laporan",
      type: "checkbox",
    },
  ],
  storage: [
    {
      path: "storage.bank_directory",
      label: "Folder bank pada mesin worker",
      help: "Masukkan lokasi folder pada komputer worker. Ini bukan folder di HP atau browser kamu.",
    },
    {
      path: "drive.folder_url",
      label: "Link folder Google Drive",
      type: "url",
      help: "Gunakan https://drive.google.com/drive/folders/... dengan akses yang sesuai.",
    },
    {
      path: "cleanup.enabled",
      label: "Aktifkan cleanup file kerja",
      type: "checkbox",
    },
    {
      path: "cleanup.retention_hours",
      label: "Retensi setelah seluruh tujuan tayang (jam)",
      type: "number",
      min: 24,
      help: "Bank konten dan arsip tetap disimpan. Minimum 24 jam setelah tujuan terakhir terverifikasi.",
    },
  ],
  general: [
    {
      path: "workflow.max_batch_links",
      label: "Maksimal link per batch",
      type: "number",
      min: 1,
      max: 100,
    },
    {
      path: "workflow.max_pending_assets",
      label: "Batas aset belum selesai",
      type: "number",
      min: 1,
      max: 10000,
    },
  ],
};
export function ConfigEditor({
  section,
  title,
  revision = 0,
}: {
  section: string;
  title: string;
  revision?: number;
}) {
  const resource = useResource("/configuration", revision);
  const [draft, setDraft] = useState<Row>({});
  const [base, setBase] = useState(0);
  const [applied, setApplied] = useState(0);
  const [validation, setValidation] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<Row | null>(null);
  const [storageCheck, setStorageCheck] = useState<Row | null>(null);
  useEffect(() => {
    if (resource.data) {
      setDraft(resource.data.config);
      setBase(resource.data.desired_version);
      setApplied(resource.data.applied_version);
      setValidation(null);
      setSaved(null);
    }
  }, [resource.data]);
  useEffect(() => {
    if (!saved) return;
    let alive = true;
    const timer = setInterval(
      () =>
        void api("/configuration")
          .then((r) => {
            if (alive) setApplied(r.applied_version);
          })
          .catch(() => {}),
      2000,
    );
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [saved]);
  const update = (path: string, value: unknown) => {
    setDraft((d) => setPath(d, path, value));
    setValidation(null);
    setSaved(null);
    setError("");
    setStorageCheck(null);
  };
  async function validate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setValidation(await post("/configuration/validate", { config: draft }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    setBusy(true);
    setError("");
    try {
      const r = await put("/configuration", {
        config: draft,
        base_version: base,
      });
      setSaved(r);
      setBase(r.version ?? r.desired_version);
      setValidation(null);
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 409
          ? "Pengaturan telah berubah di tab atau sesi lain. Muat versi terbaru sebelum menyimpan kembali."
          : (e as Error).message,
      );
    } finally {
      setBusy(false);
    }
  }
  async function checkStorage() {
    setBusy(true);
    setError("");
    try {
      setStorageCheck(
        await post("/storage/check", {
          bank_directory: getPath(draft, "storage.bank_directory"),
          folder_url: getPath(draft, "drive.folder_url"),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel
      title={title}
      note="Perubahan berlaku setelah disimpan dan dikonfirmasi worker."
    >
      <Resource {...resource}>
        <div className="config-version">
          <span>
            Tersimpan <b>v{base}</b>
          </span>
          <span>
            Aktif di worker <b>v{applied}</b>
          </span>
          <Badge state={base === applied ? "applied" : "pending"} />
        </div>
        <form onSubmit={(e) => void validate(e)}>
          <div className="form-grid">
            {(fields[section] || []).map((f) => (
              <label
                key={f.path}
                className={`field ${f.type === "checkbox" ? "checkbox-field" : ""}`}
              >
                <span>{f.label}</span>
                {f.type === "checkbox" ? (
                  <input
                    aria-label={f.label}
                    type="checkbox"
                    checked={!!getPath(draft, f.path)}
                    onChange={(e) => update(f.path, e.target.checked)}
                  />
                ) : f.options ? (
                  <select
                    aria-label={f.label}
                    value={getPath(draft, f.path) ?? ""}
                    onChange={(e) => update(f.path, e.target.value)}
                  >
                    {f.options.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    aria-label={f.label}
                    type={f.type || "text"}
                    value={getPath(draft, f.path) ?? ""}
                    onChange={(e) =>
                      update(
                        f.path,
                        f.type === "number"
                          ? Number(e.target.value)
                          : e.target.value,
                      )
                    }
                    min={f.min}
                    max={f.max}
                    autoComplete="off"
                  />
                )}
                {f.help && <small>{f.help}</small>}
                {list(validation?.errors)
                  .filter((r) => r.field === f.path)
                  .map((r, i) => (
                    <span className="field-error" key={i}>
                      {r.message}
                    </span>
                  ))}
              </label>
            ))}
          </div>
          {section === "video" && (
            <div className="inset-note">
              <Icon name="film" />
              <p>
                Profil tetap: orientasi asli, tanpa mirror, zoom 110%, hook
                sebelum detik 3, audio asli. Perubahan tidak merender ulang
                video yang sudah selesai.
              </p>
            </div>
          )}
          {section === "storage" && (
            <div className="inset-note">
              <Icon name="drive" />
              <p>
                Satu aplikasi eksternal mengurus sinkronisasi folder.
                Pemeriksaan lokasi dan URL belum membuktikan file cocok; worker
                memeriksa ID, ukuran, serta checksum tiap file.
              </p>
            </div>
          )}
          <div className="form-actions">
            {section === "storage" && (
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => void checkStorage()}
              >
                Periksa lokasi & link
              </button>
            )}
            <button className="button" disabled={busy}>
              {busy ? <span className="loader" /> : <Icon name="check" />}
              Periksa perubahan
            </button>
          </div>
        </form>
        {storageCheck && (
          <div
            className={`notice ${storageCheck.valid ? "success" : "danger"}`}
            role="status"
          >
            <div>
              <b>
                {storageCheck.valid
                  ? "Lokasi dan bentuk link valid"
                  : "Lokasi atau link perlu diperbaiki"}
              </b>
              <p>{storageCheck.note}</p>
              {list(storageCheck.findings).map((f, i) => (
                <p key={i}>{f.message}</p>
              ))}
              {storageCheck.folder_id && (
                <p>
                  ID folder: <code>{storageCheck.folder_id}</code>
                </p>
              )}
            </div>
          </div>
        )}
        {validation && (
          <div
            className={`validation ${validation.valid ? "" : "invalid"}`}
            role="status"
          >
            <h3>
              {validation.valid
                ? "Perubahan siap disimpan"
                : "Periksa pengaturan berikut"}
            </h3>
            {validation.valid ? (
              <>
                <ul>
                  {list(validation.impact).map((v, i) => (
                    <li key={i}>{String(v)}</li>
                  ))}
                </ul>
                <button
                  className="button"
                  disabled={busy}
                  onClick={() => void save()}
                >
                  Simpan versi baru
                </button>
              </>
            ) : (
              <ul>
                {list(validation.errors).map((v, i) => (
                  <li key={i}>
                    {v.field}: {v.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {saved && (
          <div className="notice success">
            <div>
              <b>Versi {saved.version ?? saved.desired_version} tersimpan</b>
              <p>Penyimpanan dan penerapan mempunyai status terpisah.</p>
              <Badge
                state={
                  applied === (saved.version ?? saved.desired_version)
                    ? "applied"
                    : "pending"
                }
              />
              <p>
                {applied === (saved.version ?? saved.desired_version)
                  ? "Worker sudah mengonfirmasi versi ini."
                  : "Perintah penerapan sudah dicatat. Menunggu konfirmasi worker."}
              </p>
            </div>
          </div>
        )}
        {error && (
          <div className="notice danger" role="alert">
            {error}
          </div>
        )}
      </Resource>
    </Panel>
  );
}
const credentialFields: Record<string, { key: string; label: string }[]> = {
  repliz: [
    { key: "access_key", label: "Access Key baru" },
    { key: "secret_key", label: "Secret Key baru" },
  ],
  ai: [{ key: "api_key", label: "API key baru" }],
  drive: [{ key: "access_token", label: "OAuth access token baru" }],
  telegram: [{ key: "bot_token", label: "Token bot baru" }],
};
export function CredentialForm({
  provider,
  onSaved,
}: {
  provider: string;
  onSaved?: () => void;
}) {
  const [values, setValues] = useState<Row>({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [test, setTest] = useState<Row | null>(null);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setTest(null);
    try {
      setResult(await post(`/credentials/${provider}`, values));
      setValues({});
      onSaved?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function check() {
    setBusy(true);
    setError("");
    try {
      setTest(await post(`/connections/${provider}/test`, {}));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={(e) => void save(e)} className="credential-form">
      <div className="form-grid">
        {credentialFields[provider]?.map((f) => (
          <label className="field" key={f.key}>
            <span>{f.label}</span>
            <input
              type="password"
              value={values[f.key] || ""}
              onChange={(e) =>
                setValues({ ...values, [f.key]: e.target.value })
              }
              autoComplete="new-password"
              required
              spellCheck={false}
            />
          </label>
        ))}
      </div>
      <p className="form-help">
        Nilai tersimpan tidak ditampilkan kembali. Isi kedua kunci Repliz saat
        mengganti koneksi. Rahasia disimpan di mesin layanan.
      </p>
      <div className="form-actions">
        <button
          type="button"
          className="button secondary"
          disabled={busy}
          onClick={() => void check()}
        >
          Tes koneksi baca
        </button>
        <button className="button" disabled={busy}>
          {busy ? <span className="loader" /> : <Icon name="shield" />}Simpan
          kredensial
        </button>
      </div>
      {result && (
        <p className="notice success" role="status">
          Kredensial tersimpan pada versi{" "}
          {result.version ?? result.credential_version}. Perintah penerapan
          sudah dicatat; lihat versi aktif pada halaman Pengaturan.
        </p>
      )}
      {test && (
        <div
          className={`notice ${test.valid || test.ok || test.connected ? "success" : "warning"}`}
          role="status"
        >
          <div>
            <b>
              {test.message ||
                test.detail ||
                test.status ||
                "Pemeriksaan selesai"}
            </b>
            {test.note && <p>{test.note}</p>}
            {test.account_count !== undefined && (
              <p>{test.account_count} akun terbaca</p>
            )}
          </div>
        </div>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
