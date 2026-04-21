"""
PuzzleForge -- Level Designer Agent (Design Layer)

Purpose: Create grid layouts, object placement, and solution paths for each level.
Tools:   LLM reasoning only (temperature 0.7). No external tools.
Hard:    Every level must have an intended solution path.
Soft:    Vary grid dimensions across levels; avoid repeating layout patterns.
"""

from __future__ import annotations
import json
import time
from typing import Any, Dict, List

from src.config import TEMP_LEVEL_DESIGNER
from src.models import LevelDefinition
from src.utils.llm import call_llm, parse_json_response, BudgetExceededError
from src.utils.trace_logger import make_trace_entry

SYSTEM_PROMPT = """You are the Level Designer for PuzzleForge, a multi-agent puzzle game generation system.

Your job: Given a game specification (mechanics, progression plan), create concrete grid layouts
for each level with wall placement, box positions, target positions, and player start.

MECHANICS:
- "push": Standard Sokoban. Player pushes a box exactly 1 tile. Boxes stop immediately.
  Design tips: Use corridors and L-shaped paths. Corner deadlocks are the main hazard.
- "slide": Ice/slide puzzle. When pushed, a box SLIDES until it hits a wall or another box.
  Design tips:
  * Place targets ADJACENT TO WALLS so sliding boxes can land on them.
  * Use interior walls as "stoppers" -- without them, boxes slide to the grid edge.
  * Avoid wide open spaces where boxes slide uncontrollably.
  * Multi-step solutions come from using walls/boxes as intermediate blockers.
  * A box in an open corridor with no wall behind it will slide past the target.

CONSTRAINTS:
- Grid sizes: 6x6 minimum, 15x15 maximum. VARY dimensions across levels.
- Number of boxes must equal number of targets in each level.
- Player start must be on an empty floor tile (not a wall, box, or target).
- Walls must form the outer boundary of the grid (all edge tiles are walls).
- Every level must include an intended_solution: a list of moves (U/D/L/R) that the designer
  believes solves the level. The automated solver will verify this independently.
- Do NOT repeat the same wall patterns across levels.

DIFFICULTY TARGETS (the game should be CHALLENGING, not trivial):
- Level 1 (tutorial): 6x6 grid, 2 boxes, minimum 12-move solution
- Level 2: 7x7 grid, 2 boxes, add interior walls/obstacles, minimum 18-move solution
- Level 3: 8x8 grid, 3 boxes, multi-room layout, minimum 25-move solution
- Level 4: 9x9 grid, 3-4 boxes, complex interior maze, minimum 35-move solution
- Level 5+ (challenge): 10x10+ grid, 4-5 boxes, tight corridors, minimum 45-move solution
- Use interior walls to create real puzzles: choke points, rooms, narrow corridors, diversions.
- Place boxes and targets so the player must PLAN order of operations (not just push straight).
- A level with a 5-move solution is too easy -- iterate until you have meaningful depth.

COORDINATE SYSTEM: (0,0) is top-left. X increases rightward, Y increases downward.

OUTPUT FORMAT: Return a JSON array of level definitions:
[
  {
    "level_id": 1,
    "grid_width": 6,
    "grid_height": 6,
    "walls": [[0,0], [1,0], ...],
    "boxes": [[2,3]],
    "targets": [[4,3]],
    "player_start": [1,1],
    "intended_solution": ["R", "R", "D", "R"]
  },
  ...
]

Important: walls MUST include ALL border tiles. Interior walls are optional obstacles."""


