"use client";

import { useEffect, useState } from "react";
import {
  Megaphone,
  MessageSquare,
  Eye,
  Plug,
  FileText,
  Brain,
  Loader2,
  Reply,
  Repeat,
} from "lucide-react";
import { api, connectActivityWS } from "@/lib/api";

interface Stat {
  label: string;
  value: string | number;
  change?: string;
  icon: React.ReactNode;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stat[]>([]);
  const [recentActivity, setRecentActivity] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [campaigns, health, gateway] = await Promise.all([
          api.listCampaigns().catch(() => ({ campaigns: [], active_swarms: [] })),
          api.getHealth().catch(() => ({ status: "offline" })),
          api.getGatewayHealth().catch(() => ({ gateway: "offline" })),
        ]);

        setStats([
          {
            label: "Active Campaigns",
            value: campaigns.active_swarms?.length ?? 0,
            icon: <Megaphone className="h-5 w-5" />,
          },
          {
            label: "Total Campaigns",
            value: campaigns.campaigns?.length ?? 0,
            icon: <FileText className="h-5 w-5" />,
          },
          {
            label: "Orchestrator",
            value: health.status === "ok" ? "Online" : "Offline",
            icon: <Brain className="h-5 w-5" />,
          },
          {
            label: "Gateway",
            value: gateway.gateway === "healthy" ? "Online" : "Offline",
            icon: <Plug className="h-5 w-5" />,
          },
        ]);
      } catch (e) {
        console.error("Failed to load dashboard:", e);
      } finally {
        setLoading(false);
      }
    }

    load();

    // Connect WebSocket for live activity
    const ws = connectActivityWS((event) => {
      if (event.type === "initial" || event.type === "refresh") {
        setRecentActivity(event.data || []);
      } else if (event.type === "heartbeat") {
        setRecentActivity((prev) => {
          const incoming = event.data || [];
          const merged = [...incoming, ...prev];
          // Deduplicate by id
          const seen = new Set<string>();
          return merged.filter((item: any) => {
            if (seen.has(item.id)) return false;
            seen.add(item.id);
            return true;
          }).slice(0, 20);
        });
      }
    });

    return () => ws.close();
  }, []);

  const getActionIcon = (actionType: string) => {
    switch (actionType) {
      case "comment":
        return <MessageSquare className="h-4 w-4" />;
      case "reply":
        return <Reply className="h-4 w-4" />;
      case "repost":
        return <Repeat className="h-4 w-4" />;
      default:
        return <MessageSquare className="h-4 w-4" />;
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          <span className="gradient-text">Dashboard</span>
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your swarm of agents is working. Here&apos;s what&apos;s happening.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-border bg-surface-raised p-5 card-hover"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {stat.label}
              </span>
              <div className="text-brand-400">{stat.icon}</div>
            </div>
            <p className="mt-2 text-2xl font-bold text-foreground">
              {loading ? (
                <span className="inline-block h-7 w-16 animate-pulse rounded bg-muted" />
              ) : (
                stat.value
              )}
            </p>
          </div>
        ))}
      </div>

      {/* Recent Activity */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          Recent Agent Activity
        </h2>
        <div className="space-y-2">
          {recentActivity.length === 0 ? (
            <div className="rounded-xl border border-border bg-surface-raised p-8 text-center">
              <p className="text-sm text-muted-foreground">
                {loading
                  ? "Loading activity..."
                  : "No activity yet. Create a campaign to get started!"}
              </p>
            </div>
          ) : (
            recentActivity.map((item: any, i: number) => (
              <div
                key={item.id || i}
                className="flex items-start gap-4 rounded-lg border border-border bg-surface-raised p-4 card-hover"
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-500/10 text-brand-400">
                  {getActionIcon(item.action_type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium uppercase text-brand-400">
                      {item.platform}
                    </span>
                    <span className="text-xs text-muted-foreground">·</span>
                    <span className="text-xs text-muted-foreground">
                      {item.action_type}
                    </span>
                    {item.strategy_style && (
                      <>
                        <span className="text-xs text-muted-foreground">·</span>
                        <span className="text-xs text-muted-foreground">
                          {item.strategy_style}
                        </span>
                      </>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-foreground/70 line-clamp-2">
                    {item.content}
                  </p>
                  {(item.latest_impressions || item.latest_likes) && (
                    <div className="mt-2 flex gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Eye className="h-3 w-3" />
                        {item.latest_impressions ?? 0}
                      </span>
                      <span className="flex items-center gap-1">
                        <MessageSquare className="h-3 w-3" />
                        {item.latest_likes ?? 0}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
