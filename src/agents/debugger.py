"""
PuzzleForge -- Debugger Agent (Implementation Layer)

Purpose: Make targeted fixes to configuration based on QA failure reports.
Tools:   LLM reasoning at low temperature (0.3) for precise edits.
Hard:    Never modify game mechanics or progression plan; only adjust tile/entity positions.
Soft:    Prefer moving one entity over restructuring the grid; minimize changes.
Gated:   If fix requires changing > 25% of tiles, flag as 'design flaw' and return.
"""

from __future__ import annotations
import json
import time
from typing import Any, Dict, List

from src.config import TEMP_DEBUGGER, ROUTING_TILE_CHANGE_THRESHOLD
from src.utils.llm import call_llm, parse_json_response, BudgetExceededError
from src.utils.trace_logger import make_trace_entry

SYSTEM_PROMPT = """You are the Debugger for PuzzleForge, a multi-agent puzzle game generation system.

Your job: Given a QA failure report and the current level configuration, make the MINIMAL
change needed to fix the issue. You may only adjust tile and entity positions. You must NOT
change game mechanics, add new entities beyond what exists, or fundamentally redesign the level.

RULES:
1. Change as few tiles as possible (ideally 1-3 tiles).
2. Keep the level's original structure and intent intact.
3. Common fixes: move a wall to open a path, reposition a box, adjust player start,
   move a target to a reachable position.
4. If you determine the fix requires changing more than 25% of the level's non-wall tiles,
   output {"escalate": true, "reason": "..."} instead of a patch.

OUTPUT FORMAT: Return a JSON object:
{
  "level_id": <int>,
  "change_description": "<what you changed>",
  "rationale": "<why this fix works>",
  "tiles_modified": <int count of changed tiles>,
  "changes": [{"x": <int>, "y": <int>, "old_type": "<wall|floor|box|target>", "new_type": "<...>"}],
  "patched_walls": [[x,y], ...],
  "patched_boxes": [[x,y], ...],
  "patched_targets": [[x,y], ...],
  "patched_player_start": [x, y]
}

Or if escalating: {"escalate": true, "reason": "<why redesign is needed>", "level_id": <int>}"""


def debugger_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Debugger agent.

    Processes each failed level that was routed as a 'config_bug' by the Developer.
    Produces patches or escalation flags.
    """
    t0 = time.time()
    game_config = state["game_config"]
    qa_report = state.get("qa_report", {})
    routing_decisions = state.get("routing_decisions", [])

    # Use failed_level_ids directly -- this is set by developer_route_node
    # to contain ONLY current-cycle config bugs. Do not union with
    # routing_decisions (which is append-only and includes past cycles).
    failed_ids = set(state.get("failed_level_ids", []))
    levels_to_fix = failed_ids

    new_patches = []
    escalated_ids = []
    total_tokens = 0

    for level in game_config["levels"]:
        lid = level["level_id"]
        if lid not in levels_to_fix:
            continue

        # Find QA report for this level
        qa_for_level = next(
            (lr for lr in qa_report.get("level_reports", []) if lr["level_id"] == lid),
            None,
        )
        if not qa_for_level:
            continue

        patch_result = _fix_level(level, qa_for_level)
        total_tokens += patch_result["tokens"]

        if patch_result.get("escalate"):
            escalated_ids.append(lid)
        else:
            new_patches.append(patch_result["patch"])

    duration = time.time() - t0

    output_summary = (
        f"Debugger processed {len(levels_to_fix)} levels: "
        f"{len(new_patches)} patched, {len(escalated_ids)} escalated to redesign"
    )

    trace = make_trace_entry(
        step=len(state.get("trace_log", [])) + 1,
        agent="Debugger",
        action="fix_config_bugs",
        input_summary=f"Fixing levels {sorted(levels_to_fix)} flagged as config bugs",
        output_summary=output_summary,
        tokens_used=total_tokens,
        duration_seconds=duration,
    )

    # Escalated levels need full redesign --> route to Level Designer next cycle
    current_redesign = state.get("levels_needing_redesign", [])
    new_redesign = list(set(current_redesign + escalated_ids))

    return {
        "debug_patches": new_patches,
        "levels_needing_redesign": new_redesign,
        "trace_log": [trace],
        "total_tokens": state.get("total_tokens", 0) + total_tokens,
    }


def _fix_level(level: Dict[str, Any], qa_report: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt to fix a single level. Returns patch dict or escalation."""
    user_prompt = (
        f"Fix this level based on the QA failure report.\n\n"
        f"Level {level['level_id']} config:\n"
        f"  Grid: {level['grid_width']}x{level['grid_height']}\n"
        f"  Walls: {level['walls']}\n"
        f"  Boxes: {level['boxes']}\n"
        f"  Targets: {level['targets']}\n"
        f"  Player start: {level['player_start']}\n\n"
        f"QA report:\n"
        f"  Solvable: {qa_report['solvable']}\n"
        f"  Issues: {qa_report.get('issues', [])}\n"
        f"  Softlock positions: {qa_report.get('softlock_positions', [])}\n\n"
        f"Make the MINIMAL fix. Return the patched configuration JSON."
    )

    try:
        result = call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=TEMP_DEBUGGER,
            max_tokens=2000,
        )
    except BudgetExceededError:
        return {"escalate": True, "level_id": level["level_id"], "tokens": 0}

    tokens = result["tokens_used"]

    try:
        parsed = parse_json_response(result["content"])

        if parsed.get("escalate"):
            return {"escalate": True, "level_id": level["level_id"], "tokens": tokens}

        # Validate tile change threshold
        total_floor = (level["grid_width"] * level["grid_height"]) - len(level["walls"])
        if parsed.get("tiles_modified", 0) > total_floor * ROUTING_TILE_CHANGE_THRESHOLD:
            return {"escalate": True, "level_id": level["level_id"], "tokens": tokens}

        # Validate the patch through Pydantic before accepting it
        from src.models import DebugPatch
        validated = DebugPatch(**parsed)
        return {"patch": validated.model_dump(), "tokens": tokens}

    except Exception:
        return {"escalate": True, "level_id": level["level_id"], "tokens": tokens}
