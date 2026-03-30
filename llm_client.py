"""
LLM Client
==========
Single place to configure which LLM backend the agents use.
Switch between Ollama (local) and Anthropic by changing BACKEND below.

Ollama runs an OpenAI-compatible API at http://localhost:11434/v1
so we use the openai SDK pointed at that base URL.
"""

import os
import json
import requests
from rich.console import Console

console = Console()

# ── Configuration ─────────────────────────────────────────────────
BACKEND = os.environ.get("AGENT_BACKEND", "ollama")   # "ollama" | "anthropic"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL",    "mistral")
# ──────────────────────────────────────────────────────────────────


class LLMClient:
    """
    Thin wrapper so agents call self.llm.chat(prompt) regardless
    of whether we're using Ollama or Anthropic.
    """

    def __init__(self):
        self.backend = BACKEND
        if BACKEND == "anthropic":
            from anthropic import Anthropic
            self._anthropic = Anthropic()
        else:
            self._check_ollama()

    def _check_ollama(self):
        try:
            r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            models = [m["name"].split(":")[0] for m in r.json().get("models", [])]
            if OLLAMA_MODEL not in models:
                console.print(
                    f"[yellow]⚠  Model '{OLLAMA_MODEL}' not found in Ollama. "
                    f"Available: {models}. Run: ollama pull {OLLAMA_MODEL}[/yellow]"
                )
            else:
                console.print(f"  [dim]🦙 Ollama ready — model: {OLLAMA_MODEL}[/dim]")
        except Exception as e:
            console.print(f"[red]⚠  Cannot reach Ollama at {OLLAMA_BASE_URL}: {e}[/red]")
            console.print("[dim]   Make sure Ollama is running: ollama serve[/dim]")

    def chat(self, prompt: str, max_tokens: int = 1500, system: str = None) -> str:
        """Send a prompt and return the text response."""
        if self.backend == "anthropic":
            return self._anthropic_chat(prompt, max_tokens, system)
        else:
            return self._ollama_chat(prompt, max_tokens, system)

    def _ollama_chat(self, prompt: str, max_tokens: int, system: str) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model":   OLLAMA_MODEL,
            "messages": messages,
            "stream":  False,
            "options": {"num_predict": max_tokens},
        }

        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
        except requests.exceptions.Timeout:
            return '{"error": "Ollama request timed out. Try a shorter prompt."}'
        except Exception as e:
            return f'{{"error": "Ollama error: {e}"}}'

    def _anthropic_chat(self, prompt: str, max_tokens: int, system: str) -> str:
        kwargs = {
            "model": "claude-opus-4-5",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        resp = self._anthropic.messages.create(**kwargs)
        return resp.content[0].text.strip()


# Singleton shared by all agents
llm = LLMClient()
