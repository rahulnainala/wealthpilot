import { create } from "zustand";

/** Chat sheet state, global so the command palette can open it with a query. */
interface ChatState {
  open: boolean;
  seed: string | null; // question handed off from the palette
  screen: string; // which page the user is viewing (Pilot context)
  setScreen: (screen: string) => void;
  setOpen: (open: boolean) => void;
  ask: (question: string) => void;
  consumeSeed: () => string | null;
}

export const useChatStore = create<ChatState>((set, get) => ({
  open: false,
  seed: null,
  screen: "Overview",
  setScreen: (screen) => set({ screen }),
  setOpen: (open) => set({ open }),
  ask: (question) => set({ open: true, seed: question || null }),
  consumeSeed: () => {
    const seed = get().seed;
    if (seed) set({ seed: null });
    return seed;
  },
}));
