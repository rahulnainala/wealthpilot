import { create } from "zustand";

export interface Tick {
  token: number;
  symbol: string;
  ltp: number;
  change_pct: number;
  ts: number;
}

export type StreamStatus = "live" | "delayed" | "snapshot";

const HISTORY_CAP = 30;

export interface TickerState {
  streamStatus: StreamStatus;
  ticks: Record<string, Tick>; // latest tick keyed by symbol
  history: Record<string, number[]>; // rolling LTP history for sparklines
  setStreamStatus: (status: StreamStatus) => void;
  applyTick: (tick: Tick) => void;
  reset: () => void;
}

export const useTickerStore = create<TickerState>((set) => ({
  streamStatus: "snapshot",
  ticks: {},
  history: {},
  setStreamStatus: (status) => set({ streamStatus: status }),
  applyTick: (tick) =>
    set((state) => {
      const prior = state.history[tick.symbol] ?? [];
      const next = [...prior, tick.ltp].slice(-HISTORY_CAP);
      return {
        ticks: { ...state.ticks, [tick.symbol]: tick },
        history: { ...state.history, [tick.symbol]: next },
      };
    }),
  reset: () => set({ ticks: {}, history: {}, streamStatus: "snapshot" }),
}));
