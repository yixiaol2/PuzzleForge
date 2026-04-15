"""
PuzzleForge -- LangGraph global state schema.

This TypedDict is the single source of truth shared across all agents.
The Developer/Orchestrator maintains this state; other agents read from and
write to specific fields via the LangGraph node return convention.

Design decision (addressing Phase 1 feedback item #2):
    We use LangGraph's TypedDict + Annotated[..., operator.add] pattern so that
    list fields (traces, routing decisions, debug patches) accumulate across
    nodes without overwriting earlier entries.
"""

from __future__ import annotations
import operator
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict


class PipelineState(TypedDict, total=False):
    """
    Global shared state for the PuzzleForge LangGraph pipeline.

    Fields are grouped by pipeline stage. Annotated lists use operator.add
    so each node *appends* rather than replaces.
    """

    # -- User input ----------------------------------------------------
    user_concept: str                          # Free-text game concept from user

    # -- Game Designer output ------------------------------------------
    game_spec: Optional[Dict[str, Any]]        # Validated GameSpec as dict

    # -- Level Designer output -----------------------------------------
    level_definitions: Optional[List[Dict[str, Any]]]  # List of LevelDefinition dicts

    # -- Developer output ----------------------------------------------
    game_config: Optional[Dict[str, Any]]      # GameConfig dict for template engine

    # -- QA Tester output ----------------------------------------------
    qa_report: Optional[Dict[str, Any]]        # Full QAReport dict

    # -- Routing & debug -----------------------------------------------
    routing_decisions: Annotated[List[Dict[str, Any]], operator.add]
    debug_patches: Annotated[List[Dict[str, Any]], operator.add]
    failed_level_ids: List[int]                # Levels that failed QA this cycle
    levels_needing_redesign: List[int]         # Levels routed to Level Designer

    # -- Pipeline control ----------------------------------------------
    debug_cycle: int                           # Current cycle (0-based, max 3)
    pipeline_status: str                       # "running" | "completed" | "completed_with_failures" | "budget_exceeded" | "timeout"

    # -- Observability -------------------------------------------------
    trace_log: Annotated[List[Dict[str, Any]], operator.add]  # Append-only trace
    total_tokens: int
    start_time: float

    # -- Final output --------------------------------------------------
    final_game_html: Optional[str]             # Rendered HTML/JS game
    final_design_doc: Optional[Dict[str, Any]] # Structured design document


def initial_state(user_concept: str) -> PipelineState:
    """Factory for a fresh pipeline state."""
    import time
    return PipelineState(
        user_concept=user_concept,
        game_spec=None,
        level_definitions=None,
        game_config=None,
        qa_report=None,
        routing_decisions=[],
        debug_patches=[],
        failed_level_ids=[],
        levels_needing_redesign=[],
        debug_cycle=0,
        pipeline_status="running",
        trace_log=[],
        total_tokens=0,
        start_time=time.time(),
        final_game_html=None,
        final_design_doc=None,
    )
