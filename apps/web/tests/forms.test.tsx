// @vitest-environment jsdom
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { CredentialForm, ConfigEditor } from "../src/configuration";
import {
  ActionButton,
  Progress,
  TrendChart,
  Resource,
  useResource,
} from "../src/components";
import { api, setCsrf } from "../src/api";
import { Intake } from "../src/content-pages";
const response = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
beforeEach(() => {
  setCsrf("test-session");
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe("Authenticated controls", () => {
  it("sets CSRF and never persists credential values in browser storage", async () => {
    const fetcher = vi.fn(async (_path: string, _init?: RequestInit) =>
      response({ configured: true, version: 2 }),
    );
    vi.stubGlobal("fetch", fetcher);
    const local = vi.spyOn(Storage.prototype, "setItem");
    render(<CredentialForm provider="repliz" />);
    fireEvent.change(screen.getByLabelText("Access Key baru"), {
      target: { value: "fixture-access" },
    });
    fireEvent.change(screen.getByLabelText("Secret Key baru"), {
      target: { value: "fixture-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Simpan kredensial" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Secret Key baru")).toHaveProperty(
        "value",
        "",
      ),
    );
    expect(fetcher.mock.calls[0]?.[0]).toBe("/api/credentials/repliz");
    const init = fetcher.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("test-session");
    expect(init.credentials).toBe("same-origin");
    expect(local).not.toHaveBeenCalled();
    expect(screen.queryByText("fixture-secret")).toBeNull();
  });
  it("uses the provider telegram field name", async () => {
    const fetcher = vi.fn(async (_path: string, _init?: RequestInit) =>
      response({ configured: true, version: 1 }),
    );
    vi.stubGlobal("fetch", fetcher);
    render(<CredentialForm provider="telegram" />);
    fireEvent.change(screen.getByLabelText("Token bot baru"), {
      target: { value: "fixture-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Simpan kredensial" }));
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(
      JSON.parse((fetcher.mock.calls[0]?.[1] as RequestInit).body as string),
    ).toEqual({ bot_token: "fixture-token" });
  });
  it("tracks a command once under StrictMode and exposes worker result", async () => {
    const fetcher = vi.fn(async (path: string) =>
      response(
        path === "/api/commands"
          ? { command: { id: "command1", status: "pending" } }
          : {
              command: {
                id: "command1",
                status: "succeeded",
                result: { message: "Worker dijeda" },
              },
            },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    render(
      <StrictMode>
        <ActionButton kind="pause_processing">Jeda</ActionButton>
      </StrictMode>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Jeda" }));
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain("Worker dijeda"),
    );
    expect(
      fetcher.mock.calls.filter((c) => c[0] === "/api/commands"),
    ).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Jeda" })).toHaveProperty(
      "disabled",
      false,
    );
  });
  it("shows conflict without replacing the user draft", async () => {
    const config = {
      workflow: { max_batch_links: 100, max_pending_assets: 1000 },
    };
    const fetcher = vi.fn(async (path: string, init?: RequestInit) =>
      path === "/api/configuration" && !init?.method
        ? response({ config, desired_version: 2, applied_version: 1 })
        : path.endsWith("/validate")
          ? response({
              valid: true,
              impact: ["Konten baru memakai versi baru."],
            })
          : response({ detail: "Konflik versi" }, 409),
    );
    vi.stubGlobal("fetch", fetcher);
    render(<ConfigEditor section="general" title="Pengaturan" />);
    const input = await screen.findByLabelText("Maksimal link per batch");
    fireEvent.change(input, { target: { value: "15" } });
    fireEvent.click(screen.getByRole("button", { name: "Periksa perubahan" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Simpan versi baru" }),
    );
    await screen.findByRole("alert");
    expect(screen.getByRole("alert").textContent).toContain(
      "tab atau sesi lain",
    );
    expect(input).toHaveProperty("value", "15");
    const save = fetcher.mock.calls.find((c) => c[1]?.method === "PUT");
    expect(JSON.parse(save![1]!.body as string).base_version).toBe(2);
  });
  it("sends one batch and displays rejected source reasons", async () => {
    const fetcher = vi.fn(async () =>
      response({
        accepted: 1,
        duplicates: 0,
        rejected: [
          { url: "https://example.org", reason: "Sumber bukan Instagram" },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetcher);
    render(<Intake navigate={() => {}} />);
    fireEvent.change(screen.getByLabelText("Link sumber"), {
      target: {
        value: "https://www.instagram.com/reel/fixture/\nhttps://example.org",
      },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Periksa & masukkan antrean" }),
    );
    await screen.findByText("https://example.org: Sumber bukan Instagram");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("rejects network failures as offline and emits session expiration", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("network");
      }),
    );
    await expect(api("/health")).rejects.toThrow("tidak dapat dihubungi");
    const expired = vi.fn();
    window.addEventListener("arker-session-expired", expired);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response({ detail: "Sesi berakhir" }, 401)),
    );
    await expect(api("/health")).rejects.toThrow("Sesi berakhir");
    expect(expired).toHaveBeenCalledTimes(1);
    window.removeEventListener("arker-session-expired", expired);
  });
});
describe("Refresh continuity", () => {
  it("preserves a focused form while the same resource refreshes", async () => {
    let finish: ((response: Response) => void) | undefined;
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response({ ready: true }))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      );
    vi.stubGlobal("fetch", fetcher);
    function Form({ revision }: { revision: number }) {
      const resource = useResource("/health", revision);
      return (
        <Resource {...resource}>
          <input aria-label="Draft kerja" defaultValue="Teks belum disimpan" />
        </Resource>
      );
    }
    const view = render(<Form revision={0} />);
    const input = await screen.findByLabelText("Draft kerja");
    input.focus();
    view.rerender(<Form revision={1} />);
    expect(document.activeElement).toBe(input);
    expect(screen.queryByText("Memuat data worker…")).toBeNull();
    finish?.(response({ ready: true }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    expect(document.activeElement).toBe(input);
  });
});
describe("Progress and chart evidence", () => {
  it("does not expose a fabricated value for an unmeasured stage", () => {
    render(<Progress done={null} total={null} label="Analisis" active />);
    const progress = screen.getByRole("progressbar");
    expect(progress.hasAttribute("aria-valuenow")).toBe(false);
    expect(progress.getAttribute("aria-valuetext")).toBe(
      "Total belum diketahui",
    );
  });
  it("separates asset and delivery units with an accessible data table", () => {
    render(
      <TrendChart rows={[{ date: "2026-10-19", assets: 2, deliveries: 5 }]} />,
    );
    expect(screen.getAllByText("Aset masuk")).toHaveLength(2);
    expect(screen.getByText("Delivery tayang terverifikasi")).toBeTruthy();
    expect(screen.getByRole("img").getAttribute("aria-label")).toContain(
      "bukan rasio",
    );
    expect(screen.getByText("Lihat tabel data dan waktu")).toBeTruthy();
    expect(screen.getAllByText("5")).toHaveLength(2);
  });
});
