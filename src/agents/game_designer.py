"""
PuzzleForge -- Game Designer Agent (Design Layer)

Purpose: Define puzzle mechanics, rules, win conditions, visual theme, and progression plan.
Tools:   LLM reasoning only (temperature 0.8). No external tools.
Hard:    Must choose from supported mechanics (push, slide).
Soft:    Increase difficulty through layout complexity (more boxes, larger grids), not new mechanics.
"""

from __future__ import annotations
import json
import time
from typing import Any, Dict

from src.config import TEMP_GAME_DESIGNER
from src.models import GameSpec
from src.utils.llm import call_llm, parse_json_response, BudgetExceededError
from src.utils.trace_logger import make_trace_entry

SYSTEM_PROMPT_TEMPLATE = """You are the Game Designer for PuzzleForge, a multi-agent puzzle game generation system.

Your job: Given a user's game concept, produce a structured game specification. You must make TWO
key creative decisions based on the user's concept:

1. MECHANIC: Choose "push" or "slide" based on the concept.
   - push: Player pushes an object one tile in the movement direction. Good for: warehouses,
     construction, organizing, robots, factories, moving furniture, stacking.
   - slide: Player pushes an object and it SLIDES until it hits a wall or another object. Good for:
     ice puzzles, curling, billiards, space/zero-gravity, hockey, bowling, penguin/arctic themes.

2. THEME: Design a complete visual identity that makes the game FEEL different:
   - Choose a color_scheme: "dark" (default), "earthy" (warm browns/oranges), "icy" (blues/whites),
     "gothic" (purples/dark), "space" (dark blues/greens)
   - Choose emoji/icons for each entity that match the theme narrative
   - Name the entities to match the story (boxes might be "crates", "gems", "ice blocks", etc.)
   - Write a theme-appropriate win message

CONSTRAINTS:
- puzzle_type must be "sokoban"
- Choose EXACTLY ONE mechanic: "push" or "slide" (not both)
- level_count must be exactly {level_count}
- progression_plan should increase complexity through LAYOUT difficulty
- Difficulty targets (the game should be CHALLENGING, not trivial):
  * Level 1: brief tutorial, 1-2 boxes, small but non-trivial (complexity_target: "tutorial")
  * Middle levels: 2-3 boxes, interior obstacles (complexity_target: "intermediate" / "multi-room")
  * Final level(s): 4-5 boxes, complex maze layout (complexity_target: "challenge" / "expert")
- Avoid trivial 1-box levels with direct one-step solutions. The player should feel meaningful difficulty progression.

OUTPUT FORMAT: Return ONLY valid JSON matching this schema:
{{
  "puzzle_type": "sokoban",
  "theme": "<theme name string>",
  "mechanics": [
    {{"name": "<push or slide>", "description": "<string>", "interactions": ["<string>"]}}
  ],
  "win_condition": "<string>",
  "level_count": {level_count},
  "progression_plan": [
    {{"level": 1, "new_mechanics": ["<push or slide>"], "complexity_target": "tutorial"}},
    ...
  ],
  "theme_details": {{
    "color_scheme": "<dark|earthy|icy|gothic|space>",
    "player_emoji": "<single emoji for the player character>",
    "box_emoji": "<single emoji for movable objects>",
    "target_emoji": "<single emoji for target positions>",
    "wall_emoji": "<single emoji for walls, or empty string for solid blocks>",
    "box_name": "<what boxes are called, e.g. crate, gem, ice block>",
    "target_name": "<what targets are called, e.g. marker, altar, fish>",
    "player_name": "<what the player is called, e.g. robot, wizard, penguin>",
    "win_message": "<victory message matching the theme>"
  }}
}}"""


def _failure_response(
    state: Dict[str, Any],
    t0: float,
    action: str,
    reason: str,
    tokens: int = 0,
) -> Dict[str, Any]:
    """Return a transparent terminal failure instead of crashing the graph."""
    trace = make_trace_entry(
        step=len(state.get("trace_log", [])) + 1,
        agent="Game Designer",
        action=action,
        input_summary="Game specification generation failed validation",
        output_summary=reason[:180],
        tokens_used=tokens,
        duration_seconds=time.time() - t0,
    )
    return {
        "pipeline_status": "generation_failed",
        "trace_log": [trace],
        "total_tokens": state.get("total_tokens", 0) + tokens,
    }


def game_designer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph node: Game Designer agent."""
    t0 = time.time()
    user_concept = state["user_concept"]

    from src.config import DEFAULT_LEVEL_COUNT
    n_levels = DEFAULT_LEVEL_COUNT
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(level_count=n_levels)

    user_prompt = (
        f"Design a puzzle game based on this concept:\n\n"
        f"{user_concept}\n\n"
        f"Choose the mechanic (push or slide) that best fits the concept. "
        f"Design a visual theme with appropriate emoji icons and entity names "
        f"that make this feel like a unique game. Plan {n_levels} levels with "
        f"monotonically increasing difficulty through layout complexity."
    )

    try:
        result = call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=TEMP_GAME_DESIGNER,
            max_tokens=2000,
        )
    except BudgetExceededError:
        return {"pipeline_status": "budget_exceeded", "trace_log": [
            make_trace_entry(0, "Game Designer", "budget_exceeded",
                             "Token budget exhausted before generation", "", 0, 0)
        ]}
    except Exception as e:
        return _failure_response(
            state,
            t0,
            "generate_game_spec_failed",
            f"LLM call failed: {e}",
        )

    raw_content = result["content"]
    tokens = result["tokens_used"]

    try:
        parsed = parse_json_response(raw_content)
        game_spec = GameSpec(**parsed)
        spec_dict = game_spec.model_dump()
        mechanic_name = game_spec.mechanics[0].name if game_spec.mechanics else "push"
        output_summary = (
            f"Generated spec: {game_spec.puzzle_type}, theme='{game_spec.theme}', "
            f"mechanic={mechanic_name}, {game_spec.level_count} levels"
        )
    except Exception as e:
        # Retry with error feedback
        try:
            retry_prompt = (
                f"Your previous response was invalid JSON or failed validation:\n{e}\n\n"
                f"Please fix and return ONLY valid JSON for the game specification."
            )
            result2 = call_llm(system_prompt, retry_prompt, TEMP_GAME_DESIGNER, 2000)
            tokens += result2["tokens_used"]
            parsed = parse_json_response(result2["content"])
            game_spec = GameSpec(**parsed)
            spec_dict = game_spec.model_dump()
            mechanic_name = game_spec.mechanics[0].name if game_spec.mechanics else "push"
            output_summary = (
                f"Generated spec (retry): theme='{game_spec.theme}', "
                f"mechanic={mechanic_name}"
            )
        except BudgetExceededError:
            return {"pipeline_status": "budget_exceeded", "trace_log": [
                make_trace_entry(0, "Game Designer", "budget_exceeded",
                                 "Token budget exhausted during retry", "", tokens, 0)
            ]}
        except Exception as retry_error:
            return _failure_response(
                state,
                t0,
                "generate_game_spec_failed",
                f"Retry failed validation: {retry_error}",
                tokens,
            )

    duration = time.time() - t0
    trace = make_trace_entry(
        step=len(state.get("trace_log", [])) + 1,
        agent="Game Designer",
        action="generate_game_spec",
        input_summary=f"User concept: {user_concept[:100]}",
        output_summary=output_summary,
        tokens_used=tokens,
        duration_seconds=duration,
    )

    return {
        "game_spec": spec_dict,
        "trace_log": [trace],
        "total_tokens": state.get("total_tokens", 0) + tokens,
    }
