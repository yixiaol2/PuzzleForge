"""
PuzzleForge -- Central configuration.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Demo mode: use cached responses instead of live API calls
DEMO_MODE = os.getenv("PUZZLEFORGE_DEMO_MODE", "false").lower() == "true"

# Pipeline constraints (hard rules from agent canvases)
MAX_DEBUG_CYCLES = 3
MAX_TOTAL_TOKENS = 80_000
PIPELINE_TIMEOUT_SECONDS = 300  # 5 minutes wall-clock
DEFAULT_LEVEL_COUNT = 5

# Solver constraints
# The Phase 3 push demo's hardest level needs ~243K states; keep the cap above
# that known-good case while still bounding pathological searches.
SOLVER_MAX_STATES = 500_000
SOLVER_TIMEOUT_SECONDS = 10
MAX_GRID_SIZE = 15

# Agent temperature settings (from agent canvases)
TEMP_GAME_DESIGNER = 0.8    # creative
TEMP_LEVEL_DESIGNER = 0.7   # creative but constrained
TEMP_DEVELOPER = 0.4        # deterministic orchestration
TEMP_DEBUGGER = 0.3         # precise, minimal changes

# Routing thresholds (formalized per Phase 1 feedback)
ROUTING_TILE_CHANGE_THRESHOLD = 0.25  # >25% tiles changed --> design flaw
ROUTING_MIN_CHANGES_FOR_DESIGN_FLAW = 4  # absolute minimum tile changes

# Diversity
SIMILARITY_REJECT_THRESHOLD = 0.5  # reject levels with pairwise similarity > 0.5
