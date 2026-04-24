"""
PuzzleForge -- Formal Routing Criteria (Developer's classification logic)

Addresses Phase 1 feedback item #3:
    "Formalize the routing classification criteria for the Developer."

The Developer classifies each QA failure as either a 'config_bug' (--> Debugger)
or a 'design_flaw' (--> Level Designer) using these EXPLICIT, DETERMINISTIC criteria
rather than relying on LLM judgment.

This module encodes the rules as a pure function -- no LLM involved in routing.
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple

from src.config import SOLVER_MAX_STATES


# -- Classification criteria -------------------------------------------

CRITERIA = {
    "C1_PLACEMENT_FIX": {
        "id": "C1",
        "description": "Unsolvable due to box/target placement that can be corrected "
                       "by moving <= N entities (N = 25% of non-wall tiles).",
        "routes_to": "debugger",
    },
    "C2_BLOCKED_PATH": {
        "id": "C2",
        "description": "Unsolvable because a single wall blocks the only viable path. "
                       "Removing or moving 1-2 walls would create a solution.",
        "routes_to": "debugger",
    },
    "C3_PLAYER_START_INVALID": {
        "id": "C3",
        "description": "Player starts on a wall or box tile. Fix: move player start.",
        "routes_to": "debugger",
    },
    "C4_TRIVIAL_BOX_DEADLOCK": {
        "id": "C4",
        "description": "A box starts in a corner deadlock (not on a target). "
                       "Fix: reposition the box to a non-dead square.",
        "routes_to": "debugger",
    },
    "C5_COUNT_MISMATCH": {
        "id": "C5",
        "description": "Number of boxes != number of targets. Fix: add/remove entity.",
        "routes_to": "debugger",
    },
    "D1_MECHANIC_INCOMPATIBLE": {
        "id": "D1",
        "description": "The level's mechanic combination produces no valid solution "
                       "regardless of entity placement. Requires redesign.",
        "routes_to": "level_designer",
    },
    "D2_GRID_TOO_SMALL": {
        "id": "D2",
        "description": "Grid dimensions are too small to accommodate the required "
                       "mechanics and entity count. Requires new layout.",
        "routes_to": "level_designer",
    },
    "D3_EXCESSIVE_CHANGES_NEEDED": {
        "id": "D3",
        "description": "Fixing requires changing > 25% of non-wall tiles, which "
                       "effectively means redesigning the level.",
        "routes_to": "level_designer",
    },
    "D4_SOLVER_TIMEOUT": {
        "id": "D4",
        "description": "Solver timed out, suggesting the level is too complex "
                       "for the grid size. Needs simpler redesign.",
        "routes_to": "level_designer",
    },
    "D5_DIVERSITY_VIOLATION": {
        "id": "D5",
        "description": "Level layout is too similar to another level "
                       "(pairwise Jaccard similarity > 0.5). Requires redesign.",
        "routes_to": "level_designer",
    },
}


def classify_failure(
    level: Dict[str, Any],
    qa_report: Dict[str, Any],
) -> Tuple[str, str, str]:
    """
    Classify a QA failure using deterministic rules.

    Returns: (failure_type, criteria_id, reason)
        failure_type: 'config_bug' or 'design_flaw'
        criteria_id:  which criterion matched (e.g., 'C1', 'D2')
        reason:       human-readable explanation
    """
    issues = qa_report.get("issues", [])
    solvable = qa_report.get("solvable", False)
    states_explored = qa_report.get("states_explored", 0)
    has_softlocks = qa_report.get("has_softlocks", False)
    softlock_positions = qa_report.get("softlock_positions", [])

    grid_w = level.get("grid_width", 0)
    grid_h = level.get("grid_height", 0)
    walls = level.get("walls", [])
    boxes = level.get("boxes", [])
    targets = level.get("targets", [])
    non_wall_tiles = (grid_w * grid_h) - len(walls)

    # -- Priority-ordered checks ---------------------------------------

    # D5: Diversity violation (solvable but too similar to another level).
    # This must be checked BEFORE solvability criteria because the level
    # may be solvable yet still need redesign for diversity reasons.
    has_diversity_issue = any("diversity" in iss.lower() for iss in issues)
    if has_diversity_issue:
        return ("design_flaw", "D5",
                "Level is too similar to another level (pairwise similarity > 0.5). "
                "Requires redesign with a different layout, not a config patch.")

    # C5: Count mismatch
    if len(boxes) != len(targets):
        return ("config_bug", "C5",
                f"Box count ({len(boxes)}) != target count ({len(targets)})")

    # C3: Player on wall/box
    player = tuple(level.get("player_start", [0, 0]))
    wall_set = set(map(tuple, walls))
    box_set = set(map(tuple, boxes))
    if player in wall_set or player in box_set:
        return ("config_bug", "C3",
                f"Player starts on {'wall' if player in wall_set else 'box'} at {player}")

    # D4: Solver timeout (must check before placement analysis)
    if qa_report.get("solvable") is None or states_explored >= SOLVER_MAX_STATES:
        return ("design_flaw", "D4",
                f"Solver explored {states_explored} states without finding solution -- "
                f"level is too complex for {grid_w}x{grid_h} grid")

    # D2: Grid too small for entity count
    min_needed_floor = len(boxes) * 3 + 2  # each box needs path space
    if non_wall_tiles < min_needed_floor:
        return ("design_flaw", "D2",
                f"Grid has {non_wall_tiles} floor tiles but needs ~{min_needed_floor} "
                f"for {len(boxes)} boxes")

    # C4: Box starts in corner deadlock
    if has_softlocks and softlock_positions:
        dead_set = set(map(tuple, softlock_positions))
        boxes_on_dead = [b for b in boxes if tuple(b) in dead_set]
        if boxes_on_dead and len(boxes_on_dead) <= len(boxes) // 2 + 1:
            return ("config_bug", "C4",
                    f"Box(es) at {boxes_on_dead} start in dead squares -- reposition them")

    # D1: Mechanic combination incompatible -- the solver supports push and slide.
    # If the level claims mechanics beyond these supported types, the mechanic
    # combination itself may be the problem, not placement.
    mechanics = level.get("mechanics_active", ["push"])
    supported = {"push", "slide"}
    if not solvable and any(m not in supported for m in mechanics):
        return ("design_flaw", "D1",
                f"Level uses unsupported mechanics {mechanics}. "
                f"Only push and slide are supported -- requires redesign")

    # C2: Wall blockage -- measured by: unsolvable, few issues (<=2), and sufficient
    # floor space (>=1.5x the minimum needed), indicating the geometry is adequate
    # but a specific wall blocks the path.
    if not solvable and len(issues) <= 2 and non_wall_tiles >= min_needed_floor * 1.5:
        return ("config_bug", "C2",
                f"Unsolvable despite adequate floor space ({non_wall_tiles} tiles, "
                f"need {min_needed_floor}). Likely a wall placement blocking the solution path")

    # D3: Excessive changes needed -- measured by: unsolvable with >2 distinct issues
    # reported by QA, indicating structural problems spanning multiple level aspects.
    if not solvable and len(issues) > 2:
        return ("design_flaw", "D3",
                f"{len(issues)} distinct issues reported -- structural problems "
                f"requiring redesign (issues: {'; '.join(issues[:3])})")

    # C1: Default for unsolvable levels with no specific structural problem detected.
    # Attempt placement fix before escalating.
    if not solvable:
        return ("config_bug", "C1",
                "Unsolvable with no specific structural issue detected -- "
                "attempting placement fix before escalating")

    return ("config_bug", "C1", "Minor issue -- attempting minimal fix")


def classify_all_failures(
    game_config: Dict[str, Any],
    qa_report: Dict[str, Any],
    failed_ids: List[int],
) -> List[Dict[str, Any]]:
    """
    Classify all failed levels and produce routing decisions.

    Returns a list of RoutingDecision dicts ready for PipelineState.
    """
    decisions = []
    levels_by_id = {lvl["level_id"]: lvl for lvl in game_config["levels"]}

    for lid in failed_ids:
        level = levels_by_id.get(lid)
        lr = next(
            (r for r in qa_report.get("level_reports", []) if r["level_id"] == lid),
            None,
        )
        if not level or not lr:
            continue

        failure_type, criteria_id, reason = classify_failure(level, lr)

        decisions.append({
            "level_id": lid,
            "failure_type": failure_type,
            "reason": reason,
            "criteria_matched": criteria_id,
            "routed_to": "debugger" if failure_type == "config_bug" else "level_designer",
        })

    return decisions
