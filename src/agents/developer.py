"""
PuzzleForge -- Developer / Orchestrator Agent (Implementation Layer)

Purpose: Translate design into game config for the template engine. Manage handoffs
         and routing between agents. Enforce budget/iteration caps.
Tools:   Template engine integration, state management, trace logging. LLM at temp 0.4.
Hard:    Never exceed 3 debug cycles. Never exceed 80K token budget. Never skip QA.
Soft:    Stop early if all levels pass QA. Prefer minimal config changes over full redesigns.
"""

from __future__ import annotations
import time
from typing import Any, Dict, List

from src.config import TEMP_DEVELOPER
from src.models import GameConfig, LevelConfig
from src.utils.trace_logger import make_trace_entry


def developer_translate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate game spec + level definitions into a GameConfig for the template engine.
    This is a deterministic translation, not LLM-based.
    """
    t0 = time.time()
    game_spec = state["game_spec"]
    level_defs = state["level_definitions"]

    levels = []
    for i, ld in enumerate(level_defs):
        prog = game_spec["progression_plan"][i] if i < len(game_spec["progression_plan"]) else {}
        levels.append(LevelConfig(
            level_id=ld["level_id"],
            title=f"Level {ld['level_id']}",
            grid_width=ld["grid_width"],
            grid_height=ld["grid_height"],
            walls=[tuple(w) for w in ld["walls"]],
            boxes=[tuple(b) for b in ld["boxes"]],
            targets=[tuple(t) for t in ld["targets"]],
            player_start=tuple(ld["player_start"]),
            mechanics_active=prog.get("new_mechanics", ["push"]),
        ).model_dump())

    # Extract primary mechanic from the game spec
    mechanics_list = game_spec.get("mechanics", [])
    primary_mechanic = "push"
    if mechanics_list:
        first_mech = mechanics_list[0]
        if isinstance(first_mech, dict):
            primary_mechanic = first_mech.get("name", "push")
        elif isinstance(first_mech, str):
            primary_mechanic = first_mech

    game_config = GameConfig(
        game_title=f"PuzzleForge: {game_spec['theme']}",
        puzzle_type=game_spec["puzzle_type"],
        theme=game_spec["theme"],
        win_condition=game_spec["win_condition"],
        levels=levels,
        primary_mechanic=primary_mechanic,
        theme_details=game_spec.get("theme_details"),
    ).model_dump()

    duration = time.time() - t0
    trace = make_trace_entry(
        step=len(state.get("trace_log", [])) + 1,
        agent="Developer",
        action="translate_to_config",
        input_summary=f"Translating {len(level_defs)} level defs + game spec",
        output_summary=f"Produced GameConfig with {len(levels)} levels",
        tokens_used=0,
        duration_seconds=duration,
    )

    return {
        "game_config": game_config,
        "trace_log": [trace],
    }


def developer_apply_patches_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply Debugger patches to the game config.
    Replace level data for patched levels.
    """
    t0 = time.time()
    game_config = state["game_config"]
    patches = state.get("debug_patches", [])
    cycle = state.get("debug_cycle", 0)

    if not patches:
        return {}

    # Only apply patches from the CURRENT debug cycle.
    # Patches accumulate via operator.add across cycles, so we filter
    # by the level IDs that were just routed to the Debugger this cycle.
    failed_ids = set(state.get("failed_level_ids", []))
    recent_patches = [p for p in patches if p.get("level_id") in failed_ids]
    if not recent_patches:
        return {}

    levels = list(game_config["levels"])
    patched_ids = []

    for patch in recent_patches:
        lid = patch["level_id"]
        for i, lvl in enumerate(levels):
            if lvl["level_id"] == lid:
                levels[i] = {
                    **lvl,
                    "walls": [tuple(w) for w in patch["patched_walls"]],
                    "boxes": [tuple(b) for b in patch["patched_boxes"]],
                    "targets": [tuple(t) for t in patch["patched_targets"]],
                    "player_start": tuple(patch["patched_player_start"]),
                }
                patched_ids.append(lid)
                break

    game_config = {**game_config, "levels": levels}

    duration = time.time() - t0
    trace = make_trace_entry(
        step=len(state.get("trace_log", [])) + 1,
        agent="Developer",
        action="apply_debug_patches",
        input_summary=f"Applying {len(recent_patches)} patches",
        output_summary=f"Patched levels: {patched_ids}",
        tokens_used=0,
        duration_seconds=duration,
    )

    return {
        "game_config": game_config,
        "trace_log": [trace],
    }
