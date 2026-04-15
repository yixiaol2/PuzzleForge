"""
PuzzleForge -- LangGraph Pipeline Definition

This module defines the full orchestration graph using LangGraph's StateGraph.
The Developer agent's coordination logic is encoded as conditional edges,
making the flow explicit, auditable, and reproducible.

Pipeline flow:
    User Input --> Game Designer --> Level Designer --> Developer (translate)
    --> QA Tester --> [route_after_qa] -->
        all_pass   --> Finalize
        has_failures --> Developer (classify & route) -->
            config_bugs  --> Debugger --> Apply Patches --> QA Tester (re-test)
            design_flaws --> Level Designer (redesign) --> Developer --> QA Tester
            max_cycles   --> Finalize (with remaining failures logged)
"""

from __future__ import annotations
import time
import json
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, END

from src.state import PipelineState
from src.agents.game_designer import game_designer_node
from src.agents.level_designer import level_designer_node
from src.agents.developer import developer_translate_node, developer_apply_patches_node
from src.agents.qa_tester import qa_tester_node
from src.agents.debugger import debugger_node
from src.orchestrator.routing import classify_all_failures
from src.engine.template_engine import render_game
import src.config as _cfg
from src.utils.trace_logger import make_trace_entry


# -- Routing nodes -----------------------------------------------------

def developer_route_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Developer's routing logic: classify each failed level and record decisions.
    Uses formal criteria from routing.py -- no LLM involved.
    """
    t0 = time.time()
    failed_ids = state.get("failed_level_ids", [])

    if not failed_ids:
        return {"routing_decisions": [], "levels_needing_redesign": []}

    decisions = classify_all_failures(
        game_config=state["game_config"],
        qa_report=state["qa_report"],
        failed_ids=failed_ids,
    )

    # Separate config bugs from design flaws
    config_bug_ids = [d["level_id"] for d in decisions if d["failure_type"] == "config_bug"]
    design_flaw_ids = [d["level_id"] for d in decisions if d["failure_type"] == "design_flaw"]

    duration = time.time() - t0
    trace = make_trace_entry(
        step=len(state.get("trace_log", [])) + 1,
        agent="Developer",
        action="classify_and_route_failures",
        input_summary=f"Classifying {len(failed_ids)} failed levels",
        output_summary=f"Config bugs: {config_bug_ids}, Design flaws: {design_flaw_ids}",
        tokens_used=0,
        duration_seconds=duration,
    )

    return {
        "routing_decisions": decisions,
        "failed_level_ids": config_bug_ids,  # Only config bugs go to debugger
        "levels_needing_redesign": design_flaw_ids,
        "trace_log": [trace],
    }


def finalize_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Package the final game: render HTML, compile design document."""
    t0 = time.time()
    game_config = state.get("game_config")

    # Render HTML game
    html_output = ""
    if game_config:
        try:
            html_output = render_game(game_config)
        except Exception as e:
            html_output = f"<!-- Render error: {e} -->"

    # Compile design document
    design_doc = {
        "game_spec": state.get("game_spec"),
        "level_definitions": state.get("level_definitions"),
        "game_config": game_config,
        "qa_report": state.get("qa_report"),
        "routing_decisions": state.get("routing_decisions", []),
        "debug_patches": state.get("debug_patches", []),
        "debug_cycles_used": state.get("debug_cycle", 0),
        "total_tokens": state.get("total_tokens", 0),
        "pipeline_duration_seconds": round(time.time() - state.get("start_time", time.time()), 2),
    }

    duration = time.time() - t0
    trace = make_trace_entry(
        step=len(state.get("trace_log", [])) + 1,
        agent="Developer",
        action="finalize_game",
        input_summary="Packaging final game output",
        output_summary=f"HTML: {len(html_output)} chars, design doc compiled",
        tokens_used=0,
        duration_seconds=duration,
    )

    # Determine accurate terminal status.
    # Preserve budget_exceeded / timeout if already set by an upstream node.
    existing_status = state.get("pipeline_status", "running")
    if existing_status in ("budget_exceeded", "timeout"):
        status = existing_status
    else:
        failed_ids = state.get("failed_level_ids", [])
        cycles = state.get("debug_cycle", 0)
        tokens = state.get("total_tokens", 0)
        elapsed = time.time() - state.get("start_time", time.time())
        if elapsed >= _cfg.PIPELINE_TIMEOUT_SECONDS:
            status = "timeout"
        elif tokens >= _cfg.MAX_TOTAL_TOKENS:
            status = "budget_exceeded"
        elif failed_ids and cycles >= _cfg.MAX_DEBUG_CYCLES:
            status = "completed_with_failures"
        else:
            status = "completed"

    return {
        "final_game_html": html_output,
        "final_design_doc": design_doc,
        "pipeline_status": status,
        "trace_log": [trace],
    }


