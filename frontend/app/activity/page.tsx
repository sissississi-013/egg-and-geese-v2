"use client";

import { useEffect, useState, useRef } from "react";
import {
  MessageSquare,
  Reply,
  Repeat,
  Eye,
  Heart,
  ExternalLink,
} from "lucide-react";
import { connectActivityWS } from "@/lib/api";

interface ActivityItem {
  id: string;
  action_type: string;
  content: string;
  timestamp: string;
  post_url: string;
  post_text: string;
  platform: string;
  strategy_style: string;
  latest_impressions: number;
  latest_likes: number;
}

const PLATFORM_COLORS: Record<string, string> = {
  twitter: "text-blue-400 bg-blue-500/10",
  reddit: "text-orange-400 bg-orange-500/10",
  instagram: "text-pink-400 bg-pink-500/10",
};

export default function ActivityPage() {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [connected, setConnected] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ws = connectActivityWS((event) => {
      setConnected(true);

      if (event.type === "initial" || event.type === "refresh") {
        setItems(event.data || []);
      } else if (event.type === "heartbeat") {
        setItems((prev) => {
          const incoming = event.data || [];
          const merged = [...incoming, ...prev];
          const seen = new Set<string>();
          return merged
            .filter((item: ActivityItem) => {
              if (seen.has(item.id)) return false;
              seen.add(item.id);
              return true;
            })
            .slice(0, 100);
        });
      } else if (event.type === "pong") {
        // heartbeat ack
      }
    });

    return () => ws.close();
  }, []);

  const getActionIcon = (actionType: string) => {
    switch (actionType) {
      case "comment":
        return <MessageSquare className="h-5 w-5" />;
      case "reply":
        return <Reply className="h-5 w-5" />;
      case "repost":
        return <Repeat className="h-5 w-5" />;
      default:
        return <MessageSquare className="h-5 w-5" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="gradient-text">Activity Feed</span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Real-time agent actions across all campaigns.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              connected ? "bg-brand-400 animate-pulse" : "bg-red-400"
            }`}
          />
          <span className="text-xs text-muted-foreground">
            {connected ? "Live" : "Connecting..."}
          </span>
        </div>
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-5 top-0 bottom-0 w-px bg-border" />

        <div className="space-y-4">
          {items.length === 0 ? (
            <div className="ml-12 rounded-xl border border-border bg-surface-raised p-8 text-center">
              <p className="text-sm text-muted-foreground">
                Waiting for agent activity...
              </p>
              <p className="mt-1 text-xs text-muted-foreground/50">
                Create a campaign to see your agents in action.
              </p>
            </div>
          ) : (
            items.map((item, i) => (
              <div key={item.id || i} className="relative flex gap-4">
                {/* Timeline dot */}
                <div className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface-raised text-brand-400">
                  {getActionIcon(item.action_type)}
                </div>

                {/* Content */}
                <div className="flex-1 rounded-xl border border-border bg-surface-raised p-4 card-hover">
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className={`rounded-md px-2 py-0.5 text-[10px] font-bold uppercase ${
                        PLATFORM_COLORS[item.platform] || "text-muted-foreground bg-muted"
                      }`}
                    >
                      {item.platform}
                    </span>
                    <span className="text-[10px] text-muted-foreground uppercase font-medium">
                      {item.action_type}
                    </span>
                    {item.strategy_style && (
                      <span className="text-[10px] text-muted-foreground/70">
                        · {item.strategy_style}
                      </span>
                    )}
                  </div>

                  {/* Original post context */}
                  {item.post_text && (
                    <div className="mb-2 rounded-lg bg-muted/50 p-2.5 border-l-2 border-border">
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {item.post_text}
                      </p>
                    </div>
                  )}

                  {/* Agent's comment */}
                  <p className="text-sm text-foreground/70">{item.content}</p>

                  {/* Metrics */}
                  <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                    {item.latest_impressions > 0 && (
                      <span className="flex items-center gap-1">
                        <Eye className="h-3 w-3" />
                        {item.latest_impressions.toLocaleString()}
                      </span>
                    )}
                    {item.latest_likes > 0 && (
                      <span className="flex items-center gap-1">
                        <Heart className="h-3 w-3" />
                        {item.latest_likes}
                      </span>
                    )}
                    {item.post_url && (
                      <a
                        href={item.post_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-auto flex items-center gap-1 text-brand-400/50 hover:text-brand-400"
                      >
                        View post <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
