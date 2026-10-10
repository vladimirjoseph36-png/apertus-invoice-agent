"""
Apertus API client - Groq Inference.

Provides a thin wrapper around the Groq API (OpenAI-compatible)
to call an open-source LLM (GPT-OSS 20B by default).

Author:
    Anio Joseph

Project:
    Hack Apertus - October 2026
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from groq import Groq


class ApertusClient:
    """
    Simple client for LLM inference via Groq (OpenAI-compatible API).

    Attributes:
        model_id: Groq model identifier.
        api_key: Groq API key.
    """

    def __init__(self) -> None:
        self.model_id = os.getenv(
            "APERTUS_MODEL",
            "openai/gpt-oss-20b",
        )
        self.api_key = os.getenv("GROQ_API_KEY", "")

        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Add it to your .env file."
            )

        self.client = Groq(api_key=self.api_key)

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.8,
        top_p: float = 0.9,
    ) -> str:
        """
        Send a chat completion request to Groq.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            top_p: Nucleus sampling.

        Returns:
            The generated text response.
        """
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        return response.choices[0].message.content or ""

    def simple_chat(self, user_message: str) -> str:
        """
        Convenience method for a single-turn conversation.

        Args:
            user_message: The user's message.

        Returns:
            The model's response.
        """
        return self.chat(
            messages=[{"role": "user", "content": user_message}],
        )


__all__ = ["ApertusClient"]