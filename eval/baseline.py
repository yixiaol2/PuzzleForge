"""
PuzzleForge -- Single-LLM Baseline Evaluation

Generates Sokoban levels using a single GPT-4o call (no multi-agent pipeline,
no solver verification, no debug loop). Then runs the BFS solver to measure
actual solvability. Compares against the multi-agent pipeline results.

Usage:
    python eval/baseline.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.llm import call_llm, parse_json_response
from src.solver.sokoban_solver import SokobanSolver, estimate_difficulty

BASELINE_PROMPT = """Generate a complete Sokoban puzzle game with 5 levels.

Game concept: {concept}

For each level, provide:
- grid_width, grid_height (5x5 to 8x8, increasing across levels)
- walls: list of [x,y] positions (MUST include ALL border tiles)
- boxes: list of [x,y] positions (movable objects)
- targets: list of [x,y] positions (goal positions, same count as boxes)
- player_start: [x,y] (must be on empty floor, not on wall/box/target)

Mechanic: {mechanic}
- push: player pushes a box exactly 1 tile in the movement direction
- slide: player pushes a box and it slides until hitting a wall or another box

CRITICAL RULES:
- Number of boxes MUST equal number of targets in each level
- Player start must NOT be on a wall, box, or target
- All border tiles (x=0, x=max, y=0, y=max) must be walls
- Each level must be solvable
- Increase difficulty: Level 1 = 1 box, Level 5 = 3 boxes

Coordinate system: (0,0) is top-left. X increases right, Y increases down.

