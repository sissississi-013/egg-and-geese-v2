/**
 * Bridge Router — HTTP API that the Python orchestrator calls.
 *
 * Endpoints:
 *   POST /api/execute   — Execute a social media action
 *   POST /api/metrics   — Collect metrics for posts
 */

import { Router, Request, Response } from "express";
import { v4 as uuidv4 } from "uuid";
import { platformAgents, logger } from "./index";

interface ExecuteRequest {
  action: "comment" | "reply" | "repost";
  platform: string;
  post_url: string;
  content: string;
  parent_comment_id?: string;
  metadata?: Record<string, any>;
}

interface MetricsRequest {
  action: "collect_metrics";
  platform: string;
  post_ids: string[];
}

export function createBridgeRouter(): Router {
  const router = Router();

  // ── Execute an action ──
  router.post("/api/execute", async (req: Request, res: Response) => {
    const body = req.body as ExecuteRequest;
    const { action, platform, post_url, content, parent_comment_id, metadata } =
      body;

    logger.info(
      `Execute: ${action} on ${platform} — ${post_url.substring(0, 60)}...`
    );

    const agent = platformAgents[platform];
    if (!agent) {
      res.status(400).json({ error: `Unsupported platform: ${platform}` });
      return;
    }

    try {
      const result = await agent.execute({
        action,
        postUrl: post_url,
        content,
        parentCommentId: parent_comment_id,
        metadata: metadata || {},
      });

      const platformPostId = result?.id || uuidv4();

      logger.info(
        `Execute success: ${action} on ${platform} — id=${platformPostId}`
      );

      res.json({
        status: "success",
        platform_post_id: platformPostId,
        platform,
        action,
        result,
      });
    } catch (err: any) {
      logger.error(`Execute failed: ${action} on ${platform} — ${err.message}`);
      res.status(500).json({
        status: "error",
        error: err.message,
        platform,
        action,
      });
    }
  });

  // ── Collect metrics ──
  router.post("/api/metrics", async (req: Request, res: Response) => {
    const body = req.body as MetricsRequest;
    const { platform, post_ids } = body;

    logger.info(
      `Metrics: collecting for ${post_ids.length} posts on ${platform}`
    );

    const agent = platformAgents[platform];
    if (!agent) {
      res.status(400).json({ error: `Unsupported platform: ${platform}` });
      return;
    }

    try {
      const metrics = await agent.collectMetrics(post_ids);
      res.json({ metrics, platform });
    } catch (err: any) {
      logger.error(`Metrics failed for ${platform}: ${err.message}`);
      res.status(500).json({ error: err.message, platform });
    }
  });

  return router;
}
