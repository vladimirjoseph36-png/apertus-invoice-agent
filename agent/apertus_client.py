"""
Apertus API client - Dual mode: Groq (cloud) + Ollama (local, sovereign).

By default, uses Groq (fast cloud inference).
Set USE_LOCAL_APERTUS=true in .env to run 100% offline with Apertus 8B via Ollama.

Author:
    Anio Joseph

Project:
    Hack Apertus - October 2026
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()


def _is_local_mode() -> bool:
    """Check if local (Ollama) mode is enabled."""
    return os.getenv("USE_LOCAL_APERTUS", "false").lower() in ("true", "1", "yes")


class ApertusClient:
    """
    Dual-mode LLM client.

    - Cloud mode (default): Groq API (OpenAI-compatible)
    - Local mode (sovereign): Ollama + Apertus 8B (100% offline)

    Attributes:
        mode: "cloud" or "local"
        model_id: model identifier (Groq or Ollama)
    """

    def __init__(self) -> None:
        self.mode = "local" if _is_local_mode() else "cloud"

        if self.mode == "local":
            self._init_local()
        else:
            self._init_cloud()

    def _init_cloud(self) -> None:
        """Initialize the Groq cloud client."""
        from groq import Groq

        self.model_id = os.getenv("APERTUS_MODEL", "openai/gpt-oss-120b")
        self.api_key = os.getenv("GROQ_API_KEY", "")

        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Add it to your .env file, "
                "or set USE_LOCAL_APERTUS=true to use the local Apertus model."
            )

        self.client = Groq(api_key=self.api_key)
        print(f"[ApertusClient] Mode: CLOUD (Groq) - model={self.model_id}")

    def _init_local(self) -> None:
        """Initialize the Ollama local client."""
        try:
            from ollama import Client
        except ImportError:
            raise ImportError(
                "The 'ollama' package is required for local mode. "
                "Install it with: pip install ollama"
            )

        self.model_id = os.getenv(
            "OLLAMA_MODEL",
            "MichelRosselli/apertus:8b-instruct-2509-q4_k_m",
        )
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.client = Client(host=self.host)
        print(f"[ApertusClient] Mode: LOCAL (Ollama) - model={self.model_id}")

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1500,
        temperature: float = 0.3,
        top_p: float = 0.9,
    ) -> str:
        """
        Send a chat completion request (cloud or local).

        Args:
            messages: List of message dicts with 'role' and 'content'.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            top_p: Nucleus sampling.

        Returns:
            The generated text response.
        """
        if self.mode == "local":
            return self._chat_local(messages, max_tokens, temperature, top_p)
        return self._chat_cloud(messages, max_tokens, temperature, top_p)

    def _chat_cloud(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> str:
        """Send a request to Groq."""
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        return response.choices[0].message.content or ""

    def _chat_local(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> str:
        """Send a request to Ollama (local Apertus)."""
        try:
            response = self.client.chat(
                model=self.model_id,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                },
            )
            # Ollama returns a dict-like object
            if hasattr(response, "message"):
                return response.message.content or ""
            if isinstance(response, dict):
                return response.get("message", {}).get("content", "")
            return str(response)
        except Exception as e:
            return f"[Ollama error] {type(e).__name__}: {e}"

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

    def is_local(self) -> bool:
        """Return True if running in local (sovereign) mode."""
        return self.mode == "local"


__all__ = ["ApertusClient"]