import {
  Component,
  useCallback,
  useEffect,
  useState,
  type ErrorInfo,
  type FormEvent,
  type ReactNode,
} from "react";
import { api, post, setCsrf } from "./api";
import { Badge, useResource } from "./components";
import { ConfigEditor } from "./configuration";
import {
  AssetDetail,
  Attention,
  Flow,
  Intake,
  Overview,
  Queue,
  WorkerPage,
  type Navigate,
} from "./content-pages";
import {
  Accounts,
  Activity,
  Backups,
  Comments,
  Connections,
  Deliveries,
  Personas,
  Reports,
  Settings,
  Storage,
  Telegram,
} from "./operation-pages";
import { Icon } from "./icons";
import { menus, when, type Session } from "./model";
function readPreference(key: string, fallback: string) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}
function Login({
  session,
  onLogin,
  error: connectionError,
}: {
  session: Session;
  onLogin: (s: Session) => void;
  error?: string;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await post<Session>("/auth/login", { email, password });
      setPassword("");
      setCsrf(result.csrf_token);
      onLogin(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <a className="brand" href="#overview">
          <span className="brand-mark">
            <span />
            <span />
            <span />
          </span>
          arker<span className="brand-period">.</span>
        </a>
        <div>
          <span className="eyebrow">Kendali konten, dari satu tempat</span>
          <h1>
            Kenali alurnya.
            <br />
            Atur langkahnya.
          </h1>
          <p>
            Ikuti setiap konten, pahami kendala worker, dan terapkan pengaturan
            dengan status yang jelas.
          </p>
          <div
            className="login-flow"
            aria-label="Alur konten: sumber menuju TikTok, Facebook dan YouTube"
          >
            <div>
              <Icon name="film" size={25} />
              <span>Satu konten</span>
            </div>
            <span className="flow-connector" />
            <div className="login-destinations">
              <span>TikTok</span>
              <span>Facebook</span>
              <span>YouTube</span>
            </div>
          </div>
        </div>
        <span className="login-caption">
          Kontrol lokal · Windows, macOS & Linux
        </span>
      </section>
      <section className="login-form-side">
        <div className="login-form">
          <span className="small-mark">
            <Icon name="shield" size={24} />
          </span>
          <h2>
            {session.setup_required
              ? "Siapkan admin pertama"
              : "Masuk ke Arker"}
          </h2>
          <p>
            {session.setup_required
              ? "Buat admin secara privat pada mesin layanan, lalu muat ulang halaman ini."
              : "Gunakan akun admin instalasi kamu untuk membuka panel worker."}
          </p>
          {session.setup_required ? (
            <>
              <code className="code-block">python -m arker init</code>
              <p className="form-help">
                CLI meminta email dan password. Tidak ada akun atau password
                bawaan.
              </p>
              <button className="button full" onClick={() => location.reload()}>
                Periksa kembali
              </button>
            </>
          ) : (
            <form onSubmit={(e) => void submit(e)}>
              <label className="field">
                <span>Email</span>
                <input
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@example.com"
                />
              </label>
              <label className="field">
                <span>Password</span>
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              <button className="button full" disabled={busy}>
                {busy ? <span className="loader" /> : null}Masuk ke panel{" "}
                <Icon name="arrow" size={18} />
              </button>
            </form>
          )}
          {(error || connectionError) && (
            <p className="notice danger" role="alert">
              {error || connectionError}
            </p>
          )}
          <div className="login-security">
            <Icon name="shield" size={15} />
            <span>Kredensial layanan dikelola setelah login.</span>
          </div>
        </div>
      </section>
    </main>
  );
}
function Dashboard({
  session,
  onLogout,
  error,
}: {
  session: Session;
  onLogout: () => void;
  error?: string;
}) {
  const [hash, setHash] = useState(location.hash.slice(1) || "overview");
  const [revision, setRevision] = useState(0);
  const [sidebar, setSidebar] = useState(false);
  const [search, setSearch] = useState("");
  const [theme, setTheme] = useState(() =>
    readPreference("arker-theme", "system"),
  );
  const [motion, setMotion] = useState(() =>
    readPreference("arker-motion", "system"),
  );
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const [hidden, setHidden] = useState(document.hidden);
  const [path, query = ""] = hash.split("?");
  const page = menus.find((m) => m.id === path) || menus[0];
  const params = new URLSearchParams(query);
  const health = useResource("/health", revision, true);
  const config = useResource("/configuration", revision, true);
  const refresh = useCallback(() => setRevision((v) => v + 1), []);
  useEffect(() => {
    const change = () => {
      setHash(location.hash.slice(1) || "overview");
      setSidebar(false);
      window.scrollTo({ top: 0, behavior: "instant" });
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    const change = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", change);
    return () => document.removeEventListener("visibilitychange", change);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.motion = motion;
    try {
      localStorage.setItem("arker-theme", theme);
      localStorage.setItem("arker-motion", motion);
    } catch {}
  }, [theme, motion]);
  useEffect(() => {
    document.title = `${page.label} · Arker`;
  }, [page.label]);
  const navigate: Navigate = (id, p) => {
    location.hash = id + (p ? "?" + new URLSearchParams(p).toString() : "");
  };
  const groups = [...new Set(menus.map((m) => m.group))];
  const online = health.data?.connected && !health.error;
  const content = () => {
    switch (page.id) {
      case "overview":
        return <Overview navigate={navigate} revision={revision} />;
      case "flow":
        return <Flow navigate={navigate} revision={revision} />;
      case "worker":
        return <WorkerPage revision={revision} refresh={refresh} />;
      case "attention":
        return (
          <Attention
            revision={revision}
            refresh={refresh}
            navigate={navigate}
          />
        );
      case "intake":
        return <Intake navigate={navigate} />;
      case "queue":
        return (
          <Queue params={params} navigate={navigate} revision={revision} />
        );
      case "bank":
        return (
          <Queue params={params} navigate={navigate} revision={revision} bank />
        );
      case "detail":
        return (
          <AssetDetail
            id={params.get("id")}
            navigate={navigate}
            revision={revision}
            refresh={refresh}
          />
        );
      case "accounts":
        return <Accounts revision={revision} refresh={refresh} />;
      case "quota":
        return <Accounts revision={revision} refresh={refresh} quota />;
      case "calendar":
        return (
          <Deliveries
            revision={revision}
            navigate={navigate}
            params={params}
            calendar
          />
        );
      case "published":
        return (
          <Deliveries revision={revision} navigate={navigate} params={params} />
        );
      case "video":
        return (
          <ConfigEditor
            section="video"
            title="Profil video dan analisis AI"
            revision={revision}
          />
        );
      case "personas":
        return <Personas revision={revision} refresh={refresh} />;
      case "comments":
        return <Comments revision={revision} refresh={refresh} />;
      case "reports":
        return <Reports revision={revision} />;
      case "connections":
        return (
          <Connections
            revision={revision}
            refresh={refresh}
            navigate={navigate}
          />
        );
      case "telegram":
        return <Telegram revision={revision} refresh={refresh} />;
      case "storage":
        return <Storage revision={revision} refresh={refresh} />;
      case "backups":
        return <Backups revision={revision} refresh={refresh} />;
      case "activity":
        return <Activity revision={revision} />;
      case "settings":
        return (
          <Settings
            session={session}
            revision={revision}
            refresh={refresh}
            onLogout={onLogout}
          />
        );
    }
  };
  return (
    <div className="app" data-idle={!online || hidden ? "true" : "false"}>
      <a
        className="skip-link"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Langsung ke isi halaman
      </a>
      {sidebar && (
        <button
          className="sidebar-backdrop"
          aria-label="Tutup navigasi"
          onClick={() => setSidebar(false)}
        />
      )}
      <aside
        className={`sidebar ${sidebar ? "open" : ""}`}
        aria-label="Navigasi utama"
      >
        <div className="sidebar-brand">
          <a className="brand" href="#overview">
            <span className="brand-mark">
              <span />
              <span />
              <span />
            </span>
            arker<span className="brand-period">.</span>
          </a>
          <button
            className="icon-button close-sidebar"
            aria-label="Tutup menu"
            onClick={() => setSidebar(false)}
          >
            <Icon name="close" />
          </button>
        </div>
        <div className="workspace-label">
          <span className="workspace-avatar">
            <Icon name="worker" size={18} />
          </span>
          <span>
            <strong>Worker lokal</strong>
            <small>
              {config.data?.config?.application?.mode === "shadow"
                ? "Mode shadow · publikasi nonaktif"
                : config.data?.config?.application?.mode === "live"
                  ? "Mode live"
                  : "Memuat konfigurasi"}
            </small>
          </span>
        </div>
        <label className="nav-search">
          <Icon name="search" size={17} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari menu…"
            aria-label="Cari menu navigasi"
          />
          {search && (
            <button aria-label="Hapus pencarian" onClick={() => setSearch("")}>
              <Icon name="close" size={15} />
            </button>
          )}
        </label>
        <nav>
          {groups.map((group) => {
            const items = menus.filter(
              (m) =>
                m.group === group &&
                m.label.toLowerCase().includes(search.toLowerCase()),
            );
            if (!items.length) return null;
            const closed = collapsed.includes(group) && !search;
            return (
              <section className="nav-group" key={group}>
                <button
                  className="nav-group-title"
                  aria-expanded={!closed}
                  onClick={() =>
                    setCollapsed((v) =>
                      v.includes(group)
                        ? v.filter((g) => g !== group)
                        : [...v, group],
                    )
                  }
                >
                  {group}
                  <Icon name="chevron" size={13} />
                </button>
                {!closed &&
                  items.map((m) => (
                    <a
                      key={m.id}
                      href={`#${m.id}`}
                      className={m.id === page.id ? "active" : ""}
                      aria-current={m.id === page.id ? "page" : undefined}
                    >
                      <Icon name={m.icon} size={17} />
                      <span>{m.label}</span>
                      {m.id === page.id && <span className="nav-active-dot" />}
                    </a>
                  ))}
              </section>
            );
          })}
          {!menus.some((m) =>
            m.label.toLowerCase().includes(search.toLowerCase()),
          ) && <p className="nav-no-results">Menu tidak ditemukan.</p>}
        </nav>
        <div className="sidebar-footer">
          <span className={`connection-dot ${online ? "connected" : ""}`} />
          <span>
            {online ? "Worker terhubung" : "Worker tidak terhubung"}
            <small>Data {when(health.data?.heartbeat_at)}</small>
          </span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Buka navigasi"
              onClick={() => setSidebar(true)}
            >
              <Icon name="menu" />
            </button>
            <span>Workspace</span>
            <Icon name="chevron" size={14} />
            <strong>{page.group}</strong>
          </div>
          <div className="topbar-tools">
            <span className="mode-label">
              {config.data?.config?.application?.mode && (
                <Badge state={config.data.config.application.mode} />
              )}
            </span>
            <button
              className="icon-button"
              aria-label={
                theme === "dark" ? "Gunakan tema terang" : "Gunakan tema gelap"
              }
              title={theme === "dark" ? "Tema terang" : "Tema gelap"}
              onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            >
              <Icon name={theme === "dark" ? "sun" : "moon"} size={19} />
            </button>
            <button
              className={`icon-button ${motion === "reduced" ? "selected" : ""}`}
              aria-label={
                motion === "reduced"
                  ? "Aktifkan animasi sesuai sistem"
                  : "Kurangi animasi"
              }
              aria-pressed={motion === "reduced"}
              title={
                motion === "reduced"
                  ? "Animasi minimal aktif"
                  : "Kurangi animasi"
              }
              onClick={() =>
                setMotion((m) => (m === "reduced" ? "system" : "reduced"))
              }
            >
              <Icon name={motion === "reduced" ? "pause" : "play"} size={18} />
            </button>
            <button
              className="user-button"
              onClick={() => navigate("settings")}
              aria-label="Buka pengaturan akun"
            >
              {session.user?.email?.slice(0, 2).toUpperCase() || "AD"}
            </button>
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>
          <header className="page-heading">
            <div>
              <span className="page-kicker">{page.group}</span>
              <h1>{page.label}</h1>
              <p>{page.description}</p>
            </div>
            <div className="page-actions">
              <button
                className="icon-button refresh-button"
                aria-label="Perbarui data"
                title="Perbarui data"
                onClick={refresh}
              >
                <Icon name="rotate" size={18} />
              </button>
              {page.id !== "intake" && (
                <button className="button" onClick={() => navigate("intake")}>
                  <Icon name="plus" size={17} />
                  Tambah konten
                </button>
              )}
            </div>
          </header>
          {error && (
            <div className="notice danger" role="alert">
              {error}
            </div>
          )}
          {health.error && (
            <div className="notice danger" role="alert">
              <Icon name="alert" />
              <span>
                {health.error} Data terakhir tidak dianggap sebagai kondisi
                terkini.
              </span>
              <button className="text-button" onClick={refresh}>
                Coba lagi
              </button>
            </div>
          )}
          <div className="page-content" key={hash}>
            {content()}
          </div>
          <footer className="app-footer">
            <span>Arker · Repliz Worker</span>
            <span>Waktu ditampilkan dalam WIB</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    void api<Session>("/auth/session")
      .then((s) => {
        setSession(s);
        setCsrf(s.csrf_token);
      })
      .catch((e) => {
        setError(e.message);
        setSession({ authenticated: false });
      });
    const expired = () => {
      setSession({ authenticated: false });
      setCsrf();
    };
    window.addEventListener("arker-session-expired", expired);
    return () => window.removeEventListener("arker-session-expired", expired);
  }, []);
  async function logout() {
    try {
      await post("/auth/logout", {});
      setSession({ authenticated: false });
      setCsrf();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (!session)
    return (
      <div className="initial-loading" role="status">
        <span className="loader" />
        Menghubungkan ke Arker…
      </div>
    );
  return session.authenticated ? (
    <Dashboard session={session} error={error} onLogout={() => void logout()} />
  ) : (
    <Login session={session} onLogin={setSession} error={error} />
  );
}
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  componentDidCatch(_error: Error, _info: ErrorInfo) {
    /* Error contents can include private API values; do not send them to telemetry. */
  }
  render() {
    return this.state.error ? (
      <main className="fatal-error">
        <h1>Halaman tidak dapat ditampilkan</h1>
        <p>
          Muat ulang untuk mengambil kondisi terbaru. Pekerjaan worker tetap
          tersimpan pada layanan.
        </p>
        <button className="button" onClick={() => location.reload()}>
          Muat ulang panel
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
