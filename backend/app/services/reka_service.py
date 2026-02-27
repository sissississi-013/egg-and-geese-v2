"""Reka Vision API client for visual context analysis of social media posts.

Reka (https://docs.reka.ai) provides multimodal AI with:
  - Chat:   Text + image + video + audio Q&A
  - Vision: Advanced video understanding
  - Clip:   AI-powered video highlight generation
  - Speech: Transcription and translation

We use the **Chat API** with multimodal inputs to analyze images/video
in scouted social media posts before our agents comment on them.

Auth: X-Api-Key header.
Base URL: https://api.reka.ai
Endpoint: POST /v1/chat
Models: reka-flash (fast/cheap), reka-core (powerful), reka-spark (compact)
Python SDK: pip install "reka-api>=2.0.0"
Response: data["responses"][0]["message"]["content"]
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class RekaVisionService:
    """Visual Scout — analyzes images/video in scouted posts via Reka.

    Key integration point: before an agent comments on a post, Reka
    confirms that the visual content matches the product's target
    problem (e.g. oily hair texture) and enriches the context so
    the generated comment can reference visual details.
    """

    BASE_URL = settings.reka_base_url  # https://api.reka.ai

    @classmethod
    def _headers(cls) -> dict[str, str]:
        return {
            "X-Api-Key": settings.reka_api_key,
            "Content-Type": "application/json",
        }

    @classmethod
    async def _chat(
        cls,
        messages: list[dict[str, Any]],
        model: str = "reka-flash",
        max_tokens: int = 1024,
    ) -> str:
        """Low-level call to POST /v1/chat.

        Returns the text content of the first response.
        """
        payload = {
            "model": model,
            "messages": messages,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/v1/chat",
                json=payload,
                headers=cls._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

            # Reka response format: {"responses": [{"message": {"content": "..."}}]}
            responses = data.get("responses", [])
            if responses:
                return responses[0].get("message", {}).get("content", "")

            # Fallback: try OpenAI-like format just in case
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")

            logger.warning("Unexpected Reka response format: %s", list(data.keys()))
            return str(data)

    @classmethod
    async def analyze_image(
        cls,
        image_url: str,
        questions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Analyze an image by URL using Reka's multimodal chat.

        Args:
            image_url: Public URL of the image to analyze.
            questions: List of questions to ask about the image.
                       Defaults to problem-identification questions.

        Returns:
            Dict with raw answer and the questions asked.
        """
        if questions is None:
            questions = [
                "What problem or issue is shown in this image?",
                "What products or brands are visible?",
                "What is the emotional tone or sentiment of this image?",
                "Describe the visual details relevant to hair or skin care.",
            ]

        # Reka multimodal message format
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": image_url},
                    {
                        "type": "text",
                        "text": "\n".join(
                            f"{i+1}. {q}" for i, q in enumerate(questions)
                        ),
                    },
                ],
            }
        ]

        answer = await cls._chat(messages)
        return {"raw_answer": answer, "questions": questions}

    @classmethod
    async def analyze_video(
        cls,
        video_url: str,
        question: str = "What is happening in this video and what problem is being discussed?",
    ) -> dict[str, Any]:
        """Analyze a video URL via Reka's multimodal chat.

        Useful for TikTok reposts, hair-routine videos, etc.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "video_url", "video_url": video_url},
                    {"type": "text", "text": question},
                ],
            }
        ]

        answer = await cls._chat(messages, model="reka-flash")
        return {"raw_answer": answer, "question": question}

    @classmethod
    async def confirm_visual_context(
        cls,
        media_urls: list[str],
        expected_context: str,
    ) -> dict[str, Any]:
        """High-level helper: check whether post media matches the expected
        product context (e.g. "oily hair problem").

        Returns a dict with:
            - matches: bool – whether the visual confirms the context
            - visual_summary: str – description of what's in the media
            - confidence: float – how confident the match is
        """
        if not media_urls:
            return {
                "matches": False,
                "visual_summary": "No media to analyze",
                "confidence": 0.0,
            }

        # Analyze first media item (most impactful)
        url = media_urls[0]
        is_video = any(
            url.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm")
        )

        if is_video:
            result = await cls.analyze_video(
                url,
                f"Does this video show or discuss: {expected_context}? "
                "Describe what you see in detail.",
            )
        else:
            result = await cls.analyze_image(
                url,
                questions=[
                    f"Does this image show or relate to: {expected_context}?",
                    "Describe the visual details you can see.",
                    "What is the emotional tone?",
                ],
            )

        answer = result.get("raw_answer", "").lower()
        matches = any(
            kw in answer
            for kw in expected_context.lower().split()
        )

        return {
            "matches": matches,
            "visual_summary": result.get("raw_answer", ""),
            "confidence": 0.8 if matches else 0.2,
            "media_url": url,
        }

    @classmethod
    async def describe_image_for_comment(
        cls,
        image_url: str,
        product_context: str,
    ) -> str:
        """Generate a brief visual description for enriching agent comments.

        This is used to add visual references to humanized comments,
        making them feel more personal and contextually aware.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": image_url},
                    {
                        "type": "text",
                        "text": (
                            f"Context: {product_context}\n\n"
                            "In 1-2 sentences, describe what you see in this image "
                            "that relates to the context above. Focus on details a "
                            "helpful commenter might reference naturally."
                        ),
                    },
                ],
            }
        ]

        return await cls._chat(messages, max_tokens=200)
