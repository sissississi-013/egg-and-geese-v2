"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Link as LinkIcon,
  MessageSquare,
  Loader2,
  CheckCircle2,
  X,
  Sparkles,
  Target,
  Shield,
  Search,
  Tag,
  Layers,
  Zap,
  ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function NewCampaignPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"link" | "chat" | null>(null);
  const [linkUrl, setLinkUrl] = useState("");
  const [linkLoading, setLinkLoading] = useState(false);
  const [linkError, setLinkError] = useState("");
  const [extractedData, setExtractedData] = useState<any>(null);

  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hi! I'll help you create a campaign. Let's start with the basics — what product are you looking to market?",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatData, setChatData] = useState<any>(null);

  const handleLinkSubmit = async () => {
    if (!linkUrl.trim()) {
      setLinkError("Please enter a URL");
      return;
    }

    setLinkLoading(true);
    setLinkError("");

    try {
      // Call backend to scrape + extract with GLiNER
      const response = await fetch("/api/campaigns/from-link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: linkUrl }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to extract product info");
      }

      const data = await response.json();
      setExtractedData(data);
    } catch (e: any) {
      setLinkError(e.message || "Failed to process link");
    } finally {
      setLinkLoading(false);
    }
  };

  const handleChatSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!chatInput.trim() || chatLoading) return;

    const userMessage = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setChatLoading(true);

    try {
      // Call backend chat endpoint
      const response = await fetch("/api/campaigns/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [...chatMessages, { role: "user", content: userMessage }],
        }),
      });

      if (!response.ok) {
        throw new Error("Chat failed");
      }

      const data = await response.json();
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response },
      ]);

      // If campaign is ready, show it
      if (data.campaign_data) {
        setChatData(data.campaign_data);
      }
    } catch (e) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Could you try again?",
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const [campaignName, setCampaignName] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [deploying, setDeploying] = useState(false);

  const handleDeploy = async (data: any) => {
    const name = campaignName.trim() || `${data.product_name || "Product"} Campaign`;
    const audience = targetAudience.trim() || data.target_audience || "";

    setDeploying(true);
    try {
      const result = await api.createCampaign({
        name,
        product_name: data.product_name || "Product",
        product_description: data.product_description || "",
        target_audience: audience,
        platforms: data.platforms || ["twitter", "reddit", "instagram"],
        // Pass all pre-extracted data so the backend doesn't start from scratch
        extracted_entities: data.extracted_entities || undefined,
        campaign_schema: data.campaign_schema || undefined,
        gliner_raw: data.gliner_raw || undefined,
      });
      router.push(`/campaigns/${result.campaign_id}`);
    } catch (e: any) {
      alert(`Failed to deploy: ${e.message}`);
    } finally {
      setDeploying(false);
    }
  };

  if (extractedData || chatData) {
    const data = extractedData || chatData;
    const entities = data.extracted_entities || {};
    const schema = data.campaign_schema || {};

    // Auto-fill target audience from extraction if not set yet
    if (data.target_audience && !targetAudience) {
      setTargetAudience(
        Array.isArray(data.target_audience)
          ? data.target_audience.join(", ")
          : data.target_audience
      );
    }

    // Helper to render entity pills
    const renderPills = (items: string[], color: string = "brand") => (
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

    return (
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              <span className="gradient-text">Review & Deploy</span>
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {data.extraction_method === "gliner_primary_claude_synthesis" ? (
                <>GLiNER extracted grounded entities, Claude synthesized the profile.</>
              ) : (
                <>AI extracted this information. Review, adjust, and deploy.</>
              )}
            </p>
          </div>
          <button
            onClick={() => {
              setExtractedData(null);
              setChatData(null);
              setCampaignName("");
              setTargetAudience("");
              setMode(null);
            }}
            className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Editable Campaign Fields */}
        <div className="rounded-xl border border-border bg-surface-raised p-6 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-xs font-medium uppercase text-muted-foreground">
                Campaign Name
              </label>
              <input
                type="text"
                value={campaignName}
                onChange={(e) => setCampaignName(e.target.value)}
                placeholder={`${data.product_name || "Product"} Campaign`}
                className="mt-1 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm placeholder:text-muted-foreground"
              />
            </div>
            <div>
              <label className="text-xs font-medium uppercase text-muted-foreground">
                Product Name
              </label>
              <input
                type="text"
                value={data.product_name || ""}
                onChange={(e) => {
                  const updated = { ...data, product_name: e.target.value };
                  extractedData ? setExtractedData(updated) : setChatData(updated);
                }}
                className="mt-1 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium uppercase text-muted-foreground">
              Product Description
            </label>
            <textarea
              value={data.product_description || ""}
              onChange={(e) => {
                const updated = { ...data, product_description: e.target.value };
                extractedData ? setExtractedData(updated) : setChatData(updated);
              }}
              rows={3}
              className="mt-1 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm"
            />
          </div>

          <div>
            <label className="text-xs font-medium uppercase text-muted-foreground">
              Target Audience
            </label>
            <textarea
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              placeholder="Who is this product for?"
              rows={2}
              className="mt-1 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm placeholder:text-muted-foreground"
            />
          </div>
        </div>

        {/* Extracted Intelligence — organized by category */}
        <div className="rounded-xl border border-border bg-surface-raised p-6 space-y-5">
          <div className="flex items-center gap-2 text-brand-500">
            <Sparkles className="h-4 w-4" />
            <h2 className="text-sm font-semibold uppercase tracking-wider">
              Extracted Intelligence
            </h2>
            {data.extraction_method && (
              <span className="ml-auto rounded-full bg-brand-500/10 px-2.5 py-0.5 text-[10px] font-medium text-brand-500">
                {data.extraction_method === "gliner_primary_claude_synthesis"
                  ? "GLiNER Primary"
                  : "AI Extracted"}
              </span>
            )}
          </div>

          {/* Marketing Angle */}
          {entities.marketing_angle && (
            <div className="rounded-lg bg-brand-500/5 border border-brand-500/20 p-4">
              <div className="flex items-center gap-2 mb-1">
                <Zap className="h-3.5 w-3.5 text-brand-500" />
                <span className="text-[10px] font-semibold uppercase tracking-wider text-brand-500">
                  Suggested Marketing Angle
                </span>
              </div>
              <p className="text-sm text-foreground">{entities.marketing_angle}</p>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {/* Pain Points */}
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

            {/* Benefits */}
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

            {/* Key Features */}
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

            {/* Ingredients */}
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

          {/* Other entities in a compact grid */}
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
            {entities.pricing?.length > 0 && (
              <div className="rounded-md bg-muted/50 p-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Pricing</p>
                <p className="mt-0.5 text-sm font-medium text-foreground">{entities.pricing.join(", ")}</p>
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

        {/* Campaign Entity Schema — shows what GLiNER will use for scouting */}
        {schema.scouting_labels && (
          <div className="rounded-xl border border-border bg-surface-raised p-6 space-y-4">
            <div className="flex items-center gap-2 text-brand-500">
              <Search className="h-4 w-4" />
              <h2 className="text-sm font-semibold uppercase tracking-wider">
                Campaign Entity Schema
              </h2>
              <span className="ml-auto rounded-full bg-muted px-2.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                Powered by GLiNER Zero-Shot
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              When scouting social media, GLiNER will extract these entity types from
              every discovered post and score relevance by entity overlap with your
              product profile.
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
                    Comment Validation Labels
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
          </div>
        )}

        {/* Deploy Button */}
        <div className="rounded-xl border border-border bg-surface-raised p-6">
          <div className="flex gap-3">
            <button
              onClick={() => handleDeploy(data)}
              disabled={deploying}
              className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-brand-500 py-3 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
            >
              {deploying ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Deploying Agents...
                </>
              ) : (
                <>
                  <ArrowRight className="h-4 w-4" />
                  Deploy Campaign
                </>
              )}
            </button>
          </div>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            This will launch the agent swarm: Intent Agent, Scout Agent, Vision Agent, and Strategy Agent
          </p>
        </div>
      </div>
    );
  }

  if (!mode) {
    return (
      <div className="mx-auto max-w-4xl space-y-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="gradient-text">Create Campaign</span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose how you&apos;d like to get started. GLiNER extracts grounded
            entity spans from your product, then builds a campaign-specific schema
            for scouting, engagement, and learning.
          </p>
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          <button
            onClick={() => setMode("link")}
            className="group relative rounded-xl border-2 border-dashed border-border bg-surface-raised p-8 text-left transition-all hover:border-brand-500 hover:bg-brand-500/5"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="rounded-lg bg-brand-500/10 p-2 text-brand-500">
                <LinkIcon className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold">Paste Product Link</h3>
            </div>
            <p className="text-sm text-muted-foreground">
              Drop a product link and GLiNER will extract grounded entity spans
              directly from the page — pain points, ingredients, benefits — all
              verified text, not hallucinated.
            </p>
            <Sparkles className="absolute right-4 top-4 h-4 w-4 text-brand-400 opacity-0 transition-opacity group-hover:opacity-100" />
          </button>

          <button
            onClick={() => setMode("chat")}
            className="group relative rounded-xl border-2 border-dashed border-border bg-surface-raised p-8 text-left transition-all hover:border-brand-500 hover:bg-brand-500/5"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="rounded-lg bg-brand-500/10 p-2 text-brand-500">
                <MessageSquare className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold">Smart Chat</h3>
            </div>
            <p className="text-sm text-muted-foreground">
              Have a conversation with our AI. We&apos;ll ask smart questions
              and build your campaign step by step.
            </p>
            <Sparkles className="absolute right-4 top-4 h-4 w-4 text-brand-400 opacity-0 transition-opacity group-hover:opacity-100" />
          </button>
        </div>
      </div>
    );
  }

  if (mode === "link") {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setMode(null)}
            className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            ← Back
          </button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Paste Product Link
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              We&apos;ll scrape and extract product info using GLiNER
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-surface-raised p-6 space-y-4">
          <div>
            <label className="text-xs font-medium uppercase text-muted-foreground mb-2 block">
              Product URL
            </label>
            <div className="flex gap-2">
              <input
                type="url"
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                placeholder="https://example.com/product..."
                className="flex-1 rounded-lg border border-border bg-background px-4 py-2.5 text-sm placeholder:text-muted-foreground focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                onKeyDown={(e) => e.key === "Enter" && handleLinkSubmit()}
              />
              <button
                onClick={handleLinkSubmit}
                disabled={linkLoading}
                className="rounded-lg bg-brand-500 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {linkLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Extract"
                )}
              </button>
            </div>
            {linkError && (
              <p className="mt-2 text-sm text-red-400">{linkError}</p>
            )}
          </div>

          <div className="rounded-lg bg-muted/50 p-4 space-y-2">
            <p className="text-xs text-muted-foreground">
              <strong>Supported:</strong> Amazon, brand websites, any product page.
            </p>
            <p className="text-xs text-muted-foreground">
              <strong>How it works:</strong> GLiNER runs multi-pass entity extraction
              (product names, ingredients, pain points, benefits, clinical claims,
              certifications) then Claude synthesizes a coherent profile from GLiNER&apos;s
              grounded spans. A campaign-specific entity schema is auto-generated for
              scouting.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Chat mode
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => {
            setMode(null);
            setChatMessages([
              {
                role: "assistant",
                content:
                  "Hi! I'll help you create a campaign. Let's start with the basics — what product are you looking to market?",
              },
            ]);
            setChatInput("");
          }}
          className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          ← Back
        </button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Smart Chat</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Tell me about your product and I&apos;ll build your campaign
          </p>
        </div>
      </div>

      <div className="flex h-[600px] flex-col rounded-xl border border-border bg-surface-raised">
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {chatMessages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2.5 ${
                  msg.role === "user"
                    ? "bg-brand-500 text-white"
                    : "bg-muted text-foreground"
                }`}
              >
                <p className="text-sm">{msg.content}</p>
              </div>
            </div>
          ))}
          {chatLoading && (
            <div className="flex justify-start gap-3">
              <div className="rounded-lg bg-muted px-4 py-2.5">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            </div>
          )}
        </div>

        <form onSubmit={handleChatSubmit} className="border-t border-border p-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Type your message..."
              className="flex-1 rounded-lg border border-border bg-background px-4 py-2.5 text-sm placeholder:text-muted-foreground focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              disabled={chatLoading}
            />
            <button
              type="submit"
              disabled={chatLoading || !chatInput.trim()}
              className="rounded-lg bg-brand-500 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