Return ONLY a JSON array:
[
  {{
    "level_id": 1,
    "grid_width": 5,
    "grid_height": 5,
    "walls": [[0,0], [1,0], ...],
    "boxes": [[2,3]],
    "targets": [[3,3]],
    "player_start": [1,1]
  }},
  ...
]"""


def run_baseline(concept: str, mechanic: str = "push") -> dict:
    """Run single-LLM baseline for one concept."""
    t0 = time.time()

    prompt = BASELINE_PROMPT.format(concept=concept, mechanic=mechanic)

    result = call_llm(
        system_prompt="You are a Sokoban puzzle level designer. Return only valid JSON.",
        user_prompt=prompt,
        temperature=0.7,
        max_tokens=4000,
    )

    tokens = result["tokens_used"]
    duration = time.time() - t0

    # Parse levels
    try:
        parsed = parse_json_response(result["content"])
        if not isinstance(parsed, list):
            parsed = parsed.get("levels", [parsed])
        levels = parsed
    except Exception as e:
        print(f"  Parse error: {e}")
        return {
            "concept": concept,
            "mechanic": mechanic,
            "levels_produced": 0,
            "levels_solvable": 0,
            "solvability_rate": 0.0,
            "tokens": tokens,
            "duration": duration,
            "level_details": [],
            "parse_error": str(e),
        }

    # Verify each level with BFS solver
    level_details = []
    solvable_count = 0
    valid_count = 0

    for lvl in levels:
        lid = lvl.get("level_id", 0)
        try:
            walls = [tuple(w) for w in lvl["walls"]]
            boxes = [tuple(b) for b in lvl["boxes"]]
            targets = [tuple(t) for t in lvl["targets"]]
            player = tuple(lvl["player_start"])

            # Basic validation
            issues = []
            if len(boxes) != len(targets):
                issues.append(f"box/target mismatch: {len(boxes)} vs {len(targets)}")
            if player in set(walls):
                issues.append("player on wall")
            if player in set(boxes):
                issues.append("player on box")

            valid_count += 1

            solver = SokobanSolver(
                grid_width=lvl["grid_width"],
                grid_height=lvl["grid_height"],
                walls=walls,
                boxes=boxes,
                targets=targets,
                player_start=player,
                max_states=200_000,
                mechanic=mechanic,
            )
            r = solver.solve()

            solvable = r.solvable is True
            if solvable:
                solvable_count += 1

            level_details.append({
                "level_id": lid,
                "grid": f"{lvl['grid_width']}x{lvl['grid_height']}",
                "boxes": len(boxes),
                "solvable": solvable,
                "min_moves": r.min_moves,
                "states_explored": r.states_explored,
                "timeout": r.timeout,
                "issues": issues,
            })
        except Exception as e:
            level_details.append({
                "level_id": lid,
                "solvable": False,
                "error": str(e),
            })

    rate = solvable_count / len(levels) if levels else 0.0

    return {
        "concept": concept,
        "mechanic": mechanic,
        "levels_produced": len(levels),
        "levels_valid": valid_count,
        "levels_solvable": solvable_count,
        "solvability_rate": rate,
        "tokens": tokens,
        "duration": round(duration, 1),
        "level_details": level_details,
    }


def main():
    # Same 4 concepts as the pipeline runs
    concepts = [
        ("A robot organizing cargo pods in a space station", "push"),
        ("A penguin sliding ice blocks across a frozen lake to reach fishing holes", "slide"),
        ("A wizard pushing enchanted gems onto altar pedestals in a gothic dungeon", "push"),
        ("A curling game in zero gravity on a space station", "slide"),
    ]

    print("=" * 70)
    print("PuzzleForge -- Single-LLM Baseline Evaluation")
    print("=" * 70)
    print()

    all_results = []
    total_levels = 0
    total_solvable = 0

    for concept, mechanic in concepts:
        short = concept[:50] + "..." if len(concept) > 50 else concept
        print(f"[Baseline] {short} ({mechanic})")
        result = run_baseline(concept, mechanic)
        all_results.append(result)

        total_levels += result["levels_produced"]
        total_solvable += result["levels_solvable"]

        rate_pct = f"{result['solvability_rate']:.0%}"
        print(f"  Produced: {result['levels_produced']} levels")
        print(f"  Solvable: {result['levels_solvable']}/{result['levels_produced']} ({rate_pct})")
        print(f"  Tokens: {result['tokens']}, Time: {result['duration']}s")
        for ld in result["level_details"]:
            status = "PASS" if ld.get("solvable") else "FAIL"
            extra = ""
            if ld.get("timeout"):
                extra = " (timeout)"
            if ld.get("issues"):
                extra = f" ({'; '.join(ld['issues'])})"
            if ld.get("error"):
                extra = f" (error: {ld['error']})"
            print(f"    L{ld.get('level_id', '?')}: [{status}] moves={ld.get('min_moves', -1)}{extra}")
        print()

    # Summary
    overall_rate = total_solvable / total_levels if total_levels > 0 else 0
    push_levels = sum(r["levels_produced"] for r in all_results if r["mechanic"] == "push")
    push_solvable = sum(r["levels_solvable"] for r in all_results if r["mechanic"] == "push")
    slide_levels = sum(r["levels_produced"] for r in all_results if r["mechanic"] == "slide")
    slide_solvable = sum(r["levels_solvable"] for r in all_results if r["mechanic"] == "slide")
    mean_tokens = sum(r["tokens"] for r in all_results) / len(all_results)

    print("=" * 70)
    print("BASELINE SUMMARY")
    print("=" * 70)
    print(f"  Overall solvability: {total_solvable}/{total_levels} ({overall_rate:.0%})")
    if push_levels:
        print(f"  Push solvability:    {push_solvable}/{push_levels} ({push_solvable/push_levels:.0%})")
    if slide_levels:
        print(f"  Slide solvability:   {slide_solvable}/{slide_levels} ({slide_solvable/slide_levels:.0%})")
    print(f"  Mean tokens/run:     {mean_tokens:.0f}")
    print()
    print("COMPARISON: Multi-Agent Pipeline (v0.3)")
    print(f"  Overall solvability: 14/17 (82%)")
    print(f"  Push solvability:    9/10 (90%)")
    print(f"  Slide solvability:   5/7 (71%)")
    print(f"  Mean tokens/run:     6,448")
    print(f"  + BFS solver verification")
    print(f"  + Up to 3 debug/redesign cycles")
    print(f"  + Specialized agents with tuned temperatures")
    print()

    # Save results
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "baseline_results.json",
    )
    with open(output_path, "w") as f:
        json.dump({
            "baseline_results": all_results,
            "summary": {
                "total_levels": total_levels,
                "total_solvable": total_solvable,
                "overall_rate": round(overall_rate, 3),
                "push_solvable": push_solvable,
                "push_total": push_levels,
                "slide_solvable": slide_solvable,
                "slide_total": slide_levels,
                "mean_tokens": round(mean_tokens),
            },
        }, f, indent=2)
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
