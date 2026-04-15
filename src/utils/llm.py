"""
PuzzleForge -- LLM call wrapper.

Centralizes all LLM calls so we can:
    1. Track token usage across agents
    2. Switch between live API and demo mode
    3. Enforce the 80K total token budget
"""

from __future__ import annotations
import json
from typing import Any, Dict, Optional
from src.config import OPENAI_API_KEY, OPENAI_MODEL, DEMO_MODE, MAX_TOTAL_TOKENS

# Running token counter shared across all calls in a pipeline run.
_cumulative_tokens: int = 0


class BudgetExceededError(Exception):
    """Raised when the cumulative token budget is exhausted."""
    pass


def reset_token_counter() -> None:
    """Reset at the start of each pipeline run."""
    global _cumulative_tokens
    _cumulative_tokens = 0


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Call the LLM and return {"content": str, "tokens_used": int}.

    Enforces the 80K token budget: if cumulative usage already exceeds
    MAX_TOTAL_TOKENS, raises BudgetExceededError. Each calling agent
    is responsible for catching this and setting pipeline_status.

    In demo mode, returns a placeholder indicating demo mode is active.
    """
    global _cumulative_tokens

    # Budget guard: refuse to call LLM if budget is already exhausted
    if _cumulative_tokens >= MAX_TOTAL_TOKENS:
        raise BudgetExceededError(
            f"Token budget exhausted ({_cumulative_tokens}/{MAX_TOTAL_TOKENS})"
        )

    if DEMO_MODE:
        return {
            "content": '{"demo": true, "note": "Demo mode -- replace with live API response"}',
            "tokens_used": 0,
        }

    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    kwargs: Dict[str, Any] = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format

    response = client.chat.completions.create(**kwargs)

    content = response.choices[0].message.content or ""
    tokens_used = response.usage.total_tokens if response.usage else 0
    _cumulative_tokens += tokens_used

    return {"content": content, "tokens_used": tokens_used}


def parse_json_response(raw: str) -> Dict[str, Any]:
    """Extract JSON from an LLM response, handling markdown code fences."""
    text = raw.strip()
    if text.startswith("```"):
        # Remove code fences
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)
