/**
 * Heartbeat Daemon — autonomous scheduling for the OpenClaw gateway.
 *
 * Runs on a configurable interval (default: 30 min) and notifies
 * the Python orchestrator to trigger metrics collection and
 * learning cycles.
 */

import cron from "node-cron";
import { logger } from "./index";

let heartbeatTask: cron.ScheduledTask | null = null;

/**
 * Notify the Python orchestrator that a heartbeat has occurred.
 */
async function notifyOrchestrator(): Promise<void> {
  const orchestratorUrl =
    process.env.ORCHESTRATOR_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${orchestratorUrl}/api/health`);
    if (response.ok) {
      logger.info("Heartbeat: orchestrator is healthy");
    } else {
      logger.warn(`Heartbeat: orchestrator returned ${response.status}`);
    }
  } catch (err: any) {
    logger.error(`Heartbeat: orchestrator unreachable — ${err.message}`);
  }
}

/**
 * Start the heartbeat daemon.
 *
 * @param intervalMinutes - How often to beat (default: 30)
 */
export function startHeartbeat(intervalMinutes: number = 30): void {
  if (heartbeatTask) {
    logger.warn("Heartbeat already running");
    return;
  }

  // node-cron expression: every N minutes
  const cronExpr = `*/${intervalMinutes} * * * *`;

  heartbeatTask = cron.schedule(cronExpr, async () => {
    logger.info(`Heartbeat tick (every ${intervalMinutes}min)`);
    await notifyOrchestrator();
  });

  logger.info(
    `Heartbeat daemon started — ticking every ${intervalMinutes} minutes`
  );
}

/**
 * Stop the heartbeat daemon.
 */
export function stopHeartbeat(): void {
  if (heartbeatTask) {
    heartbeatTask.stop();
    heartbeatTask = null;
    logger.info("Heartbeat daemon stopped");
  }
}
