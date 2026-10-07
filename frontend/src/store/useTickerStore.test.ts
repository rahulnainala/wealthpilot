import { beforeEach, describe, expect, it } from "vitest";

import { useTickerStore } from "./useTickerStore";

describe("useTickerStore", () => {
  beforeEach(() => {
    useTickerStore.getState().reset();
  });

  it("defaults to snapshot status", () => {
    expect(useTickerStore.getState().streamStatus).toBe("snapshot");
  });

  it("updates stream status", () => {
    useTickerStore.getState().setStreamStatus("live");
    expect(useTickerStore.getState().streamStatus).toBe("live");
  });

  it("applies ticks and keeps rolling history", () => {
    const { applyTick } = useTickerStore.getState();
    applyTick({ token: 1, symbol: "IOC", ltp: 141.85, change_pct: 1.2, ts: 1 });
    applyTick({ token: 1, symbol: "IOC", ltp: 142.1, change_pct: 1.4, ts: 2 });

    const state = useTickerStore.getState();
    expect(state.ticks.IOC.ltp).toBe(142.1);
    expect(state.history.IOC).toEqual([141.85, 142.1]);
  });

  it("resets ticks and status", () => {
    const { applyTick, reset } = useTickerStore.getState();
    applyTick({ token: 1, symbol: "IOC", ltp: 100, change_pct: 0, ts: 1 });
    reset();
    expect(useTickerStore.getState().ticks).toEqual({});
    expect(useTickerStore.getState().streamStatus).toBe("snapshot");
  });
});
