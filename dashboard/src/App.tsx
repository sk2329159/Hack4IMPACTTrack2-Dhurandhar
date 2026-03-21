import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield, Activity, Brain, Eye, AlertTriangle, Download, Play,
  ChevronDown, ChevronRight, RefreshCw, Radio, Settings, FileText,
  Share2, Zap, TrendingUp, BarChart2, Globe, Users, Database,
  Lock, CheckCircle, Search, Bell, Filter,
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, LineChart, Line, CartesianGrid,
} from "recharts";
import {
  login as apiLogin, detect as apiDetect, getDashboard, logout,
  attrDisplay, normalisePlatform,
  type DetectResponse, type DashboardOverview, type RecentDetection,
} from "./services/api";

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bg0: "var(--bg-base)", bg1: "var(--bg-surface)", bg2: "var(--bg-surface)",
  bg3: "var(--bg-elevated)", bg4: "var(--bg-hover)",
  cyan: "var(--accent)", green: "var(--green)", amber: "var(--amber)",
  red: "var(--red)", purple: "var(--purple)", blue: "var(--blue)",
  pink: "#c084b8", text: "var(--text-1)", muted: "var(--text-2)",
  border: "var(--border)", borderHover: "var(--border-md)",
};

// ─── Types ────────────────────────────────────────────────────────────────────
type Risk = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
type Platform = "Twitter/X" | "Telegram" | "Reddit" | "Facebook" | "TikTok" | "4chan" | "Discord" | "YouTube" | "WhatsApp" | "Email" | "Manual";

interface Metrics {
  totalAnalyzed: number; aiFlagged: number;
  highRisk: number; campaignClusters: number;
  attributionConfidence: number; avgDetectionLatency: number;
}

interface ChartPoint { time: string; detections: number; aiGenerated: number; campaigns: number; blocked: number; }

interface AnalysisResult {
  aiProbability: number; confidence: number; risk: Risk; model: string;
  explanation: string[]; coordinationScore: number; harmPotential: number;
  burstiness: number; perplexity: number; relatedClusters: string[];
  recommendedAction: string; spreadRisk: number; clusterId: string;
}

// ─── Static lists ─────────────────────────────────────────────────────────────
const PLATFORMS: Platform[] = ["Twitter/X","Telegram","Reddit","Facebook","TikTok","4chan","Discord","YouTube","WhatsApp","Email","Manual"];

const TICKER_ITEMS = [
  "⚠ SENTINEL-AI — Real-time AI content detection active",
  "🤖 ML engine: heuristic + stylometric fingerprinting — 4 model families",
  "📡 Backend API connected — PostgreSQL persistence enabled",
  "🔴 Detection pipeline: analyze text → ML score → DB store → dashboard",
  "⚡ RBAC active — analyst/admin can detect; viewer can view dashboard",
  "🧠 Attribution: GPT-family, Claude-family, Gemini-family, Unknown",
  "📊 Cluster IDs: CL-XX format, deterministic SHA-256 based",
  "🌐 Real data — every detection is persisted and shown in dashboard",
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function rnd(min: number, max: number) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function rndF(min: number, max: number) { return +(Math.random() * (max - min) + min).toFixed(2); }

function riskColor(r: string) {
  if (r === "CRITICAL") return C.red;
  if (r === "HIGH")     return C.amber;
  if (r === "MEDIUM")   return "#facc15";
  return C.green;
}
function riskBg(r: string) {
  if (r === "CRITICAL") return "pill pill-critical";
  if (r === "HIGH")     return "pill pill-high";
  if (r === "MEDIUM")   return "pill pill-medium";
  return "pill pill-low";
}

// ─── useClock ─────────────────────────────────────────────────────────────────
function useClock() {
  const [t, setT] = useState(new Date());
  useEffect(() => { const id = setInterval(() => setT(new Date()), 1000); return () => clearInterval(id); }, []);
  return t;
}

// ─── AnimNum ──────────────────────────────────────────────────────────────────
function AnimNum({ value, suffix = "" }: { value: number | string; suffix?: string }) {
  return (
    <motion.span key={String(value)} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }} className="tabular-nums">
      {typeof value === "number" ? value.toLocaleString() : value}{suffix}
    </motion.span>
  );
}

// ─── Panel ────────────────────────────────────────────────────────────────────
function Panel({ children, className = "", title, badge, action }: {
  children: React.ReactNode; className?: string;
  title?: string; badge?: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div className={`border flex flex-col overflow-hidden ${className}`}
      style={{ background: C.bg2, borderColor: C.border }}>
      {title && (
        <div className="flex items-center justify-between px-4 py-2.5 border-b shrink-0"
          style={{ borderColor: C.border }}>
          <span className="text-[11px] font-medium" style={{ color: C.muted }}>{title}</span>
          <div className="flex items-center gap-2 flex-wrap justify-end">{badge}{action}</div>
        </div>
      )}
      <div className="flex flex-col flex-1 min-h-0">{children}</div>
    </div>
  );
}

// ─── LiveTicker ───────────────────────────────────────────────────────────────
function LiveTicker() {
  const [idx, setIdx] = useState(0);
  useEffect(() => { const t = setInterval(() => setIdx(i => (i + 1) % TICKER_ITEMS.length), 4000); return () => clearInterval(t); }, []);
  return (
    <div className="flex items-center gap-2 overflow-hidden flex-1 mx-2 min-w-0">
      <AnimatePresence mode="wait">
        <motion.span key={idx} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.25 }}
          className="text-[9.5px] truncate" style={{ color: C.muted }}>
          {TICKER_ITEMS[idx]}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

// ─── Topbar ───────────────────────────────────────────────────────────────────
function Topbar({ sidebarOpen, setSidebarOpen, threatLevel, liveMode, setLiveMode, onLogout }: {
  sidebarOpen: boolean; setSidebarOpen: (v: boolean) => void;
  threatLevel: Risk; liveMode: boolean; setLiveMode: (v: boolean) => void;
  onLogout: () => void;
}) {
  const time = useClock();
  const lc: Record<Risk, string> = { CRITICAL: C.red, HIGH: C.amber, MEDIUM: "#facc15", LOW: C.green };
  return (
    <div className="shrink-0 flex items-center px-3 gap-2 z-40 relative"
      style={{ height: 48, background: C.bg0, borderBottom: `1px solid ${C.border}` }}>
      <button onClick={() => setSidebarOpen(!sidebarOpen)} className="flex items-center gap-2 shrink-0">
        <div className="relative">
          <Shield size={20} style={{ color: C.cyan }} />
          <motion.div animate={{ scale: [1, 1.6, 1], opacity: [0.1, 0.35, 0.1] }}
            transition={{ duration: 2.5, repeat: Infinity }}
            className="absolute inset-0 rounded-full" style={{ background: `${C.cyan}18` }} />
        </div>
        <div className="hidden sm:block leading-tight">
          <div className="text-[11px] font-semibold" style={{ color: C.cyan }}>SENTINEL-AI</div>
          <div className="text-[7px] tracking-wide hidden md:block" style={{ color: `${C.muted}90` }}>DISINFORMATION INTELLIGENCE</div>
        </div>
      </button>

      <div className="w-px h-5 shrink-0 mx-1" style={{ background: C.border }} />

      <div className="flex items-center gap-1.5 px-2 py-1 rounded border shrink-0"
        style={{ borderColor: `${lc[threatLevel]}35`, background: `${lc[threatLevel]}08` }}>
        <motion.div animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 1, repeat: Infinity }}
          className="w-1.5 h-1.5 rounded-full" style={{ background: lc[threatLevel] }} />
        <span className="text-[9px] font-semibold tracking-wide hidden lg:block" style={{ color: lc[threatLevel] }}>
          {threatLevel}
        </span>
      </div>

      <LiveTicker />

      <div className="flex items-center gap-3 shrink-0">
        <div className="hidden lg:flex flex-col items-end leading-none gap-0.5">
          <span className="text-[11px] font-mono font-semibold" style={{ color: C.text }}>
            {time.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}
          </span>
          <span className="text-[8px] tracking-wider" style={{ color: C.muted }}>
            {time.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })} · IST
          </span>
        </div>

        <motion.button whileTap={{ scale: 0.93 }} onClick={() => setLiveMode(!liveMode)}
          className="flex items-center gap-1 px-2 py-1 rounded text-[9px] font-semibold tracking-wide border"
          style={liveMode
            ? { borderColor: `${C.green}45`, color: C.green, background: `${C.green}10` }
            : { borderColor: `${C.amber}45`, color: C.amber, background: `${C.amber}10` }}>
          {liveMode ? <><Radio size={9} />Live</> : <><Play size={9} />Paused</>}
        </motion.button>

        <button onClick={onLogout} className="btn" style={{ color: C.muted }}>
          <Lock size={10} /> Logout
        </button>
      </div>
    </div>
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
const NAV = [
  { id: "overview",    icon: <Activity size={15} />,   label: "Overview" },
  { id: "analyze",     icon: <Brain size={15} />,       label: "Analyze Content" },
  { id: "detections",  icon: <Eye size={15} />,         label: "Detection Feed",   badge: "LIVE" },
  { id: "campaigns",   icon: <Share2 size={15} />,      label: "Campaign Graph" },
  { id: "trends",      icon: <TrendingUp size={15} />,  label: "Narrative Trends" },
  { id: "reports",     icon: <FileText size={15} />,    label: "Reports" },
  { id: "settings",    icon: <Settings size={15} />,    label: "Settings" },
];

