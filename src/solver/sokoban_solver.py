"""
PuzzleForge -- BFS Puzzle Solver with deadlock detection.

Supports two mechanics:
  - push: standard Sokoban (box moves 1 tile when pushed)
  - slide: ice-puzzle variant (box slides until hitting a wall or another box)

This is the ground-truth verification tool used by the QA Tester agent.
Solvability determination comes ONLY from this solver, never from LLM reasoning.
"""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional, Set, Tuple

MOVES = {
    "U": (0, -1),
    "D": (0, 1),
    "L": (-1, 0),
    "R": (1, 0),
}


@dataclass
class SolverResult:
    solvable: Optional[bool]     # True / False / None (timeout)
    min_moves: int               # -1 if unsolvable or timeout
    solution: List[str]          # Move sequence (U/D/L/R)
    states_explored: int
    timeout: bool = False
    deadlock_positions: List[Tuple[int, int]] = field(default_factory=list)


class SokobanSolver:
    """
    BFS-based solver for Sokoban-style push-block puzzles.

    Supports two mechanics:
        - "push": box moves exactly 1 tile (standard Sokoban)
        - "slide": box slides until hitting a wall or another box (ice puzzle)

    Features:
        - Breadth-first search guarantees minimum-move solution.
        - Corner deadlock detection prunes unsolvable branches early.
        - Wall-line deadlock detection for boxes trapped along walls.
        - Configurable state limit to prevent runaway computation.
    """

    def __init__(
        self,
        grid_width: int,
        grid_height: int,
        walls: List[Tuple[int, int]],
        boxes: List[Tuple[int, int]],
        targets: List[Tuple[int, int]],
        player_start: Tuple[int, int],
        max_states: int = 200_000,
        mechanic: str = "push",
    ):
        self.width = grid_width
        self.height = grid_height
        self.walls: FrozenSet[Tuple[int, int]] = frozenset(walls)
        self.initial_boxes: FrozenSet[Tuple[int, int]] = frozenset(boxes)
        self.targets: FrozenSet[Tuple[int, int]] = frozenset(targets)
        self.player_start = tuple(player_start)
        self.max_states = max_states
        self.mechanic = mechanic

        # Pre-compute simple deadlock squares (corners not on targets)
        # For slide mechanic, corner deadlock is less applicable since boxes
        # slide past corners, so we skip dead-square pruning.
        if self.mechanic == "push":
            self._dead_squares = self._compute_dead_squares()
        else:
            self._dead_squares = frozenset()

    # -- Public API ----------------------------------------------------

    def solve(self) -> SolverResult:
        """Run BFS. Returns SolverResult with solvability, min moves, and path."""
        start_state = (self.player_start, self.initial_boxes)
        if self.initial_boxes == self.targets:
            return SolverResult(True, 0, [], 0)

        queue: deque = deque([(start_state, [])])
        visited: Set = {start_state}
        explored = 0

        while queue:
            (player, boxes), path = queue.popleft()
            explored += 1

            if explored > self.max_states:
                return SolverResult(
                    solvable=None, min_moves=-1, solution=[],
                    states_explored=explored, timeout=True,
                )

            for move_name, (dx, dy) in MOVES.items():
                nx, ny = player[0] + dx, player[1] + dy

                # Wall collision
                if (nx, ny) in self.walls or not self._in_bounds(nx, ny):
                    continue

                new_boxes = boxes

                # Box interaction
                if (nx, ny) in boxes:
                    if self.mechanic == "slide":
                        # Slide: box slides until hitting wall or another box
                        bx, by = nx + dx, ny + dy
                        # First check: can the box move at all?
                        if (
                            (bx, by) in self.walls
                            or not self._in_bounds(bx, by)
                            or (bx, by) in boxes
                        ):
                            continue
                        # Slide the box
                        while (
                            self._in_bounds(bx + dx, by + dy)
                            and (bx + dx, by + dy) not in self.walls
                            and (bx + dx, by + dy) not in (boxes - frozenset({(nx, ny)}))
                        ):
                            bx, by = bx + dx, by + dy
                        new_boxes = (boxes - frozenset({(nx, ny)})) | frozenset({(bx, by)})
                    else:
                        # Push: box moves exactly 1 tile
                        bx, by = nx + dx, ny + dy
                        if (
                            (bx, by) in self.walls
                            or not self._in_bounds(bx, by)
                            or (bx, by) in boxes
                        ):
                            continue
                        new_boxes = (boxes - frozenset({(nx, ny)})) | frozenset({(bx, by)})

                    # Deadlock pruning (push only -- slide has different deadlock patterns)
                    if self.mechanic == "push":
                        if (bx, by) in self._dead_squares:
                            continue
                        if self._is_freeze_deadlock((bx, by), new_boxes):
                            continue

                new_state = ((nx, ny), new_boxes)
                if new_state in visited:
                    continue
                visited.add(new_state)

                new_path = path + [move_name]

                # Goal check
                if new_boxes == self.targets:
                    return SolverResult(
                        solvable=True, min_moves=len(new_path),
                        solution=new_path, states_explored=explored,
                    )

                queue.append((new_state, new_path))

        return SolverResult(
            solvable=False, min_moves=-1, solution=[],
            states_explored=explored,
        )

    def detect_softlocks(self) -> List[Tuple[int, int]]:
        """Return positions where a box would be permanently stuck (not on a target)."""
        return sorted(self._dead_squares)

    # -- Deadlock detection helpers ------------------------------------

    def _compute_dead_squares(self) -> FrozenSet[Tuple[int, int]]:
        """
        A square is 'dead' if a box placed there can never reach any target.
        Simple heuristic: corner squares that are not targets.
        """
        dead: Set[Tuple[int, int]] = set()
        for x in range(self.width):
            for y in range(self.height):
                if (x, y) in self.walls or (x, y) in self.targets:
                    continue
                if self._is_corner(x, y):
                    dead.add((x, y))
        # Extend to wall-line dead squares
        dead |= self._compute_wall_line_dead(dead)
        return frozenset(dead)

    def _is_corner(self, x: int, y: int) -> bool:
        """Check if (x,y) is a corner: blocked on two perpendicular sides."""
        blocked_up = not self._in_bounds(x, y - 1) or (x, y - 1) in self.walls
        blocked_down = not self._in_bounds(x, y + 1) or (x, y + 1) in self.walls
        blocked_left = not self._in_bounds(x - 1, y) or (x - 1, y) in self.walls
        blocked_right = not self._in_bounds(x + 1, y) or (x + 1, y) in self.walls
        return (blocked_up or blocked_down) and (blocked_left or blocked_right)

    def _compute_wall_line_dead(self, corner_dead: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        """
        If two corner-dead squares are connected along a wall with no targets
        between them, every square on that line segment is also dead.
        """
        extra_dead: Set[Tuple[int, int]] = set()

        # Check horizontal wall lines
        for y in range(self.height):
            corners_on_row = sorted(
                [pos for pos in corner_dead if pos[1] == y], key=lambda p: p[0]
            )
            for i in range(len(corners_on_row)):
                for j in range(i + 1, len(corners_on_row)):
                    x1, x2 = corners_on_row[i][0], corners_on_row[j][0]
                    # Check if entire segment is along a wall (wall above or below every cell)
                    wall_above = all(
                        not self._in_bounds(xx, y - 1) or (xx, y - 1) in self.walls
                        for xx in range(x1, x2 + 1)
                    )
                    wall_below = all(
                        not self._in_bounds(xx, y + 1) or (xx, y + 1) in self.walls
                        for xx in range(x1, x2 + 1)
                    )
                    if not (wall_above or wall_below):
                        continue
                    # Check no target on segment
                    has_target = any((xx, y) in self.targets for xx in range(x1, x2 + 1))
                    no_wall_gap = all((xx, y) not in self.walls for xx in range(x1, x2 + 1))
                    if not has_target and no_wall_gap:
                        for xx in range(x1, x2 + 1):
                            extra_dead.add((xx, y))

        # Check vertical wall lines
        for x in range(self.width):
            corners_on_col = sorted(
                [pos for pos in corner_dead if pos[0] == x], key=lambda p: p[1]
            )
            for i in range(len(corners_on_col)):
                for j in range(i + 1, len(corners_on_col)):
                    y1, y2 = corners_on_col[i][1], corners_on_col[j][1]
                    wall_left = all(
                        not self._in_bounds(x - 1, yy) or (x - 1, yy) in self.walls
                        for yy in range(y1, y2 + 1)
                    )
                    wall_right = all(
                        not self._in_bounds(x + 1, yy) or (x + 1, yy) in self.walls
                        for yy in range(y1, y2 + 1)
                    )
                    if not (wall_left or wall_right):
                        continue
                    has_target = any((x, yy) in self.targets for yy in range(y1, y2 + 1))
                    no_wall_gap = all((x, yy) not in self.walls for yy in range(y1, y2 + 1))
                    if not has_target and no_wall_gap:
                        for yy in range(y1, y2 + 1):
                            extra_dead.add((x, yy))

        return extra_dead

    def _is_freeze_deadlock(
        self, box_pos: Tuple[int, int], all_boxes: FrozenSet[Tuple[int, int]]
    ) -> bool:
        """
        Detect 2x2 freeze deadlocks: four cells forming a 2x2 square where
        every cell is a wall or box, and at least one box is not on a target.
        """
        bx, by = box_pos
        for dx, dy in [(-1, -1), (-1, 0), (0, -1), (0, 0)]:
            corner_x, corner_y = bx + dx, by + dy
            cells = [
                (corner_x, corner_y),
                (corner_x + 1, corner_y),
                (corner_x, corner_y + 1),
                (corner_x + 1, corner_y + 1),
            ]
            all_blocked = all(
                c in self.walls or c in all_boxes for c in cells
            )
            if not all_blocked:
                continue
            # At least one box not on target --> freeze deadlock
            boxes_in_square = [c for c in cells if c in all_boxes]
            if any(b not in self.targets for b in boxes_in_square):
                return True
        return False

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height


# -- Difficulty estimation ---------------------------------------------

def estimate_difficulty(min_moves: int, states_explored: int, grid_area: int) -> int:
    """
    Heuristic difficulty rating 1-5 based on solver metrics.

    Factors:
        - min_moves: more moves --> harder
        - states_explored / grid_area: search density indicates puzzle complexity
    """
    if min_moves <= 0:
        return 0

    # Move-based component
    if min_moves <= 5:
        move_score = 1
    elif min_moves <= 15:
        move_score = 2
    elif min_moves <= 30:
        move_score = 3
    elif min_moves <= 60:
        move_score = 4
    else:
        move_score = 5

    # Search-density component
    density = states_explored / max(grid_area, 1)
    if density < 5:
        density_score = 1
    elif density < 50:
        density_score = 2
    elif density < 500:
        density_score = 3
    elif density < 5000:
        density_score = 4
    else:
        density_score = 5

    return max(1, min(5, round((move_score * 0.6 + density_score * 0.4))))


# -- Level similarity for diversity checking ---------------------------

def level_similarity(level_a: dict, level_b: dict) -> float:
    """
    Compute pairwise similarity between two level definitions.
    Returns a float in [0, 1] where 1 = identical layout.

    Compares: grid dimensions, wall positions, box count, target placement.
    """
    # Dimension similarity
    dim_match = (
        1.0 if level_a.get("grid_width") == level_b.get("grid_width")
        and level_a.get("grid_height") == level_b.get("grid_height")
        else 0.0
    )

    # Wall overlap (Jaccard index)
    walls_a = set(map(tuple, level_a.get("walls", [])))
    walls_b = set(map(tuple, level_b.get("walls", [])))
    if walls_a or walls_b:
        wall_sim = len(walls_a & walls_b) / max(len(walls_a | walls_b), 1)
    else:
        wall_sim = 1.0

    # Box/target count similarity
    box_a, box_b = len(level_a.get("boxes", [])), len(level_b.get("boxes", []))
    box_sim = 1.0 - abs(box_a - box_b) / max(box_a, box_b, 1)

    # Weighted combination
    return 0.3 * dim_match + 0.5 * wall_sim + 0.2 * box_sim
