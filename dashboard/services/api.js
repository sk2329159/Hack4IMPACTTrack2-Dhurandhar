/**
 * SENTINEL-AI — API Service Layer
 * =================================
 * All calls to the backend API go through this file.
 * Base URL: http://localhost:8000/api/v1
 *
 * Endpoints:
 *   POST /auth/login        → { access_token, role, expires_in }
 *   POST /detect            → { content_id, ai_probability, confidence,
 *                               risk_level, model_attribution, explanation,
 *                               cluster_id, detected_at }
 *   GET  /dashboard/overview → { stats, recent, trend, graph }
 */

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

// ── Token storage (in-memory — no localStorage per security policy) ───────────
let _token = null;

export function setToken(t) { _token = t; }
export function getToken()  { return _token; }
export function clearToken(){ _token = null; }

// ── Platform normalizer ───────────────────────────────────────────────────────
// Frontend uses rich display names; backend only accepts 4 values.
const PLATFORM_MAP = {
  "Twitter/X":  "twitter",
  "Twitter":    "twitter",
  "Reddit":     "reddit",
  "Email":      "email",
  "Manual":     "manual",
  // These platforms aren't in the backend enum — map to closest equivalent
  "Telegram":   "manual",
  "TikTok":     "twitter",
  "4chan":       "manual",
  "Discord":    "manual",
  "Facebook":   "manual",
  "YouTube":    "manual",
  "WhatsApp":   "manual",
};

export function normalizePlatform(displayPlatform) {
  return PLATFORM_MAP[displayPlatform] || "manual";
}

// ── Attribution display normalizer ───────────────────────────────────────────
// Backend returns: GPT-family, Claude-family, Gemini-family, Unknown
// Frontend shows:  GPT-4o, Claude-3.5, Gemini-1.5, Unknown/Custom
const ATTRIBUTION_DISPLAY_MAP = {
  "GPT-family":    "GPT-4o",
  "Claude-family": "Claude-3.5",
  "Gemini-family": "Gemini-1.5",
  "Unknown":       "Unknown/Custom",
};

export function attributionToDisplay(backendAttribution) {
  return ATTRIBUTION_DISPLAY_MAP[backendAttribution] || backendAttribution;
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (_token) {
    headers["Authorization"] = `Bearer ${_token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new APIError(res.status, err.detail || "Request failed");
  }

  return res.json();
}

export class APIError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
    this.name = "APIError";
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────

/**
 * Login with username + password.
 * Stores JWT token in memory.
 *
 * Backend demo credentials:
 *   analyst / analyst123  →  role: analyst  (can detect + view dashboard)
 *   viewer  / viewer123   →  role: viewer   (dashboard only)
 *   admin   / admin123    →  role: admin
 *
 * @returns {{ access_token, token_type, role, expires_in }}
 */
export async function login(username, password) {
  const data = await apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(data.access_token);
  return data;
}

export function logout() {
  clearToken();
}

// ── Detection ─────────────────────────────────────────────────────────────────

/**
 * Analyze text for AI-generated content.
 *
 * @param {string} text       - Content to analyze (10–10,000 chars)
 * @param {string} platform   - Display platform name (will be normalized)
 * @param {string} [actorId]  - Optional actor identifier
 *
 * @returns {{
 *   content_id, ai_probability, confidence,
 *   risk_level, model_attribution, explanation,
 *   cluster_id, detected_at
 * }}
 */
export async function detect(text, platform, actorId = null) {
  const backendPlatform = normalizePlatform(platform);

  const body = {
    text,
    platform: backendPlatform,
  };
  if (actorId && actorId.trim()) {
    body.actor_id = actorId.trim();
  }

  const data = await apiFetch("/detect", {
    method: "POST",
    body: JSON.stringify(body),
  });

  // Normalize attribution for display
  return {
    ...data,
    model_attribution_display: attributionToDisplay(data.model_attribution),
  };
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

/**
 * Get full dashboard overview.
 *
 * @param {string} window - "1h" | "6h" | "24h" | "7d"
 * @param {number} limit  - Max recent detections (1–100)
 *
 * @returns {{
 *   stats: { total_analyzed, ai_flagged, high_risk, campaign_clusters,
 *             avg_confidence, avg_latency_ms },
 *   recent: Array<{ content_id, platform, risk_level, ai_probability,
 *                   confidence, model_attribution, cluster_id,
 *                   actor_id, detected_at }>,
 *   trend:  Array<{ bucket, total, ai_flagged, high_risk }>,
 *   graph:  { nodes: Array<{id, type, label, ai_probability}>,
 *             links: Array<{source, target, type}> }
 * }}
 */
export async function getDashboardOverview(window = "24h", limit = 20) {
  return apiFetch(`/dashboard/overview?window=${window}&limit=${limit}`);
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function healthCheck() {
  const res = await fetch(`${BASE_URL.replace("/api/v1", "")}/health`);
  return res.json();
}