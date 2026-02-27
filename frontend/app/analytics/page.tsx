"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function AnalyticsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [summary, setSummary] = useState<any>(null);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listCampaigns()
      .then((data) => {
        const camps = data.campaigns || [];
        setCampaigns(camps);
        if (camps.length > 0) {
          setSelectedId(camps[0].id);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;

    Promise.all([
      api.getCampaignSummary(selectedId).catch(() => null),
      api.getStrategyPerformance(selectedId).catch(() => ({ strategies: [] })),
      api.getEngagementHistory(selectedId, 100).catch(() => ({ history: [] })),
    ]).then(([sum, strats, hist]) => {
      setSummary(sum);
      setStrategies(strats.strategies || []);
      setHistory(hist.history || []);
    });
  }, [selectedId]);

  // Compute simple aggregates from history for chart-like display
  const platformBreakdown = history.reduce(
    (acc: Record<string, number>, h: any) => {
      const p = h.platform || "unknown";
      acc[p] = (acc[p] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  const actionBreakdown = history.reduce(
    (acc: Record<string, number>, h: any) => {
      const a = h.action_type || "unknown";
      acc[a] = (acc[a] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          <span className="gradient-text">Analytics</span>
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Performance metrics, strategy analysis, and learning insights.
        </p>
      </div>

      {/* Campaign selector */}
      {campaigns.length > 0 && (
        <div className="flex gap-2">
          {campaigns.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedId(c.id)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                selectedId === c.id
                  ? "bg-brand-500 text-white"
                  : "border border-border text-muted-foreground hover:border-foreground/20"
              }`}
            >
              {c.name}
            </button>
          ))}
        </div>
      )}

      {!selectedId ? (
        <div className="rounded-xl border border-border bg-surface-raised p-12 text-center">
          <p className="text-muted-foreground">Select a campaign to view analytics.</p>
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          {summary && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
              {[
                { label: "Engagements", value: summary.total_engagements ?? 0 },
                {
                  label: "Impressions",
                  value: (summary.total_impressions ?? 0).toLocaleString(),
                },
                { label: "Likes", value: summary.total_likes ?? 0 },
                { label: "Replies", value: summary.total_replies ?? 0 },
                { label: "Reposts", value: summary.total_reposts ?? 0 },
                {
                  label: "Avg Sentiment",
                  value: (summary.avg_sentiment ?? 0).toFixed(2),
                },
              ].map((m) => (
                <div
                  key={m.label}
                  className="rounded-xl border border-border bg-surface-raised p-4"
                >
                  <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                    {m.label}
                  </p>
                  <p className="mt-1 text-xl font-bold text-foreground">{m.value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Breakdowns */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Platform Breakdown */}
            <div className="rounded-xl border border-border bg-surface-raised p-5">
              <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                By Platform
              </h3>
              <div className="space-y-3">
                {Object.entries(platformBreakdown).map(([platform, count]) => {
                  const total = history.length || 1;
                  const pct = ((count as number) / total) * 100;
                  return (
                    <div key={platform}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="capitalize text-foreground/60">
                          {platform}
                        </span>
                        <span className="text-muted-foreground">{count as number}</span>
                      </div>
                      <div className="mt-1 h-2 rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-brand-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Action Type Breakdown */}
            <div className="rounded-xl border border-border bg-surface-raised p-5">
              <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                By Action Type
              </h3>
              <div className="space-y-3">
                {Object.entries(actionBreakdown).map(([action, count]) => {
                  const total = history.length || 1;
                  const pct = ((count as number) / total) * 100;
                  return (
                    <div key={action}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="capitalize text-foreground/60">
                          {action}
                        </span>
                        <span className="text-muted-foreground">{count as number}</span>
                      </div>
                      <div className="mt-1 h-2 rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-blue-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Strategy Leaderboard */}
          {strategies.length > 0 && (
            <div className="rounded-xl border border-border bg-surface-raised p-5">
              <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Strategy Leaderboard (Self-Learning)
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground">
                      <th className="pb-3 pr-4">Strategy</th>
                      <th className="pb-3 pr-4">Tone</th>
                      <th className="pb-3 pr-4 text-right">Avg Impressions</th>
                      <th className="pb-3 pr-4 text-right">Avg Likes</th>
                      <th className="pb-3 pr-4 text-right">Samples</th>
                      <th className="pb-3 text-right">Confidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {strategies.map((s: any, i: number) => (
                      <tr key={i} className="text-foreground/60">
                        <td className="py-3 pr-4 font-medium">
                          {s.style || `Strategy ${i + 1}`}
                        </td>
                        <td className="py-3 pr-4">{s.tone || "—"}</td>
                        <td className="py-3 pr-4 text-right">
                          {Math.round(s.avg_imp ?? 0).toLocaleString()}
                        </td>
                        <td className="py-3 pr-4 text-right">
                          {Math.round(s.avg_likes ?? 0)}
                        </td>
                        <td className="py-3 pr-4 text-right">
                          {s.sample_size ?? 0}
                        </td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="h-1.5 w-16 rounded-full bg-muted">
                              <div
                                className="h-full rounded-full bg-brand-500"
                                style={{
                                  width: `${(s.confidence ?? 0.5) * 100}%`,
                                }}
                              />
                            </div>
                            <span className="text-xs">
                              {((s.confidence ?? 0.5) * 100).toFixed(0)}%
                            </span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