def increment_cycle_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Increment the debug cycle counter."""
    return {"debug_cycle": state.get("debug_cycle", 0) + 1}


# -- Conditional edge functions ----------------------------------------

def route_after_qa(state: Dict[str, Any]) -> str:
    """After QA testing, decide: all pass --> finalize, or route failures."""
    failed = state.get("failed_level_ids", [])
    if not failed:
        return "all_pass"
    if state.get("debug_cycle", 0) >= _cfg.MAX_DEBUG_CYCLES:
        return "max_cycles"
    if state.get("total_tokens", 0) >= _cfg.MAX_TOTAL_TOKENS:
        return "budget_exceeded"
    elapsed = time.time() - state.get("start_time", time.time())
    if elapsed >= _cfg.PIPELINE_TIMEOUT_SECONDS:
        return "timeout"

    # If all levels are solvable and only diversity issues remain,
    # treat as soft failure: attempt one fix cycle, then accept.
    qa_report = state.get("qa_report", {})
    all_solvable = all(
        lr.get("solvable", False)
        for lr in qa_report.get("level_reports", [])
    )
    if all_solvable and state.get("debug_cycle", 0) >= 1:
        # Already tried to fix diversity once; accept the result
        return "all_pass"

    return "has_failures"


def _check_budget_status(state: Dict[str, Any]) -> str:
    """Route to finalize if any node set pipeline_status to budget_exceeded."""
    if state.get("pipeline_status") == "budget_exceeded":
        return "budget_exceeded"
    return "continue"


def route_after_debug(state: Dict[str, Any]) -> str:
    """After debugging, decide: redesign needed, or re-test."""
    redesign_ids = state.get("levels_needing_redesign", [])
    if redesign_ids:
        return "needs_redesign"
    return "retest"


# -- Graph construction ------------------------------------------------

def build_pipeline() -> StateGraph:
    """
    Construct the PuzzleForge LangGraph pipeline.

    Returns a compiled StateGraph ready for .invoke().
    """
    graph = StateGraph(PipelineState)

    # -- Add nodes --
    graph.add_node("game_designer", game_designer_node)
    graph.add_node("level_designer", level_designer_node)
    graph.add_node("developer_translate", developer_translate_node)
    graph.add_node("qa_tester", qa_tester_node)
    graph.add_node("developer_route", developer_route_node)
    graph.add_node("debugger", debugger_node)
    graph.add_node("apply_patches", developer_apply_patches_node)
    graph.add_node("increment_cycle", increment_cycle_node)
    graph.add_node("finalize", finalize_node)

    # -- Entry point --
    graph.set_entry_point("game_designer")

    # -- Design Layer (with budget guards) --
    graph.add_conditional_edges(
        "game_designer",
        _check_budget_status,
        {"continue": "level_designer", "budget_exceeded": "finalize"},
    )
    graph.add_conditional_edges(
        "level_designer",
        _check_budget_status,
        {"continue": "developer_translate", "budget_exceeded": "finalize"},
    )
    graph.add_edge("developer_translate", "qa_tester")

    # -- Conditional: after QA testing --
    graph.add_conditional_edges(
        "qa_tester",
        route_after_qa,
        {
            "all_pass": "finalize",
            "has_failures": "developer_route",
            "max_cycles": "finalize",
            "budget_exceeded": "finalize",
            "timeout": "finalize",
        },
    )

    # -- Developer routes failures --
    graph.add_edge("developer_route", "increment_cycle")
    graph.add_edge("increment_cycle", "debugger")

    # -- Debugger --> apply patches --> check for redesign --
    graph.add_edge("debugger", "apply_patches")
    graph.add_conditional_edges(
        "apply_patches",
        route_after_debug,
        {
            "needs_redesign": "level_designer",
            "retest": "qa_tester",
        },
    )

    # -- Finalize --> END --
    graph.add_edge("finalize", END)

    return graph.compile()


# -- Convenience runner ------------------------------------------------

def run_pipeline(
    user_concept: str,
    max_debug_cycles: int | None = None,
    level_count: int | None = None,
) -> Dict[str, Any]:
    """
    Run the full PuzzleForge pipeline and return the final state.

    Args:
        user_concept: Free-text game concept from the user.
        max_debug_cycles: Override MAX_DEBUG_CYCLES (default from config).
        level_count: Override DEFAULT_LEVEL_COUNT (default from config).
    """
    # Apply overrides for this run (mutates the live module object
    # that _cfg already references, so all call-time reads see the new value)
    if max_debug_cycles is not None:
        _cfg.MAX_DEBUG_CYCLES = max_debug_cycles
    if level_count is not None:
        _cfg.DEFAULT_LEVEL_COUNT = level_count

    from src.state import initial_state
    from src.utils.llm import reset_token_counter

    reset_token_counter()

    pipeline = build_pipeline()
    init = initial_state(user_concept)
    final_state = pipeline.invoke(init)
    return final_state
