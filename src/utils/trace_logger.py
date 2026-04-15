"""
PuzzleForge -- Trace logging utility.

Every agent call is recorded as a TraceEntry appended to the pipeline state.
This produces the interaction traces required for Phase 2 and Phase 3 evidence.
"""

from __future__ import annotations
import time
from typing import Any, Dict


def make_trace_entry(
    step: int,
    agent: str,
    action: str,
    input_summary: str,
    output_summary: str,
    tokens_used: int = 0,
    duration_seconds: float = 0.0,
) -> Dict[str, Any]:
    """Create a trace entry dict compatible with PipelineState.trace_log."""
    return {
        "step": step,
        "agent": agent,
        "action": action,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "tokens_used": tokens_used,
        "duration_seconds": round(duration_seconds, 3),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def format_trace_log(trace_log: list) -> str:
    """Pretty-print the trace log for display."""
    lines = []
    for entry in trace_log:
        lines.append(
            f"[Step {entry['step']}] {entry['agent']} -- {entry['action']}\n"
            f"  Input:  {entry['input_summary'][:120]}\n"
            f"  Output: {entry['output_summary'][:120]}\n"
            f"  Tokens: {entry['tokens_used']}  Time: {entry['duration_seconds']}s"
        )
    return "\n\n".join(lines)
