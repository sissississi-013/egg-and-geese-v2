/**
 * OpenClaw Execution Gateway — Egg & Geese v2
 *
 * Node.js service that handles actual social media interactions:
 * posting, commenting, replying, reposting, and metrics collection
 * across Twitter, Reddit, and Instagram.
 *
 * Exposes an HTTP API that the Python orchestrator calls.
 */

import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { v4 as uuidv4 } from "uuid";
import { TwitterAgent } from "./agents/twitter";
import { RedditAgent } from "./agents/reddit";
import { InstagramAgent } from "./agents/instagram";
import { startHeartbeat, stopHeartbeat } from "./heartbeat";
import { createBridgeRouter } from "./bridge";
import winston from "winston";

dotenv.config();

// ---------------------------------------------------------------------------
// Logger
// ---------------------------------------------------------------------------
export const logger = winston.createLogger({
  level: "info",
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(
      ({ timestamp, level, message }) =>
        `${timestamp} | gateway | ${level.toUpperCase().padEnd(7)} | ${message}`
    )
  ),
  transports: [new winston.transports.Console()],
});

// ---------------------------------------------------------------------------
// Platform agent registry
// ---------------------------------------------------------------------------
export const platformAgents: Record<
  string,
  { execute: Function; collectMetrics: Function }
> = {
  twitter: TwitterAgent,
  reddit: RedditAgent,
  instagram: InstagramAgent,
};

// ---------------------------------------------------------------------------
// Express app
// ---------------------------------------------------------------------------
const app = express();
app.use(cors());
app.use(express.json());

// Health check
app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", service: "gateway", uptime: process.uptime() });
});

// Mount the bridge router (handles /api/execute, /api/metrics)
app.use(createBridgeRouter());

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
const PORT = parseInt(process.env.GATEWAY_PORT || "3001", 10);

app.listen(PORT, () => {
  logger.info(`OpenClaw Gateway listening on port ${PORT}`);

  // Start heartbeat daemon (configurable interval)
  const heartbeatMinutes = parseInt(
    process.env.HEARTBEAT_INTERVAL_MINUTES || "30",
    10
  );
  startHeartbeat(heartbeatMinutes);
});

// Graceful shutdown
process.on("SIGTERM", () => {
  logger.info("Shutting down gateway...");
  stopHeartbeat();
  process.exit(0);
});
