/**
 * API client for communicating with the FastAPI backend.
 */

// Use relative paths so all requests go through the Next.js rewrite proxy
// (defined in next.config.ts: /api/:path* -> http://localhost:8000/api/:path*)
// This avoids CORS issues when the frontend and backend are on different ports.
const BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

// --- Campaigns ---
export interface CampaignCreate {
  name: string;
  product_name: string;
  product_description: string;
  target_audience?: string;
  platforms?: string[];
  // Pre-extracted data from /from-link — avoids re-extraction
  extracted_entities?: Record<string, any>;
  campaign_schema?: Record<string, any>;
  gliner_raw?: any[];
}

export const api = {
  // Campaigns
  createCampaign: (data: CampaignCreate) =>
    request<any>("/api/campaigns/", { method: "POST", body: JSON.stringify(data) }),

  listCampaigns: () => request<any>("/api/campaigns/"),

  getCampaign: (id: string) => request<any>(`/api/campaigns/${id}`),

  triggerCycle: (id: string) =>
    request<any>(`/api/campaigns/${id}/cycle`, { method: "POST" }),

  triggerLearning: (id: string) =>
    request<any>(`/api/campaigns/${id}/learn`, { method: "POST" }),

  triggerMetrics: (id: string) =>
    request<any>(`/api/campaigns/${id}/collect-metrics`, { method: "POST" }),

  pauseCampaign: (id: string) =>
    request<any>(`/api/campaigns/${id}/pause`, { method: "POST" }),

  resumeCampaign: (id: string) =>
    request<any>(`/api/campaigns/${id}/resume`, { method: "POST" }),

  // Activity
  getActivity: (limit = 50) =>
    request<any>(`/api/agents/activity?limit=${limit}`),

  // Strategies
  getStrategies: (minUsage = 1, limit = 10) =>
    request<any>(`/api/agents/strategies?min_usage=${minUsage}&limit=${limit}`),

  getStrategyEvolution: (id: string) =>
    request<any>(`/api/agents/strategies/${id}/evolution`),

  // Metrics
  getCampaignSummary: (id: string) =>
    request<any>(`/api/metrics/${id}/summary`),

  getStrategyPerformance: (id: string) =>
    request<any>(`/api/metrics/${id}/strategies`),

  getEngagementHistory: (id: string, limit = 50) =>
    request<any>(`/api/metrics/${id}/history?limit=${limit}`),

  getKnowledgeGraph: (id: string) =>
    request<any>(`/api/metrics/${id}/graph`),

  // Health
  getHealth: () => request<any>("/api/health"),
  getGatewayHealth: () => request<any>("/api/agents/health"),
};

// --- WebSocket ---
export function connectActivityWS(
  onMessage: (event: any) => void
): WebSocket {
  const wsUrl =
    process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/activity";
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      onMessage(data);
    } catch {
      console.warn("Failed to parse WS message:", evt.data);
    }
  };

  ws.onclose = () => {
    // Auto-reconnect after 3 seconds
    setTimeout(() => connectActivityWS(onMessage), 3000);
  };

  return ws;
}
