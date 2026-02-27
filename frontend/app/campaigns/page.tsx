"use client";

import { useEffect, useState } from "react";
import { Package } from "lucide-react";
import { api } from "@/lib/api";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [activeSwarms, setActiveSwarms] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listCampaigns()
      .then((data) => {
        setCampaigns(data.campaigns || []);
        setActiveSwarms(data.active_swarms || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handlePause = async (id: string) => {
    await api.pauseCampaign(id);
    setActiveSwarms((prev) =>
      prev.map((s) => (s.campaign_id === id ? { ...s, status: "paused" } : s))
    );
  };

  const handleResume = async (id: string) => {
    await api.resumeCampaign(id);
    setActiveSwarms((prev) =>
      prev.map((s) => (s.campaign_id === id ? { ...s, status: "active" } : s))
    );
  };

  const handleCycle = async (id: string) => {
    try {
      await api.triggerCycle(id);
      alert("Cycle triggered successfully!");
    } catch (e: any) {
      alert(`Failed: ${e.message}`);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="gradient-text">Campaigns</span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage your marketing campaigns and agent swarms.
          </p>
        </div>
        <a
          href="/campaigns/new"
          className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-600"
        >
          + New Campaign
        </a>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-xl border border-white/5 bg-surface-raised"
            />
          ))}
        </div>
      ) : campaigns.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-surface-raised p-12 text-center">
          <div className="flex justify-center mb-4">
            <Package className="h-12 w-12 text-muted-foreground" />
          </div>
          <p className="mt-3 text-lg font-medium text-foreground">
            No campaigns yet
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Create your first campaign to deploy a swarm of agents.
          </p>
          <a
            href="/campaigns/new"
            className="mt-4 inline-block rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
          >
            Create Campaign
          </a>
        </div>
      ) : (
        <div className="space-y-3">
          {campaigns.map((campaign) => {
            const swarm = activeSwarms.find(
              (s) => s.campaign_id === campaign.id
            );
            return (
              <div
                key={campaign.id}
                className="rounded-xl border border-border bg-surface-raised p-5 card-hover"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold text-foreground">
                        {campaign.name}
                      </h3>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                          campaign.status === "active"
                            ? "bg-brand-500/10 text-brand-400"
                            : campaign.status === "paused"
                            ? "bg-yellow-500/10 text-yellow-400"
                            : "bg-white/5 text-white/30"
                        }`}
                      >
                        {campaign.status}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {campaign.product_name} ·{" "}
                      {campaign.platforms?.join(", ")}
                    </p>
                    {campaign.pain_points?.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {campaign.pain_points.map((pp: string, i: number) => (
                          <span
                            key={i}
                            className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                          >
                            {pp}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <a
                      href={`/campaigns/${campaign.id}`}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:border-foreground/20 hover:text-foreground"
                    >
                      View
                    </a>
                    {campaign.status === "active" ? (
                      <button
                        onClick={() => handlePause(campaign.id)}
                        className="rounded-lg border border-yellow-500/20 px-3 py-1.5 text-xs font-medium text-yellow-400 hover:bg-yellow-500/10"
                      >
                        Pause
                      </button>
                    ) : (
                      <button
                        onClick={() => handleResume(campaign.id)}
                        className="rounded-lg border border-brand-500/20 px-3 py-1.5 text-xs font-medium text-brand-400 hover:bg-brand-500/10"
                      >
                        Resume
                      </button>
                    )}
                    <button
                      onClick={() => handleCycle(campaign.id)}
                      className="rounded-lg bg-brand-500/10 px-3 py-1.5 text-xs font-medium text-brand-400 hover:bg-brand-500/20"
                    >
                      Run Cycle
                    </button>
                  </div>
                </div>

                {swarm && (
                  <div className="mt-3 flex gap-4 border-t border-border pt-3 text-xs text-muted-foreground">
                    <span>Cycles: {swarm.cycles_completed}</span>
                    <span>Platforms: {swarm.platforms?.join(", ")}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
