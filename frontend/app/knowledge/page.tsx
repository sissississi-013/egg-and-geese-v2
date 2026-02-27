"use client";

import { useEffect, useState } from "react";
import {
  Megaphone,
  Package,
  Globe,
  Search,
  MessageSquare,
  Brain,
} from "lucide-react";
import { api } from "@/lib/api";

interface GraphNode {
  id: string;
  type: string;
  data: Record<string, any>;
}

const NODE_COLORS: Record<string, string> = {
  Campaign: "border-brand-500 bg-brand-500/10 text-brand-400",
  Product: "border-blue-500 bg-blue-500/10 text-blue-400",
  Platform: "border-purple-500 bg-purple-500/10 text-purple-400",
  ScoutedPost: "border-yellow-500 bg-yellow-500/10 text-yellow-400",
  Engagement: "border-pink-500 bg-pink-500/10 text-pink-400",
  Strategy: "border-cyan-500 bg-cyan-500/10 text-cyan-400",
};

const NODE_ICONS: Record<string, React.ReactNode> = {
  Campaign: <Megaphone className="h-4 w-4" />,
  Product: <Package className="h-4 w-4" />,
  Platform: <Globe className="h-4 w-4" />,
  ScoutedPost: <Search className="h-4 w-4" />,
  Engagement: <MessageSquare className="h-4 w-4" />,
  Strategy: <Brain className="h-4 w-4" />,
};

export default function KnowledgeGraphPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    api
      .listCampaigns()
      .then((data) => {
        const camps = data.campaigns || [];
        setCampaigns(camps);
        if (camps.length > 0) setSelectedId(camps[0].id);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    api
      .getKnowledgeGraph(selectedId)
      .then((data) => setNodes(data.nodes || []))
      .catch(console.error);
  }, [selectedId]);

  // Group nodes by type for organized display
  const grouped = nodes.reduce(
    (acc, node) => {
      acc[node.type] = acc[node.type] || [];
      acc[node.type].push(node);
      return acc;
    },
    {} as Record<string, GraphNode[]>
  );

  const typeOrder = [
    "Campaign",
    "Product",
    "Platform",
    "Strategy",
    "ScoutedPost",
    "Engagement",
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          <span className="gradient-text">Knowledge Graph</span>
        </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Explore the Neo4j knowledge graph — every agent decision, strategy
            evolution, and engagement trace.
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
                  : "border border-white/10 text-white/40 hover:border-white/20"
              }`}
            >
              {c.name}
            </button>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-3">
        {typeOrder.map((type) => (
          <div
            key={type}
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium ${
              NODE_COLORS[type] || "border-white/10 text-white/40"
            }`}
          >
            <span className="text-brand-400">{NODE_ICONS[type]}</span>
            <span>{type}</span>
            <span className="ml-1 text-muted-foreground/50">
              ({grouped[type]?.length || 0})
            </span>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Graph nodes (grouped) */}
        <div className="lg:col-span-2 space-y-6">
          {typeOrder.map((type) => {
            const group = grouped[type];
            if (!group || group.length === 0) return null;

            return (
              <div key={type}>
                <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  <span className="text-brand-400">{NODE_ICONS[type]}</span>
                  {type} ({group.length})
                </h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {group.slice(0, 20).map((node) => (
                    <button
                      key={node.id}
                      onClick={() => setSelectedNode(node)}
                      className={`rounded-lg border p-3 text-left transition-all hover:scale-[1.02] ${
                        selectedNode?.id === node.id
                          ? NODE_COLORS[type]
                          : "border-border bg-surface-raised hover:border-foreground/10"
                      }`}
                    >
                      <p className="text-xs font-mono text-muted-foreground/50 truncate">
                        {node.id}
                      </p>
                      <p className="mt-0.5 text-sm font-medium text-foreground/70 truncate">
                        {node.data.name ||
                          node.data.style ||
                          node.data.content?.substring(0, 60) ||
                          node.data.text?.substring(0, 60) ||
                          node.type}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}

          {nodes.length === 0 && !loading && (
            <div className="rounded-xl border border-dashed border-border bg-surface-raised p-12 text-center">
              <p className="text-muted-foreground">
                No graph data yet. Run a campaign cycle to populate.
              </p>
            </div>
          )}
        </div>

        {/* Node detail panel */}
        <div className="lg:col-span-1">
          <div className="sticky top-8 rounded-xl border border-border bg-surface-raised p-5">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Node Details
            </h3>
            {selectedNode ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-md border px-2 py-0.5 text-xs font-bold ${
                      NODE_COLORS[selectedNode.type]
                    }`}
                  >
                    {selectedNode.type}
                  </span>
                </div>
                <p className="text-xs font-mono text-muted-foreground/50 break-all">
                  {selectedNode.id}
                </p>
                <div className="space-y-2">
                  {Object.entries(selectedNode.data)
                    .filter(([k]) => k !== "id")
                    .map(([key, val]) => (
                      <div key={key}>
                        <p className="text-[10px] font-medium uppercase text-muted-foreground/60">
                          {key}
                        </p>
                        <p className="text-sm text-foreground/60 break-words">
                          {Array.isArray(val)
                            ? val.join(", ") || "[]"
                            : typeof val === "object"
                            ? JSON.stringify(val, null, 2)
                            : String(val)}
                        </p>
                      </div>
                    ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground/50">
                Click a node to see its properties.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
