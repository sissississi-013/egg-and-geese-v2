"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Brain,
  Radar,
  Camera,
  PenTool,
  MessageSquare,
  TrendingUp,
  Network,
  ChevronDown,
  ChevronUp,
  Zap,
  Clock,
  ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Agent definitions ───────────────────────────────────────────────────

interface AgentDef {
  id: string;
  label: string;
  shortLabel: string;
  icon: any;
  color: string;     // tailwind color name
  api: string;       // the service it calls
  x: number;         // SVG position (0-1 normalized)
  y: number;
}

const AGENTS: AgentDef[] = [
  { id: "intent",     label: "Intent Agent",     shortLabel: "Intent",     icon: Brain,          color: "brand",   api: "GLiNER / Fastino", x: 0.22, y: 0.18 },
  { id: "scout",      label: "Scout Agent",      shortLabel: "Scout",      icon: Radar,          color: "blue",    api: "Yutori",           x: 0.78, y: 0.18 },
  { id: "vision",     label: "Vision Agent",     shortLabel: "Vision",     icon: Camera,         color: "purple",  api: "Reka Vision",      x: 0.91, y: 0.58 },
  { id: "strategy",   label: "Strategy Agent",   shortLabel: "Strategy",   icon: PenTool,        color: "emerald", api: "Claude / Senso",   x: 0.50, y: 0.85 },
  { id: "engagement", label: "Engagement Agent", shortLabel: "Engage",     icon: MessageSquare,  color: "amber",   api: "OpenClaw",         x: 0.09, y: 0.58 },
  { id: "learning",   label: "Learning Agent",   shortLabel: "Learn",      icon: TrendingUp,     color: "rose",    api: "Neo4j",            x: 0.50, y: 0.50 },
];

// Connections between agents (flow direction)
const CONNECTIONS = [
  { from: "intent",     to: "scout" },
  { from: "scout",      to: "vision" },
  { from: "vision",     to: "strategy" },
  { from: "strategy",   to: "engagement" },
  { from: "engagement", to: "learning" },
  { from: "learning",   to: "intent" },
];

// Map agent id → tailwind classes
const COLOR_MAP: Record<string, { bg: string; text: string; ring: string; glow: string; dot: string }> = {
  brand:   { bg: "bg-orange-500/10",  text: "text-orange-500",  ring: "ring-orange-500/30",  glow: "shadow-orange-500/20", dot: "#f97316" },
  blue:    { bg: "bg-blue-500/10",    text: "text-blue-500",    ring: "ring-blue-500/30",    glow: "shadow-blue-500/20",   dot: "#3b82f6" },
  purple:  { bg: "bg-purple-500/10",  text: "text-purple-500",  ring: "ring-purple-500/30",  glow: "shadow-purple-500/20", dot: "#a855f7" },
  emerald: { bg: "bg-emerald-500/10", text: "text-emerald-500", ring: "ring-emerald-500/30", glow: "shadow-emerald-500/20",dot: "#10b981" },
  amber:   { bg: "bg-amber-500/10",   text: "text-amber-500",   ring: "ring-amber-500/30",   glow: "shadow-amber-500/20",  dot: "#f59e0b" },
  rose:    { bg: "bg-rose-500/10",    text: "text-rose-500",    ring: "ring-rose-500/30",    glow: "shadow-rose-500/20",   dot: "#f43f5e" },
};

// ── Activity event type ─────────────────────────────────────────────────

interface ActivityEvent {
  timestamp: string;
  agent: string;
  action: string;
  detail: string;
  status: string;
  meta: Record<string, any>;
}

// ── Main Component ──────────────────────────────────────────────────────

