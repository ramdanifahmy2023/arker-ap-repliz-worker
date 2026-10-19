import { describe, it, expect } from "vitest";
import {
  menus,
  progressValue,
  safeHref,
  setPath,
  getPath,
  when,
  stateTone,
} from "../src/model";
describe("Operational display contracts", () => {
  it("exposes the22 unique planned destinations", () => {
    expect(menus).toHaveLength(22);
    expect(new Set(menus.map((m) => m.id)).size).toBe(22);
    expect(new Set(menus.map((m) => m.group)).size).toBe(6);
  });
  it("never invents a percent when total is absent", () => {
    expect(progressValue(25, null)).toBeNull();
    expect(progressValue(25, 0)).toBeNull();
    expect(progressValue(null, 100)).toBeNull();
    expect(progressValue(1, 3)).toBeCloseTo(33.333);
    expect(progressValue(110, 100)).toBe(100);
    expect(progressValue(-1, 10)).toBe(0);
  });
  it("blocks unsafe protocol links", () => {
    expect(safeHref("javascript:alert(1)")).toBeUndefined();
    expect(safeHref("data:text/html,secret")).toBeUndefined();
    expect(safeHref("https://example.com/post")).toBe(
      "https://example.com/post",
    );
  });
  it("keeps previous config immutable on field changes", () => {
    const original = {
      storage: { bank_directory: "/bank" },
      workflow: { daily_video_limit: 20 },
    };
    const changed = setPath(original, "workflow.daily_video_limit", 15);
    expect(getPath(changed, "workflow.daily_video_limit")).toBe(15);
    expect(original.workflow.daily_video_limit).toBe(20);
    expect(changed.storage).toEqual(original.storage);
  });
  it("uses WIB and differentiates accepted from published", () => {
    expect(when("2026-01-01T00:00:00Z")).toContain("07.00");
    expect(stateTone("scheduled")).toBe("neutral");
    expect(stateTone("published")).toBe("success");
    expect(stateTone("submit_unknown")).toBe("warning");
  });
});
