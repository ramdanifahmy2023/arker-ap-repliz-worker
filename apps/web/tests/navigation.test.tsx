// @vitest-environment jsdom
import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import App from "../src/App";
import { menus } from "../src/model";
const config = {
  application: { mode: "shadow", publish_enabled: false },
  workflow: {
    daily_video_limit: 20,
    window_start: 8,
    window_end: 23,
    max_batch_links: 100,
    max_pending_assets: 1000,
  },
  storage: { bank_directory: "/fixture/bank" },
  drive: { folder_url: "" },
  video: {
    min_duration: 3,
    max_duration: 90,
    ffmpeg: "ffmpeg",
    ffprobe: "ffprobe",
  },
  ai: { enabled: false, base_url: "https://api.openai.com/v1", model: "" },
  reply: { enabled: false, daily_limit: 20 },
  telegram: { enabled: false, public_ingest: true, admin_id: "" },
  cleanup: { enabled: false, retention_hours: 24 },
  reports: { enabled: false },
};
const fixture: Record<string, unknown> = {
  "/api/auth/session": {
    authenticated: true,
    user: { id: "fixture-admin", email: "operator@example.com" },
    csrf_token: "fixture-csrf",
  },
  "/api/configuration": {
    config,
    desired_version: 1,
    applied_version: 1,
    credentials: {},
  },
  "/api/health": {
    connected: false,
    state: "offline",
    heartbeat_at: null,
    components: {},
    applied_version: 1,
  },
  "/api/overview": {
    health: { connected: false },
    summary: {
      assets_total: 0,
      assets_active: 0,
      assets_completed: 0,
      deliveries_published: 0,
      deliveries_scheduled: 0,
      attention_count: 0,
    },
    charts: { throughput: [], stages: [], platforms: [], durations: [] },
    active_assets: [],
    attention: [],
    generated_at: 0,
  },
  "/api/storage": {
    profiles: [],
    capacity: { used: 10, total: 100, free: 90 },
    verification: { verified: 0, awaiting: 0 },
  },
  "/api/reports": {
    items: [],
    metrics: { durations: [] },
    quality: "no_provider_metrics",
  },
};
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (path: string) =>
        new Response(
          JSON.stringify(
            fixture[path.split("?")[0]] ?? { items: [], total: 0 },
          ),
          { headers: { "Content-Type": "application/json" } },
        ),
    ),
  );
  vi.stubGlobal("scrollTo", () => {});
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe("Every navigation destination has a real empty state", () => {
  for (const menu of menus)
    it(menu.label, async () => {
      history.replaceState(null, "", `/#${menu.id}`);
      render(<App />);
      await screen.findByRole("heading", { level: 1, name: menu.label });
      await waitFor(() =>
        expect(screen.queryByText("Menghubungkan ke Arker…")).toBeNull(),
      );
      expect(screen.queryByText("Halaman tidak dapat ditampilkan")).toBeNull();
      expect(screen.getByRole("navigation").querySelectorAll("a")).toHaveLength(
        22,
      );
      expect(
        screen
          .getByRole("link", { name: menu.label })
          .getAttribute("aria-current"),
      ).toBe("page");
    });
});
