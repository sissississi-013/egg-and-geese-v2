/**
 * Instagram Agent — handles commenting and metrics collection
 * on Instagram via the Instagram Graph API or browser automation.
 *
 * Instagram's API is more restrictive, so this agent may use
 * Puppeteer-based browser automation as a fallback.
 */

import { logger } from "../index";

interface ExecuteParams {
  action: "comment" | "reply" | "repost";
  postUrl: string;
  content: string;
  parentCommentId?: string;
  metadata?: Record<string, any>;
}

/**
 * Extract Instagram post shortcode from URL.
 */
function extractIgShortcode(url: string): string {
  // https://www.instagram.com/p/SHORTCODE/ or /reel/SHORTCODE/
  const match = url.match(/\/(p|reel)\/([A-Za-z0-9_-]+)/);
  return match ? match[2] : "";
}

export const InstagramAgent = {
  /**
   * Execute an action on Instagram.
   *
   * Uses Instagram Graph API for business accounts or
   * Puppeteer browser automation for personal accounts.
   */
  async execute(params: ExecuteParams): Promise<Record<string, any>> {
    const { action, postUrl, content, parentCommentId } = params;
    const shortcode = extractIgShortcode(postUrl);

    logger.info(`Instagram: ${action} on post ${shortcode}`);

    // --- Instagram Graph API integration point ---
    // For business accounts:
    // POST /{media-id}/comments with message={content}
    //
    // --- Puppeteer fallback ---
    // const browser = await puppeteer.launch({ headless: true });
    // const page = await browser.newPage();
    // await page.goto(postUrl);
    // // ... interact with comment box ...

    switch (action) {
      case "comment":
        logger.info(`Instagram: would comment on ${shortcode}: "${content.substring(0, 50)}..."`);
        return {
          id: `ig_comment_${Date.now()}`,
          shortcode,
          action: "comment",
          content,
          status: "simulated",
        };

      case "reply":
        const replyTo = parentCommentId || shortcode;
        logger.info(`Instagram: would reply to ${replyTo}: "${content.substring(0, 50)}..."`);
        return {
          id: `ig_reply_${Date.now()}`,
          reply_to: replyTo,
          action: "reply",
          content,
          status: "simulated",
        };

      case "repost":
        // Instagram doesn't have native repost — would use Stories mention
        logger.info(`Instagram: would share ${shortcode} to story`);
        return {
          id: `ig_story_${Date.now()}`,
          shortcode,
          action: "story_share",
          content,
          status: "simulated",
        };

      default:
        throw new Error(`Unsupported action: ${action}`);
    }
  },

  /**
   * Collect engagement metrics for Instagram posts.
   */
  async collectMetrics(
    postIds: string[]
  ): Promise<Record<string, any>[]> {
    logger.info(`Instagram: collecting metrics for ${postIds.length} posts`);

    // --- Instagram Graph API integration point ---
    // GET /{media-id}?fields=like_count,comments_count,impressions

    return postIds.map((id) => ({
      post_id: id,
      impressions: Math.floor(Math.random() * 15000),
      likes: Math.floor(Math.random() * 500),
      replies: Math.floor(Math.random() * 60), // comments
      reposts: Math.floor(Math.random() * 20), // saves/shares
      clicks: Math.floor(Math.random() * 200),
      follower_delta: Math.floor(Math.random() * 15) - 3,
      status: "simulated",
    }));
  },
};