def level_designer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph node: Level Designer agent."""
    t0 = time.time()
    game_spec = state["game_spec"]

    # Check if we're redesigning specific levels (feedback loop)
    redesign_ids = state.get("levels_needing_redesign", [])
    existing_levels = state.get("level_definitions") or []

    if redesign_ids and existing_levels:
        return _redesign_levels(state, redesign_ids, t0)

    # Determine the primary mechanic
    mechanics_list = game_spec.get("mechanics", [])
    primary_mechanic = "push"
    if mechanics_list:
        first_mech = mechanics_list[0]
        if isinstance(first_mech, dict):
            primary_mechanic = first_mech.get("name", "push")
        elif isinstance(first_mech, str):
            primary_mechanic = first_mech

    mechanic_guidance = ""
    if primary_mechanic == "slide":
        mechanic_guidance = (
            "\n\nCRITICAL -- This game uses SLIDE mechanics (boxes slide until hitting a wall "
            "or another box). Design accordingly:\n"
            "- Place targets next to walls so sliding boxes stop on them.\n"
            "- Add interior walls as 'stoppers' to control sliding distance.\n"
            "- Avoid large open areas where boxes slide uncontrollably.\n"
            "- Test your intended_solution mentally: each push makes the box slide until blocked.\n"
        )

    # Fresh design: create all levels
    user_prompt = (
        f"Create {game_spec['level_count']} Sokoban puzzle levels based on this game spec:\n\n"
        f"Theme: {game_spec['theme']}\n"
        f"Primary mechanic: {primary_mechanic}\n"
        f"Mechanics: {json.dumps(game_spec['mechanics'])}\n"
        f"Progression plan: {json.dumps(game_spec['progression_plan'])}\n\n"
        f"Design levels with steep, meaningful difficulty progression. The first level is a "
        f"BRIEF tutorial (6x6 grid, 2 boxes, 10+ moves). Every subsequent level should force the "
        f"player to think -- longer paths, more boxes, multi-room layouts, interior obstacles. "
        f"The final level must be a genuine challenge (10x10+ grid, 4-5 boxes, 40+ moves, "
        f"complex interior maze). Do NOT produce trivial 1-box levels solvable in under 10 moves.\n"
        f"Make sure walls include all border tiles and that each level has a valid intended solution."
        f"{mechanic_guidance}"
    )

    try:
        result = call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=TEMP_LEVEL_DESIGNER,
            max_tokens=4000,
        )
    except BudgetExceededError:
        return {"pipeline_status": "budget_exceeded", "trace_log": [
            make_trace_entry(0, "Level Designer", "budget_exceeded",
                             "Token budget exhausted", "", 0, 0)
        ]}

    tokens = result["tokens_used"]
    try:
        parsed = parse_json_response(result["content"])
        if not isinstance(parsed, list):
            parsed = parsed.get("levels", [parsed])
        levels = [LevelDefinition(**lvl).model_dump() for lvl in parsed]
        grids = [str(l["grid_width"]) + "x" + str(l["grid_height"]) for l in levels]
        output_summary = f"Designed {len(levels)} levels, grids: {grids}"
    except Exception as e:
        try:
            retry_prompt = f"Previous output was invalid: {e}. Return ONLY a valid JSON array of level definitions."
            result2 = call_llm(SYSTEM_PROMPT, retry_prompt, TEMP_LEVEL_DESIGNER, 4000)
            tokens += result2["tokens_used"]
            parsed = parse_json_response(result2["content"])
            if not isinstance(parsed, list):
                parsed = parsed.get("levels", [parsed])
            levels = [LevelDefinition(**lvl).model_dump() for lvl in parsed]
            output_summary = f"Designed {len(levels)} levels (retry)"
        except BudgetExceededError:
            return {"pipeline_status": "budget_exceeded", "trace_log": [
                make_trace_entry(0, "Level Designer", "budget_exceeded",
                                 "Token budget exhausted during retry", "", tokens, 0)
            ]}

    duration = time.time() - t0
    trace = make_trace_entry(
        step=len(state.get("trace_log", [])) + 1,
        agent="Level Designer",
        action="design_all_levels",
        input_summary=f"Game spec: {game_spec['theme']}, {game_spec['level_count']} levels",
        output_summary=output_summary,
        tokens_used=tokens,
        duration_seconds=duration,
    )

    return {
        "level_definitions": levels,
        "levels_needing_redesign": [],
        "trace_log": [trace],
        "total_tokens": state.get("total_tokens", 0) + tokens,
    }


def _redesign_levels(state: Dict[str, Any], redesign_ids: List[int], t0: float) -> Dict[str, Any]:
    """Re-design specific levels based on QA feedback."""
    game_spec = state["game_spec"]
    existing_levels = state["level_definitions"]
    qa_report = state.get("qa_report", {})

    # Gather QA feedback for failed levels
    feedback_parts = []
    for lr in qa_report.get("level_reports", []):
        if lr["level_id"] in redesign_ids:
            feedback_parts.append(
                f"Level {lr['level_id']}: solvable={lr['solvable']}, "
                f"issues={lr.get('issues', [])}"
            )

    # Include the original level dimensions so the LLM knows what to change
    original_info = []
    for ld in existing_levels:
        if ld["level_id"] in redesign_ids:
            original_info.append(
                f"  Original Level {ld['level_id']}: {ld['grid_width']}x{ld['grid_height']} grid, "
                f"{len(ld['boxes'])} boxes"
            )

    # Determine the primary mechanic for redesign context
    mechanics_list = game_spec.get("mechanics", [])
    primary_mechanic = "push"
    if mechanics_list:
        first_mech = mechanics_list[0]
        if isinstance(first_mech, dict):
            primary_mechanic = first_mech.get("name", "push")
        elif isinstance(first_mech, str):
            primary_mechanic = first_mech

    slide_note = ""
    if primary_mechanic == "slide":
        slide_note = (
            f"NOTE: This game uses SLIDE mechanics. Place targets next to walls "
            f"and use interior walls as stoppers.\n"
        )

    user_prompt = (
        f"The following levels failed QA and need complete redesign:\n"
        f"Levels to redesign: {redesign_ids}\n\n"
        f"QA feedback:\n" + "\n".join(feedback_parts) + "\n\n"
        f"Original level info:\n" + "\n".join(original_info) + "\n\n"
        f"Game spec theme: {game_spec['theme']}\n"
        f"Primary mechanic: {primary_mechanic}\n"
        f"{slide_note}"
        f"Progression plan: {json.dumps(game_spec['progression_plan'])}\n\n"
        f"IMPORTANT RULES FOR REDESIGN:\n"
        f"- Keep the same level_id numbers.\n"
        f"- If the solver timed out, the level was too complex. Use a SMALLER grid "
        f"(max 8x8) and ADD interior walls to constrain the search space.\n"
        f"- If unsolvable, ensure boxes are NOT placed in corners or against walls "
        f"where they can get stuck.\n"
        f"- Use different wall layouts and grid sizes from the originals.\n"
        f"- Return a JSON array of level definitions, one per redesigned level.\n"
        f"- walls MUST include ALL border tiles."
    )

    try:
        result = call_llm(SYSTEM_PROMPT, user_prompt, TEMP_LEVEL_DESIGNER, 3000)
    except BudgetExceededError:
        return {"pipeline_status": "budget_exceeded", "trace_log": [
            make_trace_entry(0, "Level Designer", "budget_exceeded",
                             "Token budget exhausted during redesign", "", 0, 0)
        ]}
    tokens = result["tokens_used"]

    try:
        parsed = parse_json_response(result["content"])
        if not isinstance(parsed, list):
            parsed = parsed.get("levels", [parsed]) if isinstance(parsed, dict) else [parsed]
        new_levels = [LevelDefinition(**lvl).model_dump() for lvl in parsed]
    except Exception as e:
        # Retry with error feedback instead of silently failing
        try:
            retry_prompt = (
                f"Your previous redesign output was invalid: {e}\n\n"
                f"Return ONLY a valid JSON array of level definitions for levels {redesign_ids}.\n"
                f"Each level must have: level_id, grid_width, grid_height, walls (including ALL "
                f"border tiles), boxes, targets (same count as boxes), player_start (on empty tile), "
                f"intended_solution (list of U/D/L/R moves)."
            )
            result2 = call_llm(SYSTEM_PROMPT, retry_prompt, TEMP_LEVEL_DESIGNER, 3000)
            tokens += result2["tokens_used"]
            parsed = parse_json_response(result2["content"])
            if not isinstance(parsed, list):
                parsed = parsed.get("levels", [parsed]) if isinstance(parsed, dict) else [parsed]
            new_levels = [LevelDefinition(**lvl).model_dump() for lvl in parsed]
        except BudgetExceededError:
            return {"pipeline_status": "budget_exceeded", "trace_log": [
                make_trace_entry(0, "Level Designer", "budget_exceeded",
                                 "Token budget exhausted during redesign retry", "", tokens, 0)
            ]}
        except Exception:
            new_levels = []

    # Merge: replace redesigned levels, keep others
    redesigned_ids = {l["level_id"] for l in new_levels}
    merged = [l for l in existing_levels if l["level_id"] not in redesigned_ids] + new_levels
    merged.sort(key=lambda l: l["level_id"])

    duration = time.time() - t0
    trace = make_trace_entry(
        step=len(state.get("trace_log", [])) + 1,
        agent="Level Designer",
        action="redesign_levels",
        input_summary=f"Redesigning levels {redesign_ids} based on QA feedback",
        output_summary=f"Redesigned {len(new_levels)} levels",
        tokens_used=tokens,
        duration_seconds=duration,
    )

    return {
        "level_definitions": merged,
        "levels_needing_redesign": [],
        "trace_log": [trace],
        "total_tokens": state.get("total_tokens", 0) + tokens,
    }