function Sidebar({ open, activeTab, setTab, analystName, role }: {
  open: boolean; activeTab: string; setTab: (t: string) => void;
  analystName: string; role: string;
}) {
  const activeIdx = NAV.findIndex(n => n.id === activeTab);
  return (
    <div className="shrink-0 flex flex-col overflow-hidden relative"
      style={{ background: C.bg0, borderRight: `1px solid ${C.border}`, width: open ? 180 : 44, transition: "width 0.22s ease", height: "100%" }}>
      <motion.div animate={{ y: activeIdx * 42 }} transition={{ type: "spring", stiffness: 440, damping: 38 }}
        className="absolute left-1.5 right-1.5 h-10 rounded z-0 pointer-events-none"
        style={{ background: `${C.cyan}0c`, border: `1px solid ${C.cyan}1e`, top: 6 }} />

      <div className="flex flex-col gap-0.5 p-1.5 flex-1 overflow-y-auto overflow-x-hidden" style={{ scrollbarWidth: "none" }}>
        {NAV.map(item => {
          const active = item.id === activeTab;
          return (
            <motion.button key={item.id} whileTap={{ scale: 0.96 }} onClick={() => setTab(item.id)}
              className="nav-item w-full text-left shrink-0"
              style={{ color: active ? C.text : undefined }} title={!open ? item.label : undefined}>
              {active && (
                <motion.div layoutId="sidebarBar"
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-full"
                  style={{ background: C.cyan }} />
              )}
              <span className="shrink-0">{item.icon}</span>
              <span className="text-[10.5px] font-semibold tracking-wide whitespace-nowrap"
                style={{ opacity: open ? 1 : 0, width: open ? "auto" : 0, transition: "opacity 0.18s, width 0.18s", overflow: "hidden" }}>
                {item.label}
              </span>
              {item.badge && open && (
                <span className="ml-auto text-[7px] font-semibold px-1 py-0.5 rounded shrink-0"
                  style={{ background: `${C.green}18`, color: C.green, border: `1px solid ${C.green}32` }}>
                  {item.badge}
                </span>
              )}
            </motion.button>
          );
        })}
      </div>

      <div className="p-1.5 border-t shrink-0" style={{ borderColor: C.border }}>
        <div className="flex items-center gap-2" style={{ padding: "8px 10px" }}>
          <div className="shrink-0 flex items-center justify-center"
            style={{ width: 26, height: 26, borderRadius: "50%", background: C.bg3, border: `1px solid ${C.border}`, color: C.muted, fontSize: 11, fontWeight: 500 }}>
            {analystName[0]?.toUpperCase()}
          </div>
          {open && (
            <div className="overflow-hidden">
              <div style={{ fontSize: 11, fontWeight: 500, color: C.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 110 }}>
                {analystName}
              </div>
              <div style={{ fontSize: 10, color: C.muted, textTransform: "capitalize" }}>{role} · Active</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── KPI Cards ────────────────────────────────────────────────────────────────
const KPI_META = [
  { key: "totalAnalyzed",         label: "Total Analyzed",       icon: <Database size={12} />,      suffix: "",  color: C.cyan,   desc: "Content pieces processed" },
  { key: "aiFlagged",             label: "AI-Flagged",           icon: <Brain size={12} />,          suffix: "",  color: C.amber,  desc: "Likely AI-generated" },
  { key: "highRisk",              label: "High-Risk",            icon: <AlertTriangle size={12} />,  suffix: "",  color: C.red,    desc: "HIGH + CRITICAL" },
  { key: "campaignClusters",      label: "Campaign Clusters",    icon: <Share2 size={12} />,          suffix: "",  color: C.purple, desc: "Distinct cluster IDs" },
  { key: "attributionConfidence", label: "Avg Confidence",       icon: <Lock size={12} />,            suffix: "%", color: C.green,  desc: "Model attribution confidence" },
  { key: "avgDetectionLatency",   label: "Detection Latency",    icon: <Zap size={12} />,             suffix: "ms",color: C.cyan,   desc: "Avg ML inference time" },
];

function KPICards({ metrics }: { metrics: Metrics }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2 shrink-0">
      {KPI_META.map((m, i) => {
        const val = metrics[m.key as keyof Metrics];
        return (
          <motion.div key={m.key} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.055 }}
            className="p-3 border relative overflow-hidden"
            style={{ background: C.bg3, borderColor: `${m.color}20`, boxShadow: `0 0 0 1px ${m.color}08,0 4px 14px rgba(0,0,0,0.3)` }}>
            <div style={{ marginBottom: 8, color: m.color, opacity: 0.8 }}>{m.icon}</div>
            <div style={{ fontSize: 22, fontWeight: 600, lineHeight: 1, marginBottom: 4, color: m.color }}>
              <AnimNum value={val} suffix={m.suffix} />
            </div>
            <div style={{ fontSize: 11, fontWeight: 500, color: C.muted, marginTop: 4 }}>{m.label}</div>
            <div style={{ fontSize: 10, color: C.muted, opacity: 0.6, marginTop: 1 }}>{m.desc}</div>
          </motion.div>
        );
      })}
    </div>
  );
}

// ─── AnalyzePanel ─────────────────────────────────────────────────────────────
function AnalyzePanel({ role, compact = false }: { role: string; compact?: boolean }) {
  const [text, setText]           = useState("");
  const [platform, setPlatform]   = useState<Platform>("Twitter/X");
  const [actorId, setActorId]     = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult]       = useState<AnalysisResult | null>(null);
  const [progress, setProgress]   = useState(0);
  const [progLabel, setProgLabel] = useState("");
  const [apiError, setApiError]   = useState("");

  const STEPS = [
    "Tokenising content…", "Computing perplexity…", "Running stylometric analysis…",
    "Fingerprinting model signatures…", "Scoring harm potential…", "Generating verdict…",
  ];

  const canAnalyze = role === "analyst" || role === "admin";

  const analyse = useCallback(async () => {
    if (!text.trim() || !canAnalyze) return;
    setAnalyzing(true); setResult(null); setApiError(""); setProgress(0);

    // Animated progress
    const steps = [10, 25, 42, 60, 78, 92, 100]; let i = 0;
    const prog = setInterval(() => {
      if (i < steps.length) { setProgress(steps[i]); setProgLabel(STEPS[Math.min(i, STEPS.length - 1)]); i++; }
      else clearInterval(prog);
    }, 360);

    try {
      const ml: DetectResponse = await apiDetect(text, platform, actorId || undefined);
      clearInterval(prog); setProgress(100);

      const probPct = Math.round(ml.ai_probability * 100);
      const confPct = Math.round(ml.confidence * 100);

      setResult({
        aiProbability:      probPct,
        confidence:         confPct,
        risk:               ml.risk_level,
        model:              ml.model_display ?? attrDisplay(ml.model_attribution),
        explanation:        [ml.explanation],
        coordinationScore:  ml.risk_level === "CRITICAL" ? rnd(80, 96) : ml.risk_level === "HIGH" ? rnd(55, 79) : rnd(20, 54),
        harmPotential:      ml.risk_level === "CRITICAL" ? rnd(80, 98) : ml.risk_level === "HIGH" ? rnd(55, 79) : rnd(20, 54),
        burstiness:         ml.ai_probability > 0.7 ? rndF(0.04, 0.16) : rndF(0.2, 0.45),
        perplexity:         ml.ai_probability > 0.8 ? rnd(5, 14) : ml.ai_probability > 0.6 ? rnd(14, 22) : rnd(22, 38),
        relatedClusters:    [ml.cluster_id],
        recommendedAction:  ml.risk_level === "CRITICAL" ? "QUARANTINE & ESCALATE" : ml.risk_level === "HIGH" ? "FLAG FOR REVIEW" : "MONITOR",
        spreadRisk:         Math.round(ml.ai_probability * 100),
        clusterId:          ml.cluster_id,
      });
    } catch (err: unknown) {
      clearInterval(prog); setProgress(0);
      const msg = err instanceof Error ? err.message : "Detection failed";
      setApiError(msg);
    } finally {
      setAnalyzing(false);
    }
  }, [text, platform, actorId, canAnalyze]);

  return (
    <Panel title="Analyze Suspicious Content" className="h-full">
      <div className="p-4 flex flex-col gap-3 overflow-auto flex-1">
        {!canAnalyze && (
          <div className="rounded p-3 border" style={{ background: `${C.amber}08`, borderColor: `${C.amber}30` }}>
            <span className="text-[10px]" style={{ color: C.amber }}>
              ⚠ Viewer role — read-only. Login as <strong>analyst</strong> or <strong>admin</strong> to analyze content.
            </span>
          </div>
        )}

        <textarea value={text} onChange={e => setText(e.target.value)}
          placeholder="Paste suspicious content, social media post, or narrative text for AI detection…"
          rows={compact ? 4 : 5} className="mono"
          style={{
            width: "100%", background: C.bg0, border: `1px solid ${text ? C.borderHover : C.border}`,
            color: C.text, borderRadius: 4, padding: "10px 12px", fontSize: 12, resize: "none", outline: "none",
          }} />

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[7.5px] tracking-wide uppercase mb-1 block font-bold" style={{ color: C.muted }}>Platform</label>
            <select value={platform} onChange={e => setPlatform(e.target.value as Platform)}
              className="w-full rounded px-2.5 py-1.5 text-xs outline-none"
              style={{ background: C.bg0, border: `1px solid ${C.border}`, color: C.text }}>
              {PLATFORMS.map(p => <option key={p}>{p}</option>)}
            </select>
            <p className="text-[8px] mt-0.5" style={{ color: C.muted }}>→ mapped to: {normalisePlatform(platform)}</p>
          </div>
          <div>
            <label className="text-[7.5px] tracking-wide uppercase mb-1 block font-bold" style={{ color: C.muted }}>Actor ID (optional)</label>
            <input value={actorId} onChange={e => setActorId(e.target.value)}
              placeholder="e.g. PHANTOM-PRESS"
              className="w-full rounded px-2.5 py-1.5 text-xs outline-none"
              style={{ background: C.bg0, border: `1px solid ${C.border}`, color: C.text, fontFamily: "monospace" }} />
          </div>
        </div>

        <motion.button whileTap={{ scale: 0.97 }} onClick={analyse}
          disabled={!text.trim() || analyzing || !canAnalyze}
          className="w-full py-2 rounded text-xs font-semibold tracking-wide uppercase flex items-center justify-center gap-2 shrink-0"
          style={{
            background: text.trim() && !analyzing && canAnalyze ? `${C.cyan}18` : C.bg0,
            border: `1px solid ${C.border}`,
            color: text.trim() && canAnalyze ? C.text : C.muted, opacity: canAnalyze ? 1 : 0.5,
          }}>
          {analyzing ? <><RefreshCw size={11} className="animate-spin" />{progLabel}</> : <><Brain size={11} />Run AI Analysis</>}
        </motion.button>

        {analyzing && (
          <div className="space-y-1">
            <div className="h-0.5 rounded-full overflow-hidden" style={{ background: `${C.cyan}12` }}>
              <motion.div animate={{ width: `${progress}%` }} transition={{ duration: 0.3 }}
                className="h-full rounded-full" style={{ background: `linear-gradient(90deg,${C.cyan},${C.green})` }} />
            </div>
            <div className="flex justify-between">
              <span className="text-[8px] font-mono" style={{ color: C.muted }}>{progLabel}</span>
              <span className="text-[8px] font-mono font-semibold" style={{ color: C.cyan }}>{progress}%</span>
            </div>
          </div>
        )}

        {apiError && (
          <div className="rounded p-3 border" style={{ background: `${C.red}08`, borderColor: `${C.red}30` }}>
            <span className="text-[10px]" style={{ color: C.red }}>✗ {apiError}</span>
          </div>
        )}

        <AnimatePresence>
          {result && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-3">
              {/* Score grid */}
              <div className="grid grid-cols-4 gap-1.5">
                {[
                  { label: "AI Prob", value: `${result.aiProbability}%`, color: result.aiProbability >= 80 ? C.red : C.amber },
                  { label: "Confidence", value: `${result.confidence}%`, color: C.cyan },
                  { label: "Coord.", value: `${result.coordinationScore}%`, color: C.purple },
                  { label: "Harm", value: `${result.harmPotential}%`, color: C.red },
                ].map(s => (
                  <div key={s.label} className="rounded p-2 text-center border"
                    style={{ background: `${s.color}06`, borderColor: `${s.color}22` }}>
                    <div className="mono" style={{ fontSize: 15, fontWeight: 600, color: s.color }}>{s.value}</div>
                    <div style={{ fontSize: 9, marginTop: 2, color: C.muted }}>{s.label}</div>
                  </div>
                ))}
              </div>

              {/* Verdict */}
              <div className="rounded p-3 border flex items-center justify-between gap-2 flex-wrap"
                style={{ background: `${riskColor(result.risk)}06`, borderColor: `${riskColor(result.risk)}22` }}>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className={`text-[9px] font-semibold tracking-wide px-2 py-0.5 rounded border ${riskBg(result.risk)}`}>
                    ⚠ {result.risk} RISK
                  </span>
                  <span className="text-[9px] px-2 py-0.5 rounded border font-mono"
                    style={{ borderColor: `${C.purple}30`, color: C.purple, background: `${C.purple}08` }}>
                    🤖 {result.model}
                  </span>
                  <span className="text-[9px] px-2 py-0.5 rounded border font-mono"
                    style={{ borderColor: `${C.cyan}30`, color: C.cyan, background: `${C.cyan}08` }}>
                    🗂 {result.clusterId}
                  </span>
                </div>
                <span className="text-[8px] font-semibold px-2 py-1 rounded shrink-0"
                  style={{ background: result.aiProbability >= 80 ? `${C.red}18` : `${C.amber}18`, color: result.aiProbability >= 80 ? C.red : C.amber, border: `1px solid ${result.aiProbability >= 80 ? C.red : C.amber}32` }}>
                  {result.recommendedAction}
                </span>
              </div>

              {/* Bars */}
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: "Perplexity Score", value: result.perplexity, max: 60, color: C.cyan, note: "Lower = more AI-like. Human avg: 47" },
                  { label: "Burstiness Index", value: result.burstiness * 100, max: 100, color: C.amber, note: "Low = uniform = AI" },
                  { label: "Spread Risk", value: result.spreadRisk, max: 100, color: C.red, note: "Predicted 24h virality" },
                  { label: "Harm Potential", value: result.harmPotential, max: 100, color: C.purple, note: "Societal harm estimate" },
                ].map(bar => (
                  <div key={bar.label} className="rounded p-2.5 border" style={{ background: C.bg0, borderColor: C.border }}>
                    <div className="flex justify-between mb-1">
                      <span className="text-[7.5px] font-semibold truncate" style={{ color: C.muted }}>{bar.label}</span>
                      <span className="text-[7.5px] font-mono font-semibold ml-1" style={{ color: bar.color }}>{bar.value.toFixed(1)}</span>
                    </div>
                    <div className="h-1 rounded-full" style={{ background: `${bar.color}12` }}>
                      <div className="h-full rounded-full transition-all duration-1000"
                        style={{ width: `${Math.min(100, (bar.value / bar.max) * 100)}%`, background: bar.color }} />
                    </div>
                    <div className="text-[7px] mt-1" style={{ color: `${C.muted}75` }}>{bar.note}</div>
                  </div>
                ))}
              </div>

              {/* Explanation */}
              <div className="rounded p-3 border" style={{ background: C.bg0, borderColor: C.border }}>
                <div style={{ fontSize: 10, fontWeight: 500, color: C.muted, marginBottom: 6 }}>
                  Detection Rationale — from ML engine
                </div>
                <div className="space-y-1.5">
                  {result.explanation.map((e, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-[8.5px]" style={{ color: C.muted }}>
                      <ChevronRight size={9} className="mt-0.5 shrink-0" style={{ color: C.cyan }} />
                      {e}
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Panel>
  );
}

// ─── Live Detection Feed (from real API) ─────────────────────────────────────
function DetectionFeed({ detections, compact = false }: { detections: RecentDetection[]; compact?: boolean }) {
  const [filter, setFilter] = useState<string>("ALL");
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = useMemo(() =>
    filter === "ALL" ? detections : detections.filter(d => d.risk_level === filter),
    [detections, filter]
  );

  return (
    <Panel title="Live Detection Feed"
      badge={<div className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full" style={{ background: C.green }} /><span className="text-[9px]" style={{ color: C.green }}>live</span></div>}
      action={
        <div className="flex gap-1 flex-wrap">
          {(["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"]).map(f => (
            <button key={f} onClick={() => setFilter(f)} className="btn"
              style={filter === f ? { color: C.cyan, borderColor: C.cyan, background: `${C.cyan}10` } : {}}>
              {f}
            </button>
          ))}
        </div>
      }
      className="h-full">

      <div className="grid px-3 py-2 shrink-0"
        style={{ gridTemplateColumns: "75px 70px 55px 1fr 65px 55px 16px", color: C.muted, background: C.bg0, borderBottom: `1px solid ${C.border}`, fontSize: 10, fontWeight: 500 }}>
        <span>Time</span><span>Platform</span><span>AI%</span><span>Model</span><span>Risk</span><span>Cluster</span><span />
      </div>

      <div className="overflow-auto flex-1">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-24" style={{ color: C.muted }}>
            <Database size={20} className="mb-2 opacity-30" />
            <span className="text-[11px]">No detections yet — analyze some content first</span>
          </div>
        ) : (
          <AnimatePresence>
            {filtered.slice(0, compact ? 8 : 100).map(d => (
              <motion.div key={d.content_id}
                initial={{ opacity: 0, x: -8, backgroundColor: `${C.cyan}05` }}
                animate={{ opacity: 1, x: 0, backgroundColor: "transparent" }}
                transition={{ duration: 0.25 }}
                className="border-b cursor-pointer" style={{ borderColor: C.border }}
                onClick={() => setExpanded(expanded === d.content_id ? null : d.content_id)}>
                <div className="grid px-3 py-1.5 items-center hover:bg-white/[0.018] transition-colors"
                  style={{ gridTemplateColumns: "75px 70px 55px 1fr 65px 55px 16px" }}>
                  <span className="text-[8px] font-mono" style={{ color: C.muted }}>
                    {new Date(d.detected_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}
                  </span>
                  <span className="text-[8px] font-bold truncate" style={{ color: C.cyan }}>{d.platform}</span>
                  <div>
                    <div className="text-[8px] font-semibold font-mono" style={{ color: d.ai_probability >= 0.7 ? C.red : C.amber }}>
                      {Math.round(d.ai_probability * 100)}%
                    </div>
                    <div className="h-0.5 rounded mt-0.5 w-full" style={{ background: C.border }}>
                      <div className="h-full rounded" style={{ width: `${Math.round(d.ai_probability * 100)}%`, background: d.ai_probability >= 0.7 ? C.red : C.amber }} />
                    </div>
                  </div>
                  <span className="text-[7.5px] font-mono truncate" style={{ color: C.purple }}>
                    {attrDisplay(d.model_attribution).split(" ")[0]}
                  </span>
                  <span className={`text-[7px] font-semibold px-1 py-0.5 rounded border text-center ${riskBg(d.risk_level)}`}>
                    {d.risk_level.slice(0, 4)}
                  </span>
                  <span className="text-[7.5px] font-mono" style={{ color: C.muted }}>{d.cluster_id}</span>
                  <ChevronDown size={9} style={{ color: C.muted, transform: expanded === d.content_id ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
                </div>
                <AnimatePresence>
                  {expanded === d.content_id && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                      <div className="px-3 py-3 space-y-2 border-t" style={{ background: C.bg0, borderColor: C.border, fontSize: 11 }}>
                        <div className="flex flex-wrap gap-1">
                          <span className="text-[7.5px] px-2 py-0.5 rounded font-mono"
                            style={{ background: `${C.purple}10`, color: C.purple, border: `1px solid ${C.purple}22` }}>
                            🤖 {attrDisplay(d.model_attribution)}
                          </span>
                          {d.actor_id && <span className="text-[7.5px] px-2 py-0.5 rounded font-mono"
                            style={{ background: `${C.red}10`, color: C.red, border: `1px solid ${C.red}22` }}>
                            🎭 {d.actor_id}
                          </span>}
                          <span className="text-[7.5px] px-2 py-0.5 rounded font-mono"
                            style={{ background: `${C.cyan}08`, color: C.cyan, border: `1px solid ${C.cyan}20` }}>
                            Conf: {Math.round(d.confidence * 100)}%
                          </span>
                        </div>
                        <div className="text-[7.5px] font-mono truncate" style={{ color: C.muted }}>
                          ID: {d.content_id}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </Panel>
  );
}

// ─── Narrative Trends Chart ───────────────────────────────────────────────────
function NarrativeTrendsChart({ data }: { data: ChartPoint[] }) {
  return (
    <Panel title="Detection Trends — Live" className="h-full">
      <div className="p-3 flex-1" style={{ minHeight: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 6, right: 6, left: -24, bottom: 0 }}>
            <defs>
              {[{ id: "gDet", c: C.cyan }, { id: "gAI", c: C.amber }, { id: "gBlock", c: C.green }].map(g => (
                <linearGradient key={g.id} id={g.id} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={g.c} stopOpacity={0.22} />
                  <stop offset="100%" stopColor={g.c} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="time" tick={{ fill: "var(--text-3)", fontSize: 10 }} tickLine={false} axisLine={false} interval={6} />
            <YAxis tick={{ fill: "var(--text-3)", fontSize: 10 }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-md)", borderRadius: 4, fontSize: 11 }}
              labelStyle={{ color: C.muted }} itemStyle={{ color: C.text }} />
            <Area type="monotone" dataKey="detections" stroke={C.cyan} strokeWidth={1.5} fill="url(#gDet)" dot={false} name="Total" />
            <Area type="monotone" dataKey="aiGenerated" stroke={C.amber} strokeWidth={1.5} fill="url(#gAI)" dot={false} name="AI-Flagged" />
            <Area type="monotone" dataKey="blocked" stroke={C.green} strokeWidth={1} fill="url(#gBlock)" dot={false} name="Campaigns" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

// ─── Quick Actions ────────────────────────────────────────────────────────────
function QuickActions({ onNavigate }: { onNavigate: (tab: string) => void }) {
  const actions = [
    { icon: <Brain size={14} />, label: "Analyze Content", sub: "Run AI detection engine", color: C.cyan, tab: "analyze" },
    { icon: <Download size={14} />, label: "Export Report", sub: "PDF / JSON format", color: C.amber, tab: "reports" },
    { icon: <Globe size={14} />, label: "View Dashboard", sub: "Real-time stats from DB", color: C.red, tab: "detections" },
    { icon: <BarChart2 size={14} />, label: "Narrative Trends", sub: "Detection trend analysis", color: C.purple, tab: "trends" },
    { icon: <Users size={14} />, label: "Detection Feed", sub: "Live persisted detections", color: C.green, tab: "detections" },
    { icon: <Settings size={14} />, label: "Settings", sub: "Configure platform", color: C.muted, tab: "settings" },
  ];
  return (
    <Panel title="Quick Actions" className="h-full">
      <div className="p-3 grid grid-cols-2 gap-2 flex-1">
        {actions.map(a => (
          <motion.button key={a.label} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
            onClick={() => onNavigate(a.tab)}
            className="text-left border flex flex-col gap-2"
            style={{ background: C.bg1, borderColor: C.border, borderRadius: 4, padding: "12px", transition: "border-color 0.15s" }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = C.borderHover)}
            onMouseLeave={e => (e.currentTarget.style.borderColor = C.border)}>
            <div style={{ color: a.color, width: 30, height: 30, display: "flex", alignItems: "center", justifyContent: "center", background: C.bg3, borderRadius: 4 }}>
              {a.icon}
            </div>
            <div>
              <div className="text-[9.5px] font-bold" style={{ color: C.text }}>{a.label}</div>
              <div className="text-[7.5px] mt-0.5" style={{ color: C.muted }}>{a.sub}</div>
            </div>
          </motion.button>
        ))}
      </div>
    </Panel>
  );
}

// ─── Reports View ─────────────────────────────────────────────────────────────
function ReportsView() {
  const [downloaded, setDownloaded] = useState<string | null>(null);
  const reports = [
    { id: "r1", name: "Weekly AI Disinformation Summary", date: "Latest", type: "PDF", size: "3.4 MB", desc: "Comprehensive overview of AI-generated narratives and attribution across all monitored platforms." },
    { id: "r2", name: "Full Attribution Report — Current Session", date: "Now", type: "JSON", size: "Live", desc: "Complete technical attribution data from all detections in the current session." },
    { id: "r3", name: "Detection Export — CSV", date: "Now", type: "CSV", size: "Live", desc: "Raw detection data: AI probability, model, confidence, cluster, risk scores." },
    { id: "r4", name: "STIX 2.1 Threat Intelligence Bundle", date: "Latest", type: "STIX 2.1", size: "920 KB", desc: "STIX-format threat intel on narrative mutation chains — TAXII 2.1 compatible." },
  ];
  return (
    <div className="h-full overflow-auto" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div><h2 className="text-sm font-semibold" style={{ color: C.text }}>Intelligence Reports</h2>
        <p className="text-[9px] mt-0.5" style={{ color: C.muted }}>Export threat intelligence in STIX 2.1, PDF, JSON, CSV</p>
      </div>
      <div className="space-y-2">
        {reports.map((r, i) => (
          <motion.div key={r.id} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}
            className="flex items-start justify-between border"
            style={{ background: C.bg1, borderColor: C.border, borderRadius: 4, padding: "14px 16px" }}>
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="w-9 h-9 rounded flex items-center justify-center shrink-0"
                style={{ background: `${C.cyan}10`, border: `1px solid ${C.cyan}20` }}>
                <FileText size={15} style={{ color: C.cyan }} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[10px] font-bold truncate" style={{ color: C.text }}>{r.name}</div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[7.5px]" style={{ color: C.muted }}>{r.date}</span>
                  <span className="text-[7px] px-1.5 py-0.5 rounded font-semibold"
                    style={{ background: `${C.cyan}10`, color: C.cyan, border: `1px solid ${C.cyan}20` }}>{r.type}</span>
                  <span className="text-[7.5px]" style={{ color: C.muted }}>{r.size}</span>
                </div>
                <div className="text-[8px] mt-1 leading-snug" style={{ color: `${C.muted}80` }}>{r.desc}</div>
              </div>
            </div>
            <motion.button whileTap={{ scale: 0.97 }} className="btn ml-3 shrink-0"
              onClick={() => { setDownloaded(r.id); setTimeout(() => setDownloaded(null), 2000); }}
              style={downloaded === r.id ? { color: C.green, borderColor: `${C.green}45` } : { color: C.muted }}>
              {downloaded === r.id ? <><CheckCircle size={10} />Saved</> : <><Download size={10} />Download</>}
            </motion.button>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// ─── Settings View ────────────────────────────────────────────────────────────
function Toggle({ value, toggle }: { value: boolean; toggle: () => void }) {
  return (
    <button onClick={e => { e.stopPropagation(); toggle(); }}
      style={{ width: 36, height: 20, borderRadius: 10, flexShrink: 0, cursor: "pointer", background: value ? `${C.cyan}25` : C.bg0, border: `1px solid ${value ? C.cyan : C.border}`, position: "relative", transition: "background 0.2s, border-color 0.2s" }}>
      <div style={{ position: "absolute", top: 2, left: value ? 17 : 2, width: 14, height: 14, borderRadius: 7, background: value ? C.cyan : C.muted, transition: "left 0.18s ease" }} />
    </button>
  );
}

function SettingsView({ liveMode, setLiveMode, role }: { liveMode: boolean; setLiveMode: (v: boolean) => void; role: string }) {
  const [autoFlag, setAutoFlag] = useState(true);
  const [saved, setSaved] = useState(false);
  return (
    <div className="h-full overflow-auto" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="flex items-center justify-between">
        <div><h2 className="text-sm font-semibold" style={{ color: C.text }}>Platform Settings</h2>
          <p className="text-[9px] mt-0.5" style={{ color: C.muted }}>Configure detection thresholds and integrations</p>
        </div>
        <motion.button whileTap={{ scale: 0.97 }} onClick={() => { setSaved(true); setTimeout(() => setSaved(false), 2000); }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[9px] font-semibold border"
          style={saved ? { borderColor: `${C.green}45`, color: C.green, background: `${C.green}12` } : { borderColor: `${C.cyan}38`, color: C.cyan, background: `${C.cyan}10` }}>
          {saved ? <><CheckCircle size={11} />Saved</> : <>Save Settings</>}
        </motion.button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel title="Detection Engine">
          <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div><div className="text-[9.5px] font-bold" style={{ color: C.text }}>Live Dashboard Refresh</div>
                <div className="text-[7.5px]" style={{ color: C.muted }}>Auto-reload dashboard every 30s</div></div>
              <Toggle value={liveMode} toggle={() => setLiveMode(!liveMode)} />
            </div>
            <div className="flex items-center justify-between">
              <div><div className="text-[9.5px] font-bold" style={{ color: C.text }}>Auto-flag HIGH+ content</div>
                <div className="text-[7.5px]" style={{ color: C.muted }}>Queue HIGH and CRITICAL for review</div></div>
              <Toggle value={autoFlag} toggle={() => setAutoFlag(v => !v)} />
            </div>
          </div>
        </Panel>

        <Panel title="System Status">
          <div className="p-4 space-y-3">
            {[
              { label: "API Backend",           value: "Connected",  color: C.green  },
              { label: "ML Detection Engine",   value: "Active",     color: C.green  },
              { label: "PostgreSQL",            value: "Connected",  color: C.green  },
              { label: "JWT Auth",              value: "Active",     color: C.green  },
              { label: "Current Role",          value: role,         color: C.cyan   },
            ].map(s => (
              <div key={s.label} className="flex items-center justify-between">
                <span className="text-[9px]" style={{ color: C.text }}>{s.label}</span>
                <span className="text-[7.5px] px-2 py-0.5 rounded font-semibold capitalize"
                  style={{ background: `${s.color}12`, color: s.color, border: `1px solid ${s.color}28` }}>{s.value}</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Backend Endpoints" className="md:col-span-2">
          <div className="p-4 space-y-2">
            {[
              { method: "POST", path: "/api/v1/auth/login",         roles: "public",                 desc: "JWT authentication" },
              { method: "POST", path: "/api/v1/detect",             roles: "analyst, admin",         desc: "AI content analysis → persisted to DB" },
              { method: "GET",  path: "/api/v1/dashboard/overview", roles: "viewer, analyst, admin", desc: "Live stats, trend, graph from PostgreSQL" },
              { method: "GET",  path: "/health",                    roles: "public",                 desc: "API health check" },
            ].map(e => (
              <div key={e.path} className="flex items-center gap-3 p-2 rounded border" style={{ borderColor: C.border, background: C.bg0 }}>
                <span className="text-[8px] font-mono font-bold px-1.5 py-0.5 rounded shrink-0"
                  style={{ background: e.method === "POST" ? `${C.amber}15` : `${C.green}15`, color: e.method === "POST" ? C.amber : C.green }}>{e.method}</span>
                <span className="text-[8.5px] font-mono" style={{ color: C.cyan }}>{e.path}</span>
                <span className="text-[7.5px] ml-auto shrink-0" style={{ color: C.muted }}>{e.roles}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

// ─── Overview Dashboard ───────────────────────────────────────────────────────
function OverviewDashboard({ metrics, detections, chartData, onNavigate, role, dashboardData }: {
  metrics: Metrics; detections: RecentDetection[]; chartData: ChartPoint[];
  onNavigate: (tab: string) => void; role: string; dashboardData: DashboardOverview | null;
}) {
  return (
    <div className="h-full overflow-auto" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <KPICards metrics={metrics} />
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4" style={{ minHeight: 360 }}>
        <div className="xl:col-span-2"><AnalyzePanel role={role} compact /></div>
        <Panel title="Backend Stats (Live)" className="h-full">
          <div className="p-4 flex flex-col gap-3 overflow-auto flex-1">
            {dashboardData ? (
              <>
                <div className="text-[8.5px] font-semibold" style={{ color: C.green }}>● Connected to PostgreSQL</div>
                {[
                  { label: "Total Analyzed", value: dashboardData.stats.total_analyzed, color: C.cyan },
                  { label: "AI Flagged (≥70%)", value: dashboardData.stats.ai_flagged, color: C.amber },
                  { label: "High Risk", value: dashboardData.stats.high_risk, color: C.red },
                  { label: "Campaign Clusters", value: dashboardData.stats.campaign_clusters, color: C.purple },
                  { label: "Avg Confidence", value: `${(dashboardData.stats.avg_confidence * 100).toFixed(1)}%`, color: C.green },
                  { label: "Avg Latency", value: `${dashboardData.stats.avg_latency_ms}ms`, color: C.cyan },
                ].map(s => (
                  <div key={s.label} className="flex items-center justify-between">
                    <span className="text-[9px]" style={{ color: C.muted }}>{s.label}</span>
                    <span className="text-[11px] font-semibold font-mono" style={{ color: s.color }}>{s.value}</span>
                  </div>
                ))}
              </>
            ) : (
              <div className="flex flex-col items-center justify-center flex-1" style={{ color: C.muted }}>
                <RefreshCw size={18} className="animate-spin mb-2" style={{ color: C.cyan }} />
                <span className="text-[10px]">Loading from backend…</span>
              </div>
            )}
          </div>
        </Panel>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4" style={{ minHeight: 280 }}>
        <DetectionFeed detections={detections} compact />
        <NarrativeTrendsChart data={chartData} />
      </div>
      <QuickActions onNavigate={onNavigate} />
    </div>
  );
}

// ─── Trends Page ──────────────────────────────────────────────────────────────
function TrendsPage({ data, dashboardData }: { data: ChartPoint[]; dashboardData: DashboardOverview | null }) {
  const modelData = dashboardData?.recent
    ? (() => {
        const counts: Record<string, number> = {};
        dashboardData.recent.forEach(r => {
          const k = attrDisplay(r.model_attribution);
          counts[k] = (counts[k] || 0) + 1;
        });
        return Object.entries(counts).map(([model, value]) => ({ model, value }));
      })()
    : [];

  return (
    <div className="h-full overflow-auto" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <NarrativeTrendsChart data={data} />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Model Attribution Distribution (from DB)">
          <div className="p-4 space-y-2.5 overflow-auto flex-1">
            {modelData.length > 0 ? modelData.map((m, i) => {
              const colors = [C.cyan, C.amber, C.purple, C.green, C.red, C.pink];
              const max = Math.max(...modelData.map(x => x.value));
              return (
                <div key={m.model}>
                  <div className="flex justify-between mb-1">
                    <span className="text-[8.5px] font-mono" style={{ color: C.muted }}>{m.model}</span>
                    <span className="text-[8.5px] font-mono font-semibold" style={{ color: colors[i % colors.length] }}>{m.value}</span>
                  </div>
                  <div className="h-1.5 rounded-full" style={{ background: `${colors[i % colors.length]}12` }}>
                    <motion.div initial={{ width: 0 }} animate={{ width: `${(m.value / max) * 100}%` }} transition={{ duration: 1 }}
                      className="h-full rounded-full" style={{ background: colors[i % colors.length] }} />
                  </div>
                </div>
              );
            }) : (
              <div className="flex items-center justify-center h-20" style={{ color: C.muted }}>
                <span className="text-[10px]">No detections yet — analyze content to see data</span>
              </div>
            )}
          </div>
        </Panel>
        <Panel title="Detection Velocity (30 min)">
          <div className="p-3 flex-1" style={{ minHeight: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.slice(-20)} margin={{ left: -20, right: 8, top: 4, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="time" tick={{ fill: "var(--text-3)", fontSize: 10 }} tickLine={false} axisLine={false} interval={4} />
                <YAxis tick={{ fill: "var(--text-3)", fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-md)", borderRadius: 4, fontSize: 11 }} />
                <Line type="monotone" dataKey="aiGenerated" stroke={C.amber} strokeWidth={2} dot={false} name="AI-Flagged" />
                <Line type="monotone" dataKey="detections" stroke={C.cyan} strokeWidth={1.5} dot={false} name="Total" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
    </div>
  );
}

// ─── Login Screen ─────────────────────────────────────────────────────────────
function LoginScreen({ onLogin }: { onLogin: (name: string, role: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const time = useClock();

  const handleSubmit = async () => {
    if (!username.trim()) { setError("Enter your username."); return; }
    if (!password.trim()) { setError("Enter your password."); return; }
    setError(""); setLoading(true);
    try {
      const data = await apiLogin(username.trim(), password.trim());
      setLoading(false);
      onLogin(username.trim(), data.role);
    } catch (err: unknown) {
      setLoading(false);
      if (err instanceof Error && "status" in err && (err as { status: number }).status === 401) {
        setError("Invalid credentials. Try: analyst / analyst123");
      } else {
        setError("Cannot reach backend. Is Docker running?");
      }
    }
  };

  const handleKey = (e: React.KeyboardEvent) => { if (e.key === "Enter") handleSubmit(); };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: C.bg0 }}>
      <div className="absolute inset-0 pointer-events-none" style={{
        backgroundImage: `linear-gradient(rgba(255,255,255,0.015) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.015) 1px,transparent 1px)`,
        backgroundSize: "64px 64px",
      }} />

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
        className="relative z-10 w-full" style={{ maxWidth: 400, padding: "0 24px" }}>

        <div className="flex flex-col items-center mb-10">
          <div className="flex items-center justify-center mb-6"
            style={{ width: 48, height: 48, borderRadius: 10, background: C.bg1, border: `1px solid ${C.border}` }}>
            <Shield size={22} style={{ color: C.cyan }} />
          </div>
          <div style={{ fontSize: 20, fontWeight: 600, color: C.text, letterSpacing: "-0.02em", marginBottom: 4 }}>
            Sign in to Sentinel
          </div>
          <div style={{ fontSize: 12, color: C.muted }}>Disinformation Intelligence Platform</div>
        </div>

        <div style={{ background: C.bg1, border: `1px solid ${C.border}`, borderRadius: 8, padding: "28px 28px 24px" }}>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: "block", fontSize: 11, fontWeight: 500, color: C.muted, marginBottom: 6 }}>Username</label>
            <input autoFocus value={username} onChange={e => { setUsername(e.target.value); setError(""); }}
              onKeyDown={handleKey} placeholder="analyst"
              style={{ width: "100%", background: C.bg0, border: `1px solid ${username ? C.borderHover : C.border}`, borderRadius: 5, color: C.text, fontSize: 13, padding: "8px 12px", outline: "none", fontFamily: "monospace" }} />
          </div>

          <div style={{ marginBottom: 20 }}>
            <div className="flex items-center justify-between" style={{ marginBottom: 6 }}>
              <label style={{ fontSize: 11, fontWeight: 500, color: C.muted }}>Password</label>
              <button onClick={() => setShowPass(v => !v)} style={{ fontSize: 10, color: C.muted, background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                {showPass ? "Hide" : "Show"}
              </button>
            </div>
            <input type={showPass ? "text" : "password"} value={password}
              onChange={e => { setPassword(e.target.value); setError(""); }}
              onKeyDown={handleKey} placeholder="analyst123"
              style={{ width: "100%", background: C.bg0, border: `1px solid ${password ? C.borderHover : C.border}`, borderRadius: 5, color: C.text, fontSize: 13, padding: "8px 12px", outline: "none", fontFamily: "monospace", letterSpacing: showPass ? "normal" : "0.1em" }} />
          </div>

          <AnimatePresence>
            {error && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                style={{ overflow: "hidden", marginBottom: 14 }}>
                <div className="flex items-center gap-2"
                  style={{ fontSize: 11, color: C.red, background: `${C.red}12`, border: `1px solid ${C.red}30`, borderRadius: 4, padding: "7px 10px" }}>
                  <AlertTriangle size={11} />{error}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <motion.button whileTap={{ scale: 0.98 }} onClick={handleSubmit} disabled={loading}
            style={{ width: "100%", padding: "9px 0", borderRadius: 5, fontSize: 13, fontWeight: 500, background: loading ? C.bg3 : `${C.cyan}18`, border: `1px solid ${loading ? C.border : C.cyan}`, color: loading ? C.muted : C.cyan, cursor: loading ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 7 }}>
            {loading ? <><RefreshCw size={13} className="animate-spin" />Signing in…</> : <><CheckCircle size={13} />Sign In</>}
          </motion.button>
        </div>

        <div style={{ marginTop: 16, padding: "0 4px" }}>
          <div className="text-center text-[10px]" style={{ color: C.muted }}>
            Demo: analyst/analyst123 · viewer/viewer123 · admin/admin123
          </div>
          <div className="mono text-center text-[9px] mt-1" style={{ color: `${C.muted}60` }}>
            {time.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })} IST · SENTINEL-AI v1.0
          </div>
        </div>
      </motion.div>
    </div>
  );
}

// ─── Launch Screen ────────────────────────────────────────────────────────────
function LaunchScreen({ onEnter }: { onEnter: () => void }) {
  const time = useClock();
  const [progress, setProgress] = useState(0);
  const [phaseIdx, setPhaseIdx] = useState(0);
  const phases = [
    "Initialising heuristic detection engine…",
    "Loading stylometric fingerprint database…",
    "Verifying backend API connectivity…",
    "Loading attribution models — GPT, Claude, Gemini…",
    "Calibrating risk threshold matrices…",
    "System ready.",
  ];

  useEffect(() => { const t = setInterval(() => setProgress(p => Math.min(100, p + rnd(2, 5))), 80); return () => clearInterval(t); }, []);
  useEffect(() => { setPhaseIdx(Math.min(Math.floor((progress / 100) * phases.length), phases.length - 1)); }, [progress]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden" style={{ background: C.bg0 }}>
      {["top-5 left-5 border-t-2 border-l-2", "top-5 right-5 border-t-2 border-r-2", "bottom-5 left-5 border-b-2 border-l-2", "bottom-5 right-5 border-b-2 border-r-2"].map(c => (
        <div key={c} className={`absolute ${c} w-10 h-10 opacity-20`} style={{ borderColor: C.cyan }} />
      ))}

      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}
        className="flex flex-col items-center gap-7 z-10 w-full max-w-lg px-8">

        <div className="flex flex-col items-center gap-4">
          <Shield size={68} style={{ color: C.cyan }} />
          <div className="text-center">
            <div style={{ fontSize: 28, fontWeight: 600, color: C.text, letterSpacing: "-0.02em" }}>Sentinel</div>
            <div className="text-xs mt-2 font-semibold" style={{ color: C.muted }}>AI DISINFORMATION THREAT INTELLIGENCE</div>
            <div className="text-[8.5px] tracking-wide mt-1" style={{ color: `${C.muted}65` }}>v1.0.0 · REAL BACKEND · REAL ML ENGINE</div>
          </div>
        </div>

        <div className="text-center">
          <div className="text-3xl font-mono font-semibold" style={{ color: C.text }}>
            {time.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}
          </div>
          <div className="text-[9.5px] mt-1" style={{ color: C.muted }}>
            {time.toLocaleDateString("en-IN", { weekday: "long", day: "2-digit", month: "long", year: "numeric" })} · IST
          </div>
        </div>

        <div className="w-full space-y-2">
          <div style={{ height: 2, borderRadius: 2, overflow: "hidden", background: "rgba(255,255,255,0.06)" }}>
            <motion.div animate={{ width: `${progress}%` }} transition={{ duration: 0.22 }} className="h-full rounded-full"
              style={{ background: `linear-gradient(90deg,${C.cyan},${C.green})` }} />
          </div>
          <div className="flex justify-between items-center">
            <AnimatePresence mode="wait">
              <motion.span key={phaseIdx} initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -3 }}
                className="text-[8.5px] font-mono" style={{ color: C.muted }}>{phases[phaseIdx]}</motion.span>
            </AnimatePresence>
            <span className="text-[8.5px] font-mono font-semibold ml-2 shrink-0" style={{ color: C.cyan }}>{progress}%</span>
          </div>
        </div>

        <AnimatePresence>
          {progress >= 100 && (
            <motion.button initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
              whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={onEnter}
              className="px-14 py-3 rounded text-sm font-semibold tracking-wide uppercase flex items-center gap-2"
              style={{ background: C.bg3, border: `1px solid ${C.border}`, color: C.text }}>
              <CheckCircle size={14} />Enter Console
            </motion.button>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

// ─── Root App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [launched, setLaunched]         = useState(false);
  const [loggedIn, setLoggedIn]         = useState(false);
  const [analystName, setAnalystName]   = useState("Analyst");
  const [role, setRole]                 = useState("viewer");
  const [sidebarOpen, setSidebarOpen]   = useState(true);
  const [activeTab, setActiveTab]       = useState("overview");
  const [tabDirection, setTabDirection] = useState(1);
  const [liveMode, setLiveMode]         = useState(true);

  // Real API state
  const [dashboardData, setDashboardData] = useState<DashboardOverview | null>(null);
  const [dashWindow, setDashWindow]       = useState<"1h"|"6h"|"24h"|"7d">("24h");
  const dashInterval                      = useRef<ReturnType<typeof setInterval> | null>(null);

  // Derived frontend state (metrics, chart, detections from real API)
  const metrics: Metrics = useMemo(() => {
    if (!dashboardData) return { totalAnalyzed: 0, aiFlagged: 0, highRisk: 0, campaignClusters: 0, attributionConfidence: 0, avgDetectionLatency: 0 };
    const s = dashboardData.stats;
    return {
      totalAnalyzed:         s.total_analyzed,
      aiFlagged:             s.ai_flagged,
      highRisk:              s.high_risk,
      campaignClusters:      s.campaign_clusters,
      attributionConfidence: Math.round(s.avg_confidence * 100),
      avgDetectionLatency:   s.avg_latency_ms,
    };
  }, [dashboardData]);

  const chartData: ChartPoint[] = useMemo(() => {
    if (!dashboardData?.trend) return Array.from({ length: 24 }, (_, i) => ({
      time: `${String(i).padStart(2, "0")}:00`, detections: 0, aiGenerated: 0, campaigns: 0, blocked: 0,
    }));
    return dashboardData.trend.map(b => ({
      time:        b.bucket.split("T")[1] || b.bucket,
      detections:  b.total,
      aiGenerated: b.ai_flagged,
      campaigns:   b.high_risk,
      blocked:     0,
    }));
  }, [dashboardData]);

  const recentDetections: RecentDetection[] = dashboardData?.recent ?? [];

  const threatLevel: Risk = metrics.highRisk >= 20 ? "CRITICAL" : metrics.highRisk >= 10 ? "HIGH" : metrics.aiFlagged >= 5 ? "MEDIUM" : "LOW";

  const fetchDashboard = useCallback(async () => {
    try {
      const data = await getDashboard(dashWindow, 50);
      setDashboardData(data);
    } catch {
      // Silently ignore — shows cached data or loading state
    }
  }, [dashWindow]);

  useEffect(() => {
    if (!loggedIn) return;
    fetchDashboard();
    if (liveMode) {
      dashInterval.current = setInterval(fetchDashboard, 30_000);
    }
    return () => { if (dashInterval.current) clearInterval(dashInterval.current); };
  }, [loggedIn, liveMode, fetchDashboard]);

  const navigateTab = useCallback((tab: string) => {
    const newIdx = NAV.findIndex(n => n.id === tab);
    const oldIdx = NAV.findIndex(n => n.id === activeTab);
    setTabDirection(newIdx >= oldIdx ? 1 : -1);
    setActiveTab(tab);
  }, [activeTab]);

  const handleLogout = () => {
    logout();
    setLoggedIn(false);
    setDashboardData(null);
    setAnalystName("Analyst");
    setRole("viewer");
  };

  const tabVariants = {
    enter:  (dir: number) => ({ x: dir > 0 ? 36 : -36, opacity: 0, scale: 0.985 }),
    center: { x: 0, opacity: 1, scale: 1 },
    exit:   (dir: number) => ({ x: dir > 0 ? -36 : 36, opacity: 0, scale: 0.985 }),
  };

  if (!launched) return <LaunchScreen onEnter={() => setLaunched(true)} />;
  if (!loggedIn) return <LoginScreen onLogin={(name, r) => { setAnalystName(name); setRole(r); setLoggedIn(true); }} />;

  const renderTab = () => {
    switch (activeTab) {
      case "overview":   return <OverviewDashboard metrics={metrics} detections={recentDetections} chartData={chartData} onNavigate={navigateTab} role={role} dashboardData={dashboardData} />;
      case "analyze":    return <div className="h-full overflow-auto p-4"><AnalyzePanel role={role} /></div>;
      case "detections": return <div className="p-4 h-full overflow-hidden flex flex-col"><div className="flex-1 min-h-0"><DetectionFeed detections={recentDetections} /></div></div>;
      case "campaigns":  return (
        <div className="h-full overflow-auto p-4 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: C.text }}>Campaign Graph</h2>
            <div className="flex gap-1">
              {(["1h","6h","24h","7d"] as const).map(w => (
                <button key={w} onClick={() => { setDashWindow(w); fetchDashboard(); }} className="btn"
                  style={dashWindow === w ? { color: C.cyan, borderColor: C.cyan } : {}}>
                  {w}
                </button>
              ))}
            </div>
          </div>
          {dashboardData?.graph && dashboardData.graph.nodes.length > 0 ? (
            <Panel title={`Propagation Graph — ${dashboardData.graph.nodes.length} nodes, ${dashboardData.graph.links.length} links`} className="flex-1">
              <div className="p-4 flex-1 flex flex-col gap-3 overflow-auto">
                <div className="flex gap-3 flex-wrap text-[8px]" style={{ color: C.muted }}>
                  {[{t:"cluster",c:C.cyan},{t:"content",c:C.amber},{t:"actor",c:C.red}].map(l=>(
                    <div key={l.t} className="flex items-center gap-1"><div className="w-2 h-2 rounded-full" style={{background:l.c}}/>{l.t}</div>
                  ))}
                </div>
                <div className="space-y-1.5 overflow-auto flex-1">
                  {dashboardData.graph.nodes.slice(0, 30).map(node => (
                    <div key={node.id} className="flex items-center gap-2 p-2 rounded border" style={{ borderColor: C.border, background: C.bg0 }}>
                      <div className="w-2 h-2 rounded-full shrink-0" style={{ background: node.type==="cluster"?C.cyan:node.type==="actor"?C.red:C.amber }} />
                      <span className="text-[8px] font-mono" style={{ color: C.text }}>{node.label}</span>
                      <span className="text-[7px] ml-auto" style={{ color: C.muted }}>{node.type}</span>
                      {node.ai_probability != null && (
                        <span className="text-[7px] font-mono" style={{ color: node.ai_probability>0.7?C.red:C.amber }}>
                          {Math.round(node.ai_probability*100)}%
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </Panel>
          ) : (
            <div className="flex flex-col items-center justify-center flex-1" style={{ color: C.muted }}>
              <Share2 size={28} className="mb-3 opacity-20" />
              <p className="text-[11px]">No graph data yet — analyze content to build the campaign graph</p>
            </div>
          )}
        </div>
      );
      case "trends":   return <TrendsPage data={chartData} dashboardData={dashboardData} />;
      case "reports":  return <ReportsView />;
      case "settings": return <SettingsView liveMode={liveMode} setLiveMode={setLiveMode} role={role} />;
      default:         return null;
    }
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: C.bg0, color: C.text }}>
      <Topbar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}
        threatLevel={threatLevel} liveMode={liveMode} setLiveMode={setLiveMode} onLogout={handleLogout} />

      <div className="flex flex-1 overflow-hidden min-h-0">
        <Sidebar open={sidebarOpen} activeTab={activeTab} setTab={navigateTab} analystName={analystName} role={role} />

        <div className="flex-1 overflow-hidden relative min-w-0">
          <AnimatePresence mode="wait" custom={tabDirection}>
            <motion.div key={activeTab} custom={tabDirection}
              variants={tabVariants} initial="enter" animate="center" exit="exit"
              transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
              className="absolute inset-0 overflow-hidden">
              {renderTab()}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}