export default function SwarmVisualization({
  campaignId,
  isRunning,
}: {
  campaignId: string;
  isRunning: boolean;
}) {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [eventCount, setEventCount] = useState(0);
  const [expanded, setExpanded] = useState(true);
  const [activeAgents, setActiveAgents] = useState<Set<string>>(new Set());
  const [activeEdges, setActiveEdges] = useState<Set<string>>(new Set());
  const timelineRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  // Poll for activity events
  const pollEvents = useCallback(async () => {
    try {
      const res = await api.getCampaignActivity(campaignId, eventCount);
      if (res.events && res.events.length > 0) {
        setEvents((prev) => [...prev, ...res.events]);
        setEventCount(res.total);

        // Determine currently active agents from new events
        const newActive = new Set<string>();
        const newEdges = new Set<string>();
        for (const evt of res.events) {
          if (evt.status === "running") {
            newActive.add(evt.agent);
          }
        }
        // Also check the last few events for recently active agents
        const recent = [...events, ...res.events].slice(-6);
        for (const evt of recent) {
          if (evt.status === "running") {
            newActive.add(evt.agent);
          }
          // If an agent just completed, light up the edge to the next
          if (evt.status === "done") {
            const conn = CONNECTIONS.find((c) => c.from === evt.agent);
            if (conn) newEdges.add(`${conn.from}-${conn.to}`);
          }
        }
        setActiveAgents(newActive);
        setActiveEdges(newEdges);
      }
    } catch {
      // silently ignore polling errors
    }
  }, [campaignId, eventCount, events]);

  // Poll every 2 seconds while running
  useEffect(() => {
    pollEvents(); // initial load
    if (!isRunning && events.length > 0) return;

    const interval = setInterval(pollEvents, 2000);
    return () => clearInterval(interval);
  }, [isRunning, pollEvents]);

  // Auto-scroll timeline
  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [events]);

  // Determine which agents have completed
  const completedAgents = new Set<string>();
  for (const evt of events) {
    if (evt.action === "completed" && evt.status === "done") {
      completedAgents.add(evt.agent);
    }
  }

  // SVG dimensions
  const W = 520;
  const H = 340;
  const NODE_R = 32;

  // Get agent position in SVG coords
  const pos = (agent: AgentDef) => ({
    cx: agent.x * W,
    cy: agent.y * H,
  });

  return (
    <div className="rounded-xl border border-border bg-surface-raised overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-5 py-3 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Network className="h-4 w-4 text-brand-500" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Agent Swarm
          </h2>
          {isRunning && (
            <span className="ml-2 flex items-center gap-1 text-xs text-brand-400 animate-pulse">
              <Zap className="h-3 w-3" />
              Live
            </span>
          )}
          {events.length > 0 && (
            <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
              {events.length} events
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-border">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr]">
            {/* LEFT: SVG Topology */}
            <div className="relative p-4 flex items-center justify-center min-h-[340px]">
              <svg
                ref={svgRef}
                viewBox={`0 0 ${W} ${H}`}
                className="w-full max-w-[520px]"
                style={{ filter: "drop-shadow(0 0 1px rgba(0,0,0,0.1))" }}
              >
                <defs>
                  {/* Animated dash for active edges */}
                  <style>{`
                    @keyframes dash-flow {
                      to { stroke-dashoffset: -20; }
                    }
                    .edge-active {
                      animation: dash-flow 0.8s linear infinite;
                    }
                    @keyframes pulse-ring {
                      0% { r: ${NODE_R}; opacity: 0.6; }
                      100% { r: ${NODE_R + 12}; opacity: 0; }
                    }
                    .node-pulse {
                      animation: pulse-ring 1.5s ease-out infinite;
                    }
                  `}</style>
                  {/* Arrow marker */}
                  <marker
                    id="arrowhead"
                    markerWidth="8"
                    markerHeight="6"
                    refX="8"
                    refY="3"
                    orient="auto"
                    markerUnits="strokeWidth"
                  >
                    <polygon
                      points="0 0, 8 3, 0 6"
                      fill="currentColor"
                      className="text-muted-foreground/30"
                    />
                  </marker>
                  <marker
                    id="arrowhead-active"
                    markerWidth="8"
                    markerHeight="6"
                    refX="8"
                    refY="3"
                    orient="auto"
                    markerUnits="strokeWidth"
                  >
                    <polygon
                      points="0 0, 8 3, 0 6"
                      fill="#f97316"
                    />
                  </marker>
                </defs>

                {/* Connections / edges */}
                {CONNECTIONS.map((conn) => {
                  const fromAgent = AGENTS.find((a) => a.id === conn.from)!;
                  const toAgent = AGENTS.find((a) => a.id === conn.to)!;
                  const p1 = pos(fromAgent);
                  const p2 = pos(toAgent);
                  const edgeKey = `${conn.from}-${conn.to}`;
                  const isActive = activeEdges.has(edgeKey) || activeAgents.has(conn.from);

                  // Shorten line to not overlap node circles
                  const dx = p2.cx - p1.cx;
                  const dy = p2.cy - p1.cy;
                  const dist = Math.sqrt(dx * dx + dy * dy);
                  const offset = NODE_R + 6;
                  const x1 = p1.cx + (dx / dist) * offset;
                  const y1 = p1.cy + (dy / dist) * offset;
                  const x2 = p2.cx - (dx / dist) * offset;
                  const y2 = p2.cy - (dy / dist) * offset;

                  return (
                    <line
                      key={edgeKey}
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke={isActive ? "#f97316" : "currentColor"}
                      className={`${isActive ? "" : "text-muted-foreground/20"} ${isActive ? "edge-active" : ""}`}
                      strokeWidth={isActive ? 2 : 1}
                      strokeDasharray={isActive ? "6 4" : "none"}
                      markerEnd={isActive ? "url(#arrowhead-active)" : "url(#arrowhead)"}
                      style={{ transition: "stroke 0.3s, stroke-width 0.3s" }}
                    />
                  );
                })}

                {/* Agent nodes */}
                {AGENTS.map((agent) => {
                  const { cx, cy } = pos(agent);
                  const isActive = activeAgents.has(agent.id);
                  const isDone = completedAgents.has(agent.id);
                  const colors = COLOR_MAP[agent.color];
                  const Icon = agent.icon;

                  return (
                    <g key={agent.id}>
                      {/* Pulse ring for active agents */}
                      {isActive && (
                        <circle
                          cx={cx}
                          cy={cy}
                          r={NODE_R}
                          fill="none"
                          stroke={colors.dot}
                          strokeWidth={2}
                          className="node-pulse"
                          opacity={0.5}
                        />
                      )}

                      {/* Node circle */}
                      <circle
                        cx={cx}
                        cy={cy}
                        r={NODE_R}
                        fill={isDone ? `${colors.dot}15` : isActive ? `${colors.dot}20` : "var(--color-surface-raised, #1a1a2e)"}
                        stroke={isDone ? colors.dot : isActive ? colors.dot : "var(--color-border, #2a2a4a)"}
                        strokeWidth={isDone ? 2.5 : isActive ? 2 : 1}
                        style={{ transition: "all 0.3s ease" }}
                      />

                      {/* Completed checkmark background */}
                      {isDone && (
                        <circle
                          cx={cx + NODE_R * 0.65}
                          cy={cy - NODE_R * 0.65}
                          r={8}
                          fill={colors.dot}
                        />
                      )}
                      {isDone && (
                        <text
                          x={cx + NODE_R * 0.65}
                          y={cy - NODE_R * 0.65 + 1}
                          textAnchor="middle"
                          dominantBaseline="central"
                          fill="white"
                          fontSize="10"
                          fontWeight="bold"
                        >
                          &#x2713;
                        </text>
                      )}

                      {/* Icon placeholder (foreignObject for React icon) */}
                      <foreignObject
                        x={cx - 10}
                        y={cy - 10}
                        width={20}
                        height={20}
                      >
                        <div className="flex items-center justify-center w-full h-full">
                          <Icon
                            className={`h-4 w-4 ${
                              isDone ? `text-[${colors.dot}]` : isActive ? `text-[${colors.dot}]` : "text-muted-foreground/60"
                            }`}
                            style={{ color: isDone || isActive ? colors.dot : undefined }}
                          />
                        </div>
                      </foreignObject>

                      {/* Agent label */}
                      <text
                        x={cx}
                        y={cy + NODE_R + 14}
                        textAnchor="middle"
                        fontSize="10"
                        fontWeight="600"
                        fill={isDone ? colors.dot : isActive ? colors.dot : "currentColor"}
                        className={isDone || isActive ? "" : "text-muted-foreground/60"}
                      >
                        {agent.shortLabel}
                      </text>

                      {/* API service badge */}
                      <text
                        x={cx}
                        y={cy + NODE_R + 25}
                        textAnchor="middle"
                        fontSize="8"
                        fill="currentColor"
                        className="text-muted-foreground/40"
                      >
                        {agent.api}
                      </text>
                    </g>
                  );
                })}

                {/* Center coordinator label */}
                <text
                  x={W / 2}
                  y={H / 2 - 30}
                  textAnchor="middle"
                  fontSize="9"
                  fontWeight="700"
                  letterSpacing="0.1em"
                  fill="currentColor"
                  className="text-muted-foreground/30 uppercase"
                >
                  SWARM
                </text>
              </svg>
            </div>

            {/* RIGHT: Activity Timeline */}
            <div className="border-t lg:border-t-0 lg:border-l border-border flex flex-col">
              <div className="px-4 py-2.5 border-b border-border flex items-center gap-2">
                <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Activity Log
                </span>
              </div>
              <div
                ref={timelineRef}
                className="flex-1 overflow-y-auto max-h-[300px] p-3 space-y-1"
              >
                {events.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-sm text-muted-foreground/50 py-12">
                    {isRunning ? "Waiting for agent events..." : "No activity yet"}
                  </div>
                ) : (
                  events.map((evt, i) => {
                    const agent = AGENTS.find((a) => a.id === evt.agent);
                    const dotColor = agent ? COLOR_MAP[agent.color].dot : "#888";

                    return (
                      <div
                        key={i}
                        className="flex items-start gap-2 py-1 animate-in fade-in slide-in-from-bottom-1 duration-300"
                      >
                        {/* Dot */}
                        <div
                          className="mt-1.5 h-2 w-2 rounded-full shrink-0"
                          style={{ backgroundColor: dotColor }}
                        />

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline gap-1.5">
                            <span
                              className="text-[11px] font-semibold"
                              style={{ color: dotColor }}
                            >
                              {agent?.shortLabel || evt.agent}
                            </span>
                            <span className="text-[10px] text-muted-foreground/50">
                              {evt.action.replace(/_/g, " ")}
                            </span>
                            {evt.status === "error" && (
                              <span className="text-[10px] text-red-400 font-medium">
                                FAILED
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-muted-foreground leading-tight truncate">
                            {evt.detail}
                          </p>
                        </div>

                        {/* Timestamp */}
                        <span className="text-[9px] text-muted-foreground/40 shrink-0 tabular-nums">
                          {new Date(evt.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          {/* Bottom: Agent status pills */}
          <div className="border-t border-border px-4 py-2.5 flex flex-wrap gap-2">
            {AGENTS.map((agent) => {
              const isDone = completedAgents.has(agent.id);
              const isActive = activeAgents.has(agent.id);
              const colors = COLOR_MAP[agent.color];
              const Icon = agent.icon;

              return (
                <div
                  key={agent.id}
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-all ${
                    isDone
                      ? `${colors.bg} border border-current/10`
                      : isActive
                      ? `${colors.bg} border border-current/20`
                      : "bg-muted/50 border border-transparent"
                  }`}
                  style={{ color: isDone || isActive ? colors.dot : undefined }}
                >
                  <Icon className="h-3 w-3" />
                  {agent.shortLabel}
                  {isDone && (
                    <span className="ml-0.5 text-[9px] opacity-60">Done</span>
                  )}
                  {isActive && (
                    <span className="ml-0.5 h-1.5 w-1.5 rounded-full animate-pulse" style={{ backgroundColor: colors.dot }} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
