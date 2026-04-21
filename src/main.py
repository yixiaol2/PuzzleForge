"""
PuzzleForge - CLI entry point.

Usage:
    python -m src.main "A push-block puzzle about a robot in a warehouse"
    python -m src.main --demo      # Run with cached demo data (no API key needed)
"""

from __future__ import annotations
import argparse
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="PuzzleForge - Agentic Puzzle Game Generation")
    parser.add_argument("concept", nargs="?", default=None, help="Game concept description")
    parser.add_argument("--demo", action="store_true", help="Run with demo data (no API key)")
    parser.add_argument("--output-dir", default="outputs", help="Output directory")
    args = parser.parse_args()

    if args.demo:
        os.environ["PUZZLEFORGE_DEMO_MODE"] = "true"
        run_demo(args.output_dir)
        return

    if not args.concept:
        print("Usage: python -m src.main \"Your game concept here\"")
        print("       python -m src.main --demo")
        sys.exit(1)

    # Live pipeline run
    from src.orchestrator.graph import run_pipeline
    from src.engine.template_engine import save_game
    from src.utils.trace_logger import format_trace_log

    print(f"[PuzzleForge] - Starting pipeline...")
    print(f"   Concept: {args.concept}\n")

    final_state = run_pipeline(args.concept)

    # Save outputs
    os.makedirs(args.output_dir, exist_ok=True)

    if final_state.get("final_game_html"):
        html_path = os.path.join(args.output_dir, "game.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(final_state["final_game_html"])
        print(f"[OK] Game saved: {html_path}")

    if final_state.get("final_design_doc"):
        doc_path = os.path.join(args.output_dir, "design_doc.json")
        with open(doc_path, "w", encoding="utf-8") as f:
            json.dump(final_state["final_design_doc"], f, indent=2, default=str)
        print(f"[OK] Design doc saved: {doc_path}")

    if final_state.get("trace_log"):
        trace_path = os.path.join(args.output_dir, "trace.json")
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(final_state["trace_log"], f, indent=2)
        print(f"[OK] Trace saved: {trace_path}")
        print(f"\n{'='*60}")
        print(format_trace_log(final_state["trace_log"]))

    print(f"\n{'='*60}")
    print(f"Pipeline status: {final_state.get('pipeline_status', 'unknown')}")
    print(f"Total tokens: {final_state.get('total_tokens', 0)}")
    print(f"Debug cycles: {final_state.get('debug_cycle', 0)}")


def run_demo(output_dir: str):
    """Run with pre-built demo data to demonstrate the pipeline output."""
    from src.engine.template_engine import render_game

    print("[PuzzleForge] - Demo Mode (no API key required)\n")

    # Load the pre-built sample game config
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "outputs", "sample_traces", "sample_game_config.json",
    )

    if os.path.exists(sample_path):
        with open(sample_path, "r", encoding="utf-8") as f:
            game_config = json.load(f)
    else:
        # Fallback: use embedded minimal demo config
        game_config = _embedded_demo_config()

    html = render_game(game_config)
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "demo_game.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] Demo game saved: {out_path}")
    print("   Open in your browser to play!")


def _embedded_demo_config(variant: str = "push") -> dict:
    """Embedded demo config fallback -- loads harder sample JSON if present, otherwise
    returns a minimal 3-level config. The canonical hard demos live in
    outputs/sample_traces/sample_game_config.json and sample_slide_config.json."""
    sample_file = "sample_slide_config.json" if variant == "slide" else "sample_game_config.json"
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "outputs", "sample_traces", sample_file,
    )
    if os.path.exists(sample_path):
        with open(sample_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Minimal fallback (solver-verified, harder than pre-Phase 3 defaults)
    def border(w, h):
        return ([[x,0] for x in range(w)] + [[x,h-1] for x in range(w)]
              + [[0,y] for y in range(1,h-1)] + [[w-1,y] for y in range(1,h-1)])

    if variant == "slide":
        return {
            "game_title": "PuzzleForge: Arctic Expedition",
            "puzzle_type": "sokoban", "theme": "arctic expedition",
            "win_condition": "Slide all ice blocks onto the fishing holes",
            "primary_mechanic": "slide",
            "theme_details": {
                "color_scheme": "icy",
                "player_emoji": "\U0001F427", "box_emoji": "\U0001F9CA",
                "target_emoji": "\U0001F41F", "wall_emoji": "",
                "box_name": "ice block", "target_name": "fishing hole",
                "player_name": "penguin",
                "win_message": "The penguin found all the fish!",
            },
            "levels": [
                {"level_id": 1, "title": "Level 1 - First Tracks",
                 "grid_width": 6, "grid_height": 6,
                 "walls": border(6,6) + [[3,2]],
                 "boxes": [[2,2],[3,3]], "targets": [[4,1],[1,4]],
                 "player_start": [1,1], "mechanics_active": ["slide"], "min_moves": 9},
                {"level_id": 2, "title": "Level 2 - Stoppers",
                 "grid_width": 7, "grid_height": 7,
                 "walls": border(7,7) + [[3,3],[3,4]],
                 "boxes": [[2,2],[4,2]], "targets": [[5,1],[1,5]],
                 "player_start": [3,5], "mechanics_active": ["slide"], "min_moves": 13},
                {"level_id": 3, "title": "Level 3 - Frozen Lake",
                 "grid_width": 8, "grid_height": 8,
                 "walls": border(8,8) + [[4,3],[4,4],[3,5]],
                 "boxes": [[2,2],[5,2]], "targets": [[6,1],[1,6]],
                 "player_start": [4,6], "mechanics_active": ["slide"], "min_moves": 15},
            ],
        }
    return {
        "game_title": "PuzzleForge: Space Station",
        "puzzle_type": "sokoban", "theme": "space station",
        "win_condition": "Push all cargo pods onto the docking bays",
        "primary_mechanic": "push",
        "theme_details": {
            "color_scheme": "space",
            "player_emoji": "\U0001F916", "box_emoji": "\U0001F4E6",
            "target_emoji": "\U0001F537", "wall_emoji": "",
            "box_name": "cargo pod", "target_name": "docking bay",
            "player_name": "robot",
            "win_message": "Cargo secured! Station operational!",
        },
        "levels": [
            {"level_id": 1, "title": "Level 1 - Gateway",
             "grid_width": 6, "grid_height": 6,
             "walls": border(6,6) + [[3,2]],
             "boxes": [[2,2],[2,3]], "targets": [[4,3],[4,4]],
             "player_start": [1,1], "mechanics_active": ["push"], "min_moves": 15},
            {"level_id": 2, "title": "Level 2 - Service Corridor",
             "grid_width": 7, "grid_height": 7,
             "walls": border(7,7) + [[4,2],[4,3]],
             "boxes": [[2,2],[3,5]], "targets": [[5,5],[5,1]],
             "player_start": [1,1], "mechanics_active": ["push"], "min_moves": 15},
            {"level_id": 3, "title": "Level 3 - Docking Array",
             "grid_width": 8, "grid_height": 8,
             "walls": border(8,8) + [[3,3],[4,4]],
             "boxes": [[2,2],[5,2],[2,5]], "targets": [[6,6],[1,6],[6,1]],
             "player_start": [1,1], "mechanics_active": ["push"], "min_moves": 24},
        ],
    }


if __name__ == "__main__":
    main()
