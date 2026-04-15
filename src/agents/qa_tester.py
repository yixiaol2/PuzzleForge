"""
PuzzleForge -- QA Tester Agent (Implementation Layer)

Purpose: Run automated solver on every level. Report solvability, min moves,
         softlocks, difficulty rating, and difficulty curve monotonicity.
Tools:   BFS/DFS solver (automated), softlock detector, difficulty analyzer.
Hard:    Solvability determination MUST come from the automated solver, NEVER from LLM reasoning.
Soft:    Report difficulty concerns even for solvable levels.
"""

from __future__ import annotations
import time
from typing import Any, Dict, List

from src.solver.sokoban_solver import SokobanSolver, estimate_difficulty, level_similarity
from src.config import SOLVER_MAX_STATES
from src.utils.trace_logger import make_trace_entry


def qa_tester_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: QA Tester agent.

    Runs the BFS solver on every level in game_config.
    Produces a QAReport with per-level results and overall assessment.
    No LLM calls -- this agent uses only deterministic tools.
    """
    t0 = time.time()
    game_config = state["game_config"]
    levels = game_config["levels"]
    mechanic = game_config.get("primary_mechanic", "push")

    level_reports = []
    failed_ids = []

    for lvl in levels:
        report = _test_level(lvl, mechanic=mechanic)
        level_reports.append(report)
        if not report["solvable"]:
            failed_ids.append(report["level_id"])

    # Check difficulty curve monotonicity
    ratings = [r["difficulty_rating"] for r in level_reports if r["difficulty_rating"] > 0]
    monotonic = all(ratings[i] <= ratings[i + 1] for i in range(len(ratings) - 1)) if len(ratings) > 1 else True

    # Check level diversity -- flag the SECOND level in each too-similar pair
    diversity_issues = _check_diversity(levels)
    diversity_failed_ids: set = set()
    for issue in diversity_issues:
        # Each issue names two level IDs; mark the later one for redesign
        parts = issue.split("Levels ")
        if len(parts) > 1:
            try:
                ids = parts[1].split(" and ")
                later_id = int(ids[1].split(" ")[0])
                diversity_failed_ids.add(later_id)
            except (IndexError, ValueError):
                pass
    # Inject diversity failures into the per-level reports so the router sees them
    for lr in level_reports:
        if lr["level_id"] in diversity_failed_ids:
            lr["issues"].append("Layout too similar to another level (diversity violation)")
            if lr["level_id"] not in failed_ids:
                failed_ids.append(lr["level_id"])

    # Build summary
    solvable_count = sum(1 for r in level_reports if r["solvable"])
    total = len(level_reports)
    summary = (
        f"{solvable_count}/{total} levels solvable. "
        f"Difficulty curve monotonic: {monotonic}. "
        f"Diversity issues: {len(diversity_issues)}."
    )

    qa_report = {
        "level_reports": level_reports,
        "difficulty_curve_monotonic": monotonic,
        "diversity_issues": diversity_issues,
        "summary": summary,
    }

    duration = time.time() - t0
    trace = make_trace_entry(
        step=len(state.get("trace_log", [])) + 1,
        agent="QA Tester",
        action="test_all_levels",
        input_summary=f"Testing {total} levels from game config",
        output_summary=summary,
        tokens_used=0,
        duration_seconds=duration,
    )

    return {
        "qa_report": qa_report,
        "failed_level_ids": failed_ids,
        "trace_log": [trace],
    }


def _test_level(level: Dict[str, Any], mechanic: str = "push") -> Dict[str, Any]:
    """Run solver on a single level and produce a LevelQAReport dict."""
    walls = [tuple(w) for w in level["walls"]]
    boxes = [tuple(b) for b in level["boxes"]]
    targets = [tuple(t) for t in level["targets"]]
    player = tuple(level["player_start"])

    # Validate basic constraints
    issues = []
    if len(boxes) != len(targets):
        issues.append(f"Box count ({len(boxes)}) != target count ({len(targets)})")
    if player in set(walls):
        issues.append("Player starts on a wall tile")
    if player in set(boxes):
        issues.append("Player starts on a box tile")

    # Run solver with the game's mechanic type
    solver = SokobanSolver(
        grid_width=level["grid_width"],
        grid_height=level["grid_height"],
        walls=walls,
        boxes=boxes,
        targets=targets,
        player_start=player,
        max_states=SOLVER_MAX_STATES,
        mechanic=mechanic,
    )

    result = solver.solve()

    # Detect softlocks
    softlock_positions = solver.detect_softlocks()
    # Check if any box starts on a dead square
    boxes_on_dead = [b for b in boxes if b in set(softlock_positions)]
    if boxes_on_dead:
        issues.append(f"Boxes start on dead squares (can never reach target): {boxes_on_dead}")

    # Difficulty estimation
    grid_area = level["grid_width"] * level["grid_height"]
    difficulty = estimate_difficulty(result.min_moves, result.states_explored, grid_area)

    if result.solvable and result.min_moves <= 3:
        issues.append("Level is trivially easy (3 or fewer moves)")
    if result.timeout:
        issues.append("Solver timed out -- level may be too complex or grid too large")

    return {
        "level_id": level["level_id"],
        "solvable": result.solvable if result.solvable is not None else False,
        "min_moves": result.min_moves,
        "solver_solution": result.solution[:50],  # Cap for readability
        "has_softlocks": len(boxes_on_dead) > 0,
        "softlock_positions": softlock_positions[:10],
        "difficulty_rating": difficulty,
        "issues": issues,
        "states_explored": result.states_explored,
    }


def _check_diversity(levels: List[Dict[str, Any]]) -> List[str]:
    """Check pairwise similarity between levels and flag duplicates."""
    issues = []
    for i in range(len(levels)):
        for j in range(i + 1, len(levels)):
            sim = level_similarity(levels[i], levels[j])
            if sim > 0.5:
                issues.append(
                    f"Levels {levels[i]['level_id']} and {levels[j]['level_id']} "
                    f"have high similarity ({sim:.2f})"
                )
    return issues
