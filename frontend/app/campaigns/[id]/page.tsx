"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  MessageSquare,
  Eye,
  Heart,
  Reply,
  Repeat,
  Smile,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Target,
  Tag,
  Layers,
  Zap,
  Search,
  Shield,
  Sparkles,
  RefreshCw,
  Activity,
  Brain,
  Radar,
  Camera,
  PenTool,
  TrendingUp,
} from "lucide-react";
import { api } from "@/lib/api";

// Pipeline stage definitions
const PIPELINE_STAGES = [
  { key: "intent", label: "Intent Agent", icon: Brain, description: "Extracting product intent & entities" },
  { key: "scouting", label: "Scout Agent", icon: Radar, description: "Finding relevant social media posts" },
  { key: "vision", label: "Vision Agent", icon: Camera, description: "Analyzing visual context" },
  { key: "strategy", label: "Strategy Agent", icon: PenTool, description: "Planning engagement strategy" },
  { key: "engagement", label: "Engagement", icon: MessageSquare, description: "Generating humanized comments" },
];

export default function CampaignDetailPage() {
  const params = useParams();
  const campaignId = params.id as string;

  const [campaign, setCampaign] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);

    try {
      const [camp, sum, hist, strats] = await Promise.all([
        api.getCampaign(campaignId).catch(() => null),
        api.getCampaignSummary(campaignId).catch(() => null),
        api.getEngagementHistory(campaignId).catch(() => ({ history: [] })),
        api.getStrategyPerformance(campaignId).catch(() => ({ strategies: [] })),
      ]);
      setCampaign(camp);
      setSummary(sum);
      setHistory(hist.history || []);
      setStrategies(strats.strategies || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [campaignId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh while pipeline is running
  useEffect(() => {
    const pipelineStage = campaign?.pipeline_status?.stage;
    const isRunning = pipelineStage && pipelineStage !== "completed" && pipelineStage !== "error";

    if (!isRunning) return;

    const interval = setInterval(() => {
      loadData(true);
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, [campaign?.pipeline_status?.stage, loadData]);

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-32 animate-pulse rounded-xl border border-border bg-surface-raised"
          />
        ))}
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="rounded-xl border border-border bg-surface-raised p-12 text-center">
        <p className="text-muted-foreground">Campaign not found.</p>
      </div>
    );
  }

  const entities = campaign.extracted_entities || {};
  const schema = campaign.campaign_schema || {};
  const pipelineStatus = campaign.pipeline_status || {};
  const pipelineRunning = pipelineStatus.stage && pipelineStatus.stage !== "completed" && pipelineStatus.stage !== "error";

  // Helper to render entity pills
  const renderPills = (items: string[], color: string = "brand") => {
    if (!items || items.length === 0) return null;
    return (
      <div className="flex flex-wrap gap-1.5 mt-1">
        {items.map((item, i) => (
          <span
            key={i}
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
              color === "brand"
                ? "bg-brand-500/10 text-brand-600 dark:text-brand-400"
                : color === "red"
                ? "bg-red-500/10 text-red-600 dark:text-red-400"
                : color === "green"
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                : color === "blue"
                ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {item}
          </span>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="gradient-text">{campaign.name}</span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {campaign.product_name} · {campaign.platforms?.join(", ")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="rounded-lg border border-border p-2 text-muted-foreground hover:text-foreground transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          </button>
          <span
            className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider ${
              campaign.status === "active"
                ? "bg-brand-500/10 text-brand-400"
                : campaign.status === "paused"
                ? "bg-yellow-500/10 text-yellow-400"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {campaign.status}
          </span>
        </div>
      </div>

      {/* Pipeline Status */}
      {pipelineStatus.stage && (
        <div className="rounded-xl border border-border bg-surface-raised p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              {pipelineRunning ? (
                <Loader2 className="h-4 w-4 animate-spin text-brand-500" />
              ) : pipelineStatus.stage === "completed" ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              ) : pipelineStatus.stage === "error" ? (
                <AlertCircle className="h-4 w-4 text-red-500" />
              ) : null}
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Agent Pipeline
              </h2>
            </div>
            {pipelineRunning && (
              <span className="text-xs text-brand-400 animate-pulse">
                Running...
              </span>
            )}
            {pipelineStatus.stage === "completed" && (
              <span className="text-xs text-emerald-500">
                Completed
              </span>
            )}
            {pipelineStatus.stage === "error" && (
              <span className="text-xs text-red-400">
                Error: {pipelineStatus.error?.slice(0, 80)}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1">
            {PIPELINE_STAGES.map((stage, idx) => {
              const completed = (pipelineStatus.stages_completed || []).includes(stage.key);
              const isCurrent = pipelineStatus.stage === stage.key;
              const Icon = stage.icon;

              return (
                <div key={stage.key} className="flex items-center flex-1">
                  <div className="flex flex-col items-center flex-1">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all ${
                        completed
                          ? "border-emerald-500 bg-emerald-500/10 text-emerald-500"
                          : isCurrent
                          ? "border-brand-500 bg-brand-500/10 text-brand-500 animate-pulse"
                          : "border-border bg-surface-raised text-muted-foreground"
                      }`}
                    >
                      {completed ? (
                        <CheckCircle2 className="h-5 w-5" />
                      ) : isCurrent ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : (
                        <Icon className="h-4 w-4" />
                      )}
                    </div>
                    <span className={`mt-1.5 text-[10px] font-medium text-center leading-tight ${
                      completed ? "text-emerald-500" : isCurrent ? "text-brand-400" : "text-muted-foreground"
                    }`}>
                      {stage.label}
                    </span>
                  </div>
                  {idx < PIPELINE_STAGES.length - 1 && (
                    <div className={`h-0.5 w-full mx-1 mb-5 ${
                      completed ? "bg-emerald-500" : "bg-border"
                    }`} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Metrics Summary */}
      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[
            { label: "Engagements", value: summary.total_engagements ?? 0, icon: MessageSquare },
            { label: "Impressions", value: (summary.total_impressions ?? 0).toLocaleString(), icon: Eye },
            { label: "Likes", value: summary.total_likes ?? 0, icon: Heart },
            { label: "Replies", value: summary.total_replies ?? 0, icon: Reply },
            { label: "Sentiment", value: (summary.avg_sentiment ?? 0).toFixed(2), icon: Smile },
          ].map((m) => {
            const Icon = m.icon;
            return (
              <div
                key={m.label}
                className="rounded-xl border border-border bg-surface-raised p-4"
              >
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{m.label}</span>
                  <Icon className="h-4 w-4 text-brand-400" />
                </div>
                <p className="mt-1 text-xl font-bold text-foreground">{m.value}</p>
              </div>
            );
          })}
        </div>
      )}

      {/* Extracted Entities */}
      {entities && Object.keys(entities).length > 0 && (
        <div className="rounded-xl border border-border bg-surface-raised p-6 space-y-5">
          <div className="flex items-center gap-2 text-brand-500">
            <Sparkles className="h-4 w-4" />
            <h2 className="text-sm font-semibold uppercase tracking-wider">
              Extracted Entities (GLiNER)
            </h2>
          </div>

          {/* Marketing Angle */}
          {entities.marketing_angle && (
            <div className="rounded-lg bg-brand-500/5 border border-brand-500/20 p-4">
              <div className="flex items-center gap-2 mb-1">
                <Zap className="h-3.5 w-3.5 text-brand-500" />
                <span className="text-[10px] font-semibold uppercase tracking-wider text-brand-500">
                  Marketing Angle
                </span>
              </div>
              <p className="text-sm text-foreground">{entities.marketing_angle}</p>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {entities.pain_points?.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-1">
                  <Target className="h-3.5 w-3.5 text-red-500" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-red-500">
                    Pain Points
                  </span>
                </div>
                {renderPills(entities.pain_points, "red")}
              </div>
            )}

            {entities.benefits?.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-1">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-500">
                    Benefits
                  </span>
                </div>
                {renderPills(entities.benefits, "green")}
              </div>
            )}

            {entities.key_features?.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-1">
                  <Layers className="h-3.5 w-3.5 text-brand-500" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-brand-500">
                    Key Features
                  </span>
                </div>
                {renderPills(entities.key_features, "brand")}
              </div>
            )}

            {entities.ingredients?.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-1">
                  <Tag className="h-3.5 w-3.5 text-blue-500" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-500">
                    Ingredients
                  </span>
                </div>
                {renderPills(entities.ingredients, "blue")}
              </div>
            )}
          </div>

          {/* Compact metadata */}
          <div className="grid gap-3 sm:grid-cols-3">
            {entities.brand && (
              <div className="rounded-md bg-muted/50 p-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Brand</p>
                <p className="mt-0.5 text-sm font-medium text-foreground">{entities.brand}</p>
              </div>
            )}
            {entities.category && (
              <div className="rounded-md bg-muted/50 p-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Category</p>
                <p className="mt-0.5 text-sm font-medium text-foreground">{entities.category}</p>
              </div>
            )}
            {entities.tone && (
              <div className="rounded-md bg-muted/50 p-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Tone</p>
                <p className="mt-0.5 text-sm font-medium text-foreground capitalize">{entities.tone}</p>
              </div>
            )}
            {entities.competitors?.length > 0 && (
              <div className="rounded-md bg-muted/50 p-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Competitors</p>
                <p className="mt-0.5 text-sm font-medium text-foreground">{entities.competitors.join(", ")}</p>
              </div>
            )}
            {entities.certifications?.length > 0 && (
              <div className="rounded-md bg-muted/50 p-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Certifications</p>
                <p className="mt-0.5 text-sm font-medium text-foreground">{entities.certifications.join(", ")}</p>
              </div>
            )}
            {entities.clinical_claims?.length > 0 && (
              <div className="rounded-md bg-muted/50 p-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Clinical Claims</p>
                <p className="mt-0.5 text-sm font-medium text-foreground">{entities.clinical_claims.join(", ")}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Campaign Schema */}
      {schema.scouting_labels && (
        <div className="rounded-xl border border-border bg-surface-raised p-6 space-y-4">
          <div className="flex items-center gap-2 text-brand-500">
            <Search className="h-4 w-4" />
            <h2 className="text-sm font-semibold uppercase tracking-wider">
              Campaign Entity Schema
            </h2>
            <span className="ml-auto rounded-full bg-muted px-2.5 py-0.5 text-[10px] font-medium text-muted-foreground">
              GLiNER Zero-Shot
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            GLiNER uses these labels to extract entities from social media posts and score relevance.
          </p>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Search className="h-3 w-3 text-muted-foreground" />
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Scouting Labels
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {schema.scouting_labels.map((label: string, i: number) => (
                  <span
                    key={i}
                    className="inline-flex items-center rounded-full bg-brand-500/10 px-2.5 py-0.5 text-xs text-brand-600 dark:text-brand-400"
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Shield className="h-3 w-3 text-muted-foreground" />
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Validation Labels
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {schema.validation_labels?.map((label: string, i: number) => (
                  <span
                    key={i}
                    className="inline-flex items-center rounded-full bg-yellow-500/10 px-2.5 py-0.5 text-xs text-yellow-600 dark:text-yellow-400"
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Pain point / benefit / ingredient terms */}
          <div className="grid gap-3 sm:grid-cols-3">
            {schema.pain_point_terms?.length > 0 && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-red-500">
                  Pain Point Terms
                </span>
                {renderPills(schema.pain_point_terms, "red")}
              </div>
            )}
            {schema.benefit_terms?.length > 0 && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-500">
                  Benefit Terms
                </span>
                {renderPills(schema.benefit_terms, "green")}
              </div>
            )}
            {schema.ingredient_terms?.length > 0 && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-500">
                  Ingredient Terms
                </span>
                {renderPills(schema.ingredient_terms, "blue")}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Strategy Performance */}
      {strategies.length > 0 && (
        <div className="rounded-xl border border-border bg-surface-raised p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Strategy Performance
          </h2>
          <div className="space-y-2">
            {strategies.map((s: any, i: number) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg bg-muted/50 p-3"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">{s.style || "Unknown"}</p>
                  <p className="text-xs text-muted-foreground">
                    tone: {s.tone} · samples: {s.sample_size}
                  </p>
                </div>
                <div className="flex gap-6 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Eye className="h-3 w-3" />
                    {Math.round(s.avg_imp ?? 0)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Heart className="h-3 w-3" />
                    {Math.round(s.avg_likes ?? 0)}
                  </span>
                  <div className="w-20">
                    <div className="flex items-center justify-between">
                      <span>Confidence</span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-brand-500"
                        style={{ width: `${(s.confidence ?? 0.5) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Engagement History */}
      <div className="rounded-xl border border-border bg-surface-raised p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Engagement History
        </h2>
        {history.length === 0 ? (
          <div className="text-center py-8">
            <Activity className="h-8 w-8 mx-auto text-muted-foreground/30 mb-2" />
            <p className="text-sm text-muted-foreground">
              {pipelineRunning
                ? "Agents are running. Engagements will appear here shortly..."
                : "No engagements yet. Click \"Run New Cycle\" to start."}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {history.map((h: any, i: number) => (
              <div
                key={i}
                className="flex items-start gap-3 rounded-lg bg-muted/50 p-3"
              >
                <span className="text-muted-foreground">
                  {h.action_type === "comment" ? (
                    <MessageSquare className="h-4 w-4" />
                  ) : h.action_type === "reply" ? (
                    <Reply className="h-4 w-4" />
                  ) : (
                    <Repeat className="h-4 w-4" />
                  )}
                </span>
                <div className="flex-1">
                  <p className="text-sm text-foreground/70 line-clamp-2">
                    {h.content}
                  </p>
                  <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
                    <span>{h.style}</span>
                    <span className="flex items-center gap-1">
                      <Eye className="h-3 w-3" />
                      {h.impressions ?? 0}
                    </span>
                    <span className="flex items-center gap-1">
                      <Heart className="h-3 w-3" />
                      {h.likes ?? 0}
                    </span>
                    <span className="flex items-center gap-1">
                      <Reply className="h-3 w-3" />
                      {h.replies ?? 0}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={async () => {
            try {
              await api.triggerCycle(campaignId);
              loadData(true);
            } catch (e: any) {
              console.error(e);
            }
          }}
          className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 transition-colors"
        >
          Run New Cycle
        </button>
        <button
          onClick={async () => {
            try {
              await api.triggerLearning(campaignId);
              loadData(true);
            } catch (e: any) {
              console.error(e);
            }
          }}
          className="rounded-lg border border-brand-500/20 px-4 py-2 text-sm font-medium text-brand-400 hover:bg-brand-500/10 transition-colors"
        >
          Trigger Learning
        </button>
        <button
          onClick={async () => {
            try {
              await api.triggerMetrics(campaignId);
              loadData(true);
            } catch (e: any) {
              console.error(e);
            }
          }}
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors"
        >
          Collect Metrics
        </button>
      </div>
    </div>
  );
}
