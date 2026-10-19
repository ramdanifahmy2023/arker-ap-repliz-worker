import { useEffect, useState } from "react";
import { post } from "./api";
import { Badge, Panel, Resource, useResource } from "./components";
import { Icon } from "./icons";
import type { Row } from "./model";
export function ServiceControls({ revision }: { revision: number }) {
  const [serviceRevision, setServiceRevision] = useState(0);
  const resource = useResource("/service", revision + serviceRevision, true);
  const [pending, setPending] = useState<{
    action: string;
    previousPid: unknown;
  } | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const service = resource.data || {};
  useEffect(() => {
    if (!pending || !resource.data) return;
    const current = resource.data;
    const confirmed =
      pending.action === "stop"
        ? !current.worker_running && current.worker_state === "stopped"
        : current.worker_running &&
          (pending.action !== "restart" ||
            current.worker_pid !== pending.previousPid);
    if (confirmed) {
      setMessage(
        pending.action === "stop"
          ? "Proses worker sudah berhenti. API panel tetap berjalan."
          : pending.action === "restart"
            ? "Worker sudah berjalan dengan proses baru."
            : "Proses worker sudah berjalan.",
      );
      setPending(null);
    }
  }, [resource.data, pending]);
  async function action(kind: string) {
    setSending(true);
    setError("");
    try {
      const result: Row = await post(`/service/${kind}`, {});
      setPending({ action: kind, previousPid: service.worker_pid });
      setMessage(
        result.note ||
          "Permintaan diterima. Menunggu konfirmasi kondisi proses.",
      );
      setServiceRevision((v) => v + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  }
  return (
    <Panel
      title="Proses layanan"
      note="Menghentikan proses worker tetap mempertahankan API dan akses panel."
    >
      <Resource {...resource}>
        <dl className="facts">
          <div>
            <dt>Pengelola layanan</dt>
            <dd>
              <Badge state={service.running ? "connected" : "offline"}>
                {service.running ? "Berjalan" : "Belum berjalan"}
              </Badge>
            </dd>
          </div>
          <div>
            <dt>Proses worker</dt>
            <dd>
              <Badge state={service.worker_running ? "running" : "paused"}>
                {service.worker_state === "stopping"
                  ? "Sedang berhenti"
                  : service.worker_running
                    ? "Berjalan"
                    : "Berhenti"}
              </Badge>
            </dd>
          </div>
          <div>
            <dt>PID worker</dt>
            <dd>{service.worker_pid || "Tidak ada proses"}</dd>
          </div>
        </dl>
        <div className="control-body">
          {service.running ? (
            <div className="actions">
              <button
                className="button"
                disabled={sending || !!pending || service.worker_running}
                onClick={() => void action("start")}
              >
                <Icon name="play" size={17} />
                Jalankan worker
              </button>
              <button
                className="button secondary"
                disabled={sending || !!pending || !service.worker_running}
                onClick={() => void action("stop")}
              >
                <Icon name="pause" size={17} />
                Hentikan worker
              </button>
              <button
                className="button secondary"
                disabled={sending || !!pending || !service.worker_running}
                onClick={() => void action("restart")}
              >
                <Icon name="rotate" size={17} />
                Restart worker
              </button>
            </div>
          ) : (
            <p>
              API berjalan sendiri. Untuk mengelola proses dari panel, jalankan
              instalasi melalui <code>python -m arker run</code> atau layanan
              Arker yang dikelola CLI.
            </p>
          )}
          {message && (
            <p className="service-feedback" role="status">
              {pending && <span className="loader" />}
              {message}
            </p>
          )}
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
        </div>
      </Resource>
    </Panel>
  );
}
