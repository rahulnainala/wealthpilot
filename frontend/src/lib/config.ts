export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// http(s):// -> ws(s):// for the ticker socket.
export const WS_BASE = API_BASE.replace(/^http/, "ws");

// Public read-only demo on the fictional fixture portfolio (backend DEMO_MODE).
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
