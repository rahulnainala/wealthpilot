const API_SETTING = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// "same-origin": the API is proxied under this site's own /api (next.config rewrites).
export const API_BASE = API_SETTING === "same-origin" ? "" : API_SETTING;

// http(s):// -> ws(s):// for the ticker socket. A same-origin rewrite can't carry a
// WebSocket, so the ticker stays off there and the app shows snapshot prices.
export const WS_BASE = API_BASE ? API_BASE.replace(/^http/, "ws") : null;

// Public read-only demo on the fictional fixture portfolio (backend DEMO_MODE).
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
