"""
PuzzleForge -- Pydantic data models for all inter-agent communication.

Every agent reads and writes structured JSON validated by these schemas.
Pydantic catches malformed LLM output before it reaches the next agent.
"""

from __future__ import annotations
from typing import List, Literal, Optional, Tuple
from pydantic import BaseModel, Field, model_validator

SUPPORTED_MECHANICS = ("push", "slide")


# -- Game Designer output ----------------------------------------------

class ThemeDetails(BaseModel):
    """Visual theme details for rendering the game."""
    color_scheme: str = Field(default="dark", description="One of: dark, earthy, icy, gothic, space")
    player_emoji: str = Field(default="P", description="Emoji/icon for the player, e.g. a robot or wizard")
    box_emoji: str = Field(default="B", description="Emoji/icon for movable objects")
    target_emoji: str = Field(default="X", description="Emoji/icon for target positions")
    wall_emoji: str = Field(default="", description="Emoji/icon for walls (empty = solid block)")
    box_name: str = Field(default="box", description="What boxes are called in this theme")
    target_name: str = Field(default="target", description="What targets are called in this theme")
    player_name: str = Field(default="player", description="What the player is called in this theme")
    win_message: str = Field(default="Level complete!", description="Message shown on level completion")

class MechanicSpec(BaseModel):
    name: Literal["push", "slide"] = Field(
        description="Must be one of: push, slide"
    )
    description: str = Field(description="One-sentence explanation of how this mechanic works")
    interactions: List[str] = Field(
        default_factory=list,
        description="How this mechanic interacts with other mechanics",
    )

class ProgressionStep(BaseModel):
    level: int = Field(description="1-indexed level number")
    new_mechanics: List[str] = Field(description="Mechanics introduced or combined at this level")
    complexity_target: str = Field(description="e.g. 'tutorial', 'easy', 'medium', 'hard', 'expert'")

class GameSpec(BaseModel):
    """Output of the Game Designer agent."""
    puzzle_type: str = Field(description="e.g. 'sokoban'")
    theme: str = Field(description="Visual/narrative theme, e.g. 'warehouse robot'")
    mechanics: List[MechanicSpec]
    win_condition: str = Field(description="What the player must achieve to complete a level")
    level_count: int = Field(default=5, ge=3, le=8)
    progression_plan: List[ProgressionStep]
    theme_details: Optional[ThemeDetails] = Field(default=None, description="Visual theme configuration")


# -- Level Designer output ---------------------------------------------

class Entity(BaseModel):
    entity_type: str = Field(description="One of: 'box', 'target', 'wall'")
    x: int
    y: int

class LevelDefinition(BaseModel):
    """Output of the Level Designer agent (one per level)."""
    level_id: int
    grid_width: int = Field(ge=4, le=15)
    grid_height: int = Field(ge=4, le=15)
    walls: List[Tuple[int, int]] = Field(description="List of (x,y) wall positions")
    boxes: List[Tuple[int, int]] = Field(description="List of (x,y) box positions")
    targets: List[Tuple[int, int]] = Field(description="List of (x,y) target positions")
    player_start: Tuple[int, int]
    intended_solution: List[str] = Field(
        description="Designer's intended move sequence: U/D/L/R",
    )

    @model_validator(mode="after")
    def _cross_field_checks(self) -> "LevelDefinition":
        if len(self.boxes) != len(self.targets):
            raise ValueError(
                f"Box count ({len(self.boxes)}) must equal target count "
                f"({len(self.targets)})"
            )
        wall_set = set(self.walls)
        if self.player_start in wall_set:
            raise ValueError(
                f"Player start {self.player_start} is on a wall tile"
            )
        if self.player_start in set(self.boxes):
            raise ValueError(
                f"Player start {self.player_start} overlaps with a box"
            )
        if self.player_start in set(self.targets):
            raise ValueError(
                f"Player start {self.player_start} is on a target tile "
                f"(must be an empty floor tile)"
            )
        return self


# -- QA Tester output --------------------------------------------------

class LevelQAReport(BaseModel):
    level_id: int
    solvable: Optional[bool] = Field(description="True/False/None(timeout)")
    min_moves: int = Field(default=-1, description="Minimum moves from solver; -1 if unsolvable")
    solver_solution: List[str] = Field(default_factory=list)
    has_softlocks: bool = Field(default=False)
    softlock_positions: List[Tuple[int, int]] = Field(default_factory=list)
    difficulty_rating: int = Field(
        default=0, ge=0, le=5,
        description="0=untested, 1=trivial, 2=easy, 3=medium, 4=hard, 5=expert",
    )
    issues: List[str] = Field(default_factory=list, description="Specific actionable issues")
    states_explored: int = Field(default=0)

class QAReport(BaseModel):
    """Full QA report across all levels."""
    level_reports: List[LevelQAReport]
    difficulty_curve_monotonic: bool = Field(default=False)
    summary: str = Field(default="")


# -- Routing decision --------------------------------------------------

class RoutingDecision(BaseModel):
    """Developer's classification of a QA failure."""
    level_id: int
    failure_type: str = Field(description="'config_bug' or 'design_flaw'")
    reason: str
    criteria_matched: str = Field(
        description="Which formal routing criterion triggered this classification",
    )
    routed_to: str = Field(description="'debugger' or 'level_designer'")


# -- Debugger output ---------------------------------------------------

class TileChange(BaseModel):
    x: int
    y: int
    old_type: str
    new_type: str

class DebugPatch(BaseModel):
    """Output of the Debugger agent."""
    level_id: int
    change_description: str
    rationale: str
    tiles_modified: int
    changes: List[TileChange]
    patched_walls: List[Tuple[int, int]]
    patched_boxes: List[Tuple[int, int]]
    patched_targets: List[Tuple[int, int]]
    patched_player_start: Tuple[int, int]


# -- Game config (Developer translates design --> this) ------------------

class LevelConfig(BaseModel):
    level_id: int
    title: str
    grid_width: int
    grid_height: int
    walls: List[Tuple[int, int]]
    boxes: List[Tuple[int, int]]
    targets: List[Tuple[int, int]]
    player_start: Tuple[int, int]
    mechanics_active: List[str]
    min_moves: Optional[int] = Field(default=None, description="BFS-computed shortest solution length; used for move limit")

class GameConfig(BaseModel):
    """Complete game configuration for the template engine."""
    game_title: str
    puzzle_type: str
    theme: str
    win_condition: str
    levels: List[LevelConfig]
    primary_mechanic: str = Field(default="push", description="Primary mechanic: push or slide")
    theme_details: Optional[ThemeDetails] = Field(default=None)


# -- Trace entry -------------------------------------------------------

class TraceEntry(BaseModel):
    """Single entry in the interaction trace log."""
    step: int
    agent: str
    action: str
    input_summary: str
    output_summary: str
    tokens_used: int = Field(default=0)
    duration_seconds: float = Field(default=0.0)
    timestamp: str = Field(default="")
