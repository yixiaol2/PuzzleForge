"""
PuzzleForge -- HTML/JS Game Template Engine

Translates a GameConfig JSON into a playable, self-contained HTML/JS file.
The template is a Sokoban-style push-block puzzle with:
    - CSS Grid rendering
    - Keyboard and touch controls
    - Move counter and undo
    - Level progression
    - Win detection
"""

from __future__ import annotations
import json
import os
from typing import Any, Dict


TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def render_game(game_config: Dict[str, Any]) -> str:
    """
    Render a complete, self-contained HTML file from a GameConfig dict.
    The output is a single .html file that can be opened in any browser.
    """
    template_path = os.path.join(TEMPLATE_DIR, "sokoban.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Inject game config as JSON
    config_json = json.dumps(game_config, indent=2, ensure_ascii=False)
    html = template.replace("{{GAME_CONFIG_JSON}}", config_json)
    html = html.replace("{{GAME_TITLE}}", game_config.get("game_title", "PuzzleForge Game"))

    return html


def save_game(game_config: Dict[str, Any], output_path: str) -> str:
    """Render and save the game to a file. Returns the file path."""
    html = render_game(game_config)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
