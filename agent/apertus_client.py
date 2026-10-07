"""
Apertus API client — Hugging Face Inference.

Provides a thin wrapper around the Hugging Face InferenceClient
to call the Apertus model (Swiss sovereign LLM).

Author:
    Anio Joseph

Project:
    Hack Apertus — October 2026
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from huggingface_hub import InferenceClient


class ApertusClient:
    """
    Simple client for the Apertus model via Hugging Face Inference.

    Attributes:
        model_id: Hugging Face model identifier.
        token: Hugging Face access token.
    """

    def __init__(self) -> None:
        self.model_id = os.getenv(
            "APERTUS_MODEL",
            "swiss-ai/Apertus-8B-Instruct-2509",
        )
        self.token = os.getenv("HF_TOKEN", "")

        if not self.token:
            raise ValueError(
                "HF_TOKEN is not set. Add it to your .env file."
            )

        self.client = InferenceClient(
            model=self.model_id,
            token=self.token,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.8,
        top_p: float = 0.9,
    ) -> str:
        """
        Send a chat completion request to Apertus.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.8 recommended).
            top_p: Nucleus sampling (0.9 recommended).

        Returns:
            The generated text response.
        """
        response = self.client.chat_completion(
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