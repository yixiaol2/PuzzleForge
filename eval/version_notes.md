# PuzzleForge -- Version Notes

## v0.3-phase3 (Phase 3, 2026-04-14)

### New features
- **Push + slide mechanics:** Game Designer chooses between push (standard Sokoban) and slide (ice puzzle) based on user concept. BFS solver supports both. HTML template renders both with correct physics.
- **Theme system:** Game Designer outputs ThemeDetails (color_scheme, emoji icons, entity names, win message). 5 color themes: dark, earthy, icy, gothic, space. Each game has a unique visual identity.
- **Slide-specific level design:** Level Designer prompt includes slide physics guidance (targets next to walls, interior walls as stoppers).
- **Streamlit demo selection:** Two demo buttons (push/slide) showcasing different mechanics and themes.

### Bug fixes
- **F-004: Silent redesign failure** -- Added retry logic with error feedback in `_redesign_levels()`
- **F-005: Diversity hard-blocking** -- Added soft-fail logic in `route_after_qa()`
- **F-006: Debugger processing stale levels** -- Use only current-cycle `failed_level_ids`
- **F-007: Slide levels harder for LLM** -- Added slide-specific design guidance (partially mitigated)
- **F-008: Level Designer shortfall on slide** -- Known limitation; retry recovers partial results

### What changed
- `src/models.py` -- Added ThemeDetails model; MechanicSpec accepts push/slide; GameConfig carries primary_mechanic + theme_details
- `src/agents/game_designer.py` -- Complete rewrite: LLM chooses mechanic and designs visual theme
- `src/agents/level_designer.py` -- Slide-specific design guidance; mechanic context in fresh design and redesign prompts
- `src/agents/developer.py` -- Passes primary_mechanic and theme_details to GameConfig
- `src/agents/qa_tester.py` -- Passes mechanic type to solver constructor
- `src/solver/sokoban_solver.py` -- Added slide mechanic (box slides until hitting wall/box); dead-square pruning disabled for slide
- `src/engine/templates/sokoban.html` -- Complete rewrite: 5 color themes, emoji rendering, slide JS mechanics, mechanic badge
- `src/engine/template_engine.py` -- ensure_ascii=False for emoji preservation
- `src/orchestrator/routing.py` -- D1 updated: only flags unsupported mechanics (push and slide both supported)
- `src/app.py` -- Two demo buttons (push/slide); updated demo trace data
- `src/main.py` -- Embedded demo configs for push (Space Station) and slide (Arctic Expedition)

### Live pipeline run results (v0.3)
- Run 1: "Space station cargo robot" (push, space) -- 4/5 solvable, 3 debug cycles, 6,093 tokens, ~28s
- Run 2: "Penguin sliding ice blocks" (slide, icy) -- 3/4 solvable, 3 debug cycles, 8,538 tokens, ~44s
- Run 3: "Gothic dungeon gem puzzle" (push, gothic) -- 5/5 solvable, 0 debug cycles, 2,969 tokens, ~15s
- Run 4: "Zero-gravity curling" (slide, space) -- 2/3 solvable, 3 debug cycles, 8,193 tokens, ~36s
- Overall: 14/17 solvable (82%), push: 90%, slide: 71%. Mean tokens: 6,448. Mean time: 30.9s.

### Baseline comparison (single-LLM vs multi-agent)
- Single-LLM baseline: 13/20 solvable (65%). Push: 100%, Slide: 30%. Mean tokens: 1,348.
- Multi-agent pipeline: 14/17 solvable (82%). Push: 90%, Slide: 71%. Mean tokens: 6,448.
- Key finding: pipeline's debug loop more than doubles slide solvability (30% -> 71%).

---

## v0.1-prototype (Phase 2, 2026-04-07)

### What's implemented
- Full LangGraph pipeline with 9 nodes and 4 conditional edges
- Game Designer agent (LLM-based, temp 0.8)
- Level Designer agent (LLM-based, temp 0.7) with redesign support
- Developer/Orchestrator (deterministic translation + formal routing criteria)
- QA Tester agent (BFS solver with deadlock detection, difficulty estimation, diversity checking)
- Debugger agent (LLM-based, temp 0.3) with escalation threshold
- Sokoban BFS solver with corner deadlock, wall-line deadlock, and freeze deadlock detection
- HTML/JS game template with keyboard/touch controls, undo, level progression
- Streamlit dashboard with trace viewer, QA results display, and architecture view
- Pydantic validation on all inter-agent JSON communication
- Append-only trace logging via LangGraph Annotated state

### Known limitations
- Solver timeout at 200K states may be too low for complex 15x15 grids
- Level Designer sometimes produces levels with box/target count mismatch (caught by Pydantic)
- HTML template renders push and slide mechanics; switch/teleport are not yet implemented
- Debugger relies on LLM for fix generation, which occasionally produces invalid patches

### Architecture decisions made this phase
- **LangGraph StateGraph** as orchestration framework (addresses Phase 1 feedback #2)
- **TypedDict + Annotated[List, operator.add]** for append-only trace accumulation
- **Deterministic routing criteria** encoded in `routing.py` (addresses Phase 1 feedback #3)
- **Debugger 25% escalation threshold** preserved from Phase 1 canvas as a quantitative rule
