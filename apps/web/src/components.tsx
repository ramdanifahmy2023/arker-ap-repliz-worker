import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, post } from "./api";
import { Icon } from "./icons";
import {
  label,
  list,
  num,
  progressValue,
  stateTone,
  when,
  type Row,
} from "./model";
export function useResource(path: string, revision = 0, poll = false) {
  const [data, setData] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const loadedPath = useRef<string | null>(null);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function load() {
      try {
        const next = await api(path, { signal: controller.signal });
        if (alive) {
          loadedPath.current = path;
          setData(next);
          setError("");
        }
      } catch (e) {
        if (alive && !controller.signal.aborted) setError((e as Error).message);
      } finally {
        if (alive) {
          setLoading(false);
          if (poll) timer = setTimeout(load, 8000);
        }
      }
    }
    if (loadedPath.current !== path) {
      setLoading(true);
      setData(null);
    }
    setError("");
    void load();
    return () => {
      alive = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, revision, poll]);
  return { data, error, loading };
}
export function Resource({
  loading,
  error,
  children,
}: {
  loading: boolean;
  error: string;
  children: ReactNode;
}) {
  return loading ? (
    <div className="loading" role="status">
      <span className="loader" />
      Memuat data worker…
    </div>
  ) : error ? (
    <div className="notice danger" role="alert">
      <Icon name="alert" />
      <span>{error}</span>
    </div>
  ) : (
    children
  );
}
export function Empty({
  title = "Belum ada data",
  children,
  icon = "folder",
}: {
  title?: string;
  children?: ReactNode;
  icon?: string;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name={icon} size={26} />
      </span>
      <h3>{title}</h3>
      <p>
        {children ||
          "Data akan tampil setelah worker mencatat pekerjaan di instalasi ini."}
      </p>
    </div>
  );
}
export function Badge({
  state,
  children,
}: {
  state?: unknown;
  children?: ReactNode;
}) {
  return (
    <span className={`badge ${stateTone(state)}`}>
      <span aria-hidden="true" />
      {children || label(state)}
    </span>
  );
}
export function Panel({
  title,
  note,
  action,
  children,
  className = "",
}: {
  title?: string;
  note?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <header className="panel-head">
          <div>
            <h2>{title}</h2>
            {note && <p>{note}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}
export function Progress({
  done,
  total,
  label: accessibleLabel,
  active = false,
}: {
  done: unknown;
  total: unknown;
  label: string;
  active?: boolean;
}) {
  const value = progressValue(done, total);
  return (
    <div
      className={`progress ${active ? "active" : ""}`}
      role="progressbar"
      aria-label={accessibleLabel}
      aria-valuemin={value === null ? undefined : 0}
      aria-valuemax={value === null ? undefined : 100}
      aria-valuenow={value === null ? undefined : Math.round(value)}
      aria-valuetext={
        value === null
          ? "Total belum diketahui"
          : `${num(done)} dari ${num(total)}`
      }
    >
      <span
        style={{ transform: `scaleX(${value === null ? 0.12 : value / 100})` }}
      />
    </div>
  );
}
export function DataTable({
  rows,
  columns,
  empty,
}: {
  rows: Row[];
  columns: { key: string; label: string; render?: (row: Row) => ReactNode }[];
  empty?: string;
}) {
  return !rows.length ? (
    <Empty title={empty} />
  ) : (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id ?? i}>
              {columns.map((c) => (
                <td key={c.key} data-label={c.label}>
                  {c.render
                    ? c.render(r)
                    : typeof r[c.key] === "object"
                      ? JSON.stringify(r[c.key])
                      : String(r[c.key] ?? "Belum tersedia")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function ActionButton({
  kind,
  payload = {},
  children,
  onDone,
  secondary = false,
}: {
  kind: string;
  payload?: Row;
  children: ReactNode;
  onDone?: () => void;
  secondary?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearTimeout(timer.current);
    };
  }, []);
  const track = async (id: string) => {
    try {
      const r = await api(`/commands/${encodeURIComponent(id)}`);
      if (!mounted.current) return;
      const command = r.command || r;
      setResult(command);
      if (["pending", "queued", "accepted", "running"].includes(command.status))
        timer.current = setTimeout(() => void track(id), 1500);
      else {
        setBusy(false);
        onDone?.();
      }
    } catch (e) {
      if (mounted.current) {
        setError((e as Error).message);
        setBusy(false);
      }
    }
  };
  async function run() {
    setBusy(true);
    setError("");
    try {
      const r = await post("/commands", {
        kind,
        payload,
        idempotency_key: crypto.randomUUID(),
      });
      if (!mounted.current) return;
      const c = r.command || r;
      setResult(c);
      if (c.id) void track(c.id);
      else {
        setBusy(false);
        onDone?.();
      }
    } catch (e) {
      if (mounted.current) {
        setError((e as Error).message);
        setBusy(false);
      }
    }
  }
  return (
    <div className="action-wrap">
      <button
        className={secondary ? "button secondary" : "button"}
        disabled={busy}
        onClick={() => void run()}
      >
        {busy ? <span className="loader" /> : null}
        {children}
      </button>
      {result && (
        <span className="action-result" role="status">
          {label(result.status)}
          {result.error ||
          result.reason ||
          result.result?.error ||
          result.result?.message
            ? `: ${result.error || result.reason || result.result?.error || result.result?.message}`
            : ""}
        </span>
      )}
      {result?.result && Object.keys(result.result).length > 0 && (
        <details className="command-details">
          <summary>Rincian hasil perintah</summary>
          <pre>{JSON.stringify(result.result, null, 2)}</pre>
        </details>
      )}
      {error && (
        <span className="field-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
export function EntityActions({
  row,
  onDone,
}: {
  row: Row;
  onDone?: () => void;
}) {
  return (
    <div className="actions">
      {list(row.available_actions).map((a, i) => (
        <ActionButton
          key={`${a.kind}-${i}`}
          kind={a.kind}
          payload={a.payload || { id: row.id }}
          secondary
          onDone={onDone}
        >
          {a.label || label(a.kind)}
        </ActionButton>
      ))}
    </div>
  );
}
export function Timestamp({ value }: { value: unknown }) {
  return <span className="timestamp">{when(value)}</span>;
}
export function BarChart({
  rows,
  title,
  unit = "aset",
  onSelect,
}: {
  rows: Row[];
  title: string;
  unit?: string;
  onSelect?: (row: Row) => void;
}) {
  const maximum = Math.max(
    1,
    ...rows.map((r) => Number(r.value ?? r.count ?? 0)),
  );
  return (
    <div className="chart-block">
      <div className="bar-chart" role="group" aria-label={title}>
        {rows.map((r, i) => {
          const value = Number(r.value ?? r.count ?? 0);
          return (
            <button
              key={r.label ?? r.state ?? i}
              className="bar-row"
              disabled={!onSelect}
              onClick={() => onSelect?.(r)}
              aria-label={`${label(r.label ?? r.state ?? r.stage)}: ${num(value)} ${unit}`}
            >
              <span>{label(r.label ?? r.state ?? r.stage)}</span>
              <span className="bar-track">
                <span style={{ transform: `scaleX(${value / maximum})` }} />
              </span>
              <strong>{num(value)}</strong>
            </button>
          );
        })}
      </div>
      {!rows.length && (
        <Empty title="Belum ada sampel chart" icon="chart">
          Data akan muncul setelah worker mencatat tahap pekerjaan.
        </Empty>
      )}
      <details className="chart-table">
        <summary>Lihat tabel data · {unit}</summary>
        <DataTable
          rows={rows}
          columns={[
            {
              key: "label",
              label: "Kategori",
              render: (r) => label(r.label ?? r.state ?? r.stage),
            },
            {
              key: "value",
              label: unit,
              render: (r) => num(r.value ?? r.count),
            },
          ]}
        />
      </details>
    </div>
  );
}
export function TrendChart({
  rows,
  onSelect,
}: {
  rows: Row[];
  onSelect?: (row: Row) => void;
}) {
  const chartRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    if (!chartRef.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      setWidth(Math.max(240, entries[0].contentRect.width - 40));
    });
    observer.observe(chartRef.current);
    return () => observer.disconnect();
  }, []);
  const max = Math.max(
    2,
    ...rows.flatMap((r) => [
      Number(r.assets ?? r.intake ?? 0),
      Number(r.published ?? r.deliveries ?? 0),
    ]),
  );
  const height = 190;
  const x = (i: number) =>
    42 + (i * (width - 64)) / Math.max(rows.length - 1, 1);
  const y = (value: number) => height - 25 - (value / max) * (height - 45);
  const points = (key: string, alt: string) =>
    rows.map((r, i) => `${x(i)},${y(Number(r[key] ?? r[alt] ?? 0))}`).join(" ");
  return (
    <div className="trend" ref={chartRef}>
      <div className="chart-legend">
        <span>
          <i />
          Aset masuk
        </span>
        <span>
          <i />
          Delivery tayang terverifikasi
        </span>
      </div>
      {rows.length ? (
        <>
          <svg
            className="trend-svg"
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label="Tren aset masuk dan delivery tayang. Satuan masing-masing terpisah, bukan rasio keberhasilan."
          >
            {[0, 0.5, 1].map((t) => (
              <g key={t}>
                <line
                  x1="42"
                  x2={width - 20}
                  y1={y(max * t)}
                  y2={y(max * t)}
                  className="grid-line"
                />
                <text x="3" y={y(max * t) + 4}>
                  {num(Math.round(max * t))}
                </text>
              </g>
            ))}
            <polyline
              points={points("assets", "intake")}
              className="trend-line primary-line"
            />
            <polyline
              points={points("published", "deliveries")}
              className="trend-line secondary-line"
            />
            {rows.map((r, i) => (
              <g key={i}>
                <circle
                  cx={x(i)}
                  cy={y(Number(r.assets ?? r.intake ?? 0))}
                  r="3.5"
                  className="point-primary"
                />
                <circle
                  cx={x(i)}
                  cy={y(Number(r.published ?? r.deliveries ?? 0))}
                  r="3.5"
                  className="point-secondary"
                />
              </g>
            ))}
          </svg>
          <div className="chart-times">
            {rows.map((r, i) => (
              <button
                key={i}
                onClick={() => onSelect?.(r)}
                disabled={!onSelect}
                title={`${r.date ?? r.label ?? r.bucket}: ${num(r.assets ?? r.intake)} aset, ${num(r.published ?? r.deliveries)} delivery`}
              >
                {String(r.label ?? r.date ?? r.bucket ?? i).slice(-5)}
              </button>
            ))}
          </div>
        </>
      ) : (
        <Empty title="Tren belum tersedia" icon="chart">
          Grafik memakai catatan pekerjaan instalasi ini. Belum ada catatan
          untuk periode ini.
        </Empty>
      )}
      <details className="chart-table">
        <summary>Lihat tabel data dan waktu</summary>
        <DataTable
          rows={rows}
          columns={[
            {
              key: "date",
              label: "Interval",
              render: (r) => String(r.date ?? r.label ?? r.bucket),
            },
            {
              key: "assets",
              label: "Aset masuk",
              render: (r) => num(r.assets ?? r.intake),
            },
            {
              key: "published",
              label: "Delivery terverifikasi",
              render: (r) => num(r.published ?? r.deliveries),
            },
          ]}
        />
      </details>
    </div>
  );
}
