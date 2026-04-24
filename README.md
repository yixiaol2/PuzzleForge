# PuzzleForge

**Agentic Puzzle Game Design and Generation System**

A multi-agent system that transforms a user's high-level game concept into a playable, browser-based Sokoban puzzle game. The Game Designer agent chooses between push and slide mechanics based on the user's concept and designs a complete visual theme (emojis, color scheme, entity names). The system separates creative design from automated verification using 5 coordinated agents across two layers, with every level verified solvable by a BFS solver that supports both mechanics. Each generated level ships with a move limit of `shortest_solution + 2`, computed by the solver, so players face a meaningful challenge and the game transitions to a `lost` state if they exceed it.

## Team

- **Yixiao Li** -- Game Designer + Level Designer agents, BFS solver
- **Kaizhen Tan** -- QA Tester + Debugger agents, HTML/JS template, Streamlit UI
- **Hanzhe Hong** -- Developer/Orchestrator, LangGraph pipeline, routing logic

**Track:** A (Technical Build)
**Course:** 94-815 Agentic Systems Studio, CMU Heinz College, Spring 2026

## Demo Video

5-minute walkthrough: <https://drive.google.com/file/d/1wNfMunlP2ebZKdCsQFUoH5tTV9W9tSeh/view?usp=drive_link>

## Architecture

```
User Input --> Game Designer --> Level Designer --> Developer (translate)
--> QA Tester (BFS solver) --> [route_after_qa]:
    all_pass     --> Finalize (playable HTML game)
    has_failures --> Developer classifies & routes:
        config_bugs  --> Debugger --> Apply Patches --> QA re-test
        design_flaws --> Level Designer (redesign) --> QA re-test
    max_cycles   --> Finalize (with failures logged)
```

| Agent | Layer | Role | LLM? |
|---|---|---|---|
| Game Designer | Design | Generate game spec from user concept | Yes (temp 0.8) |
| Level Designer | Design | Create/redesign grid layouts | Yes (temp 0.7) |
| Developer | Implementation | Translate designs, route failures | No (deterministic) |
| QA Tester | Implementation | Verify solvability via BFS solver | No (deterministic) |
| Debugger | Implementation | Minimal config fixes | Yes (temp 0.3) |

**Key principle:** Deterministic where possible, LLM where necessary. Solvability, routing, and iteration control are handled by code -- not LLM judgment.

## Game Features

- **Two mechanics** -- push (box moves one tile) and slide (box slides until it hits a wall or another box). The Game Designer picks the mechanic from the user concept.
- **Five visual themes** -- dark, earthy, icy, gothic, space. Entities render as emoji chosen per theme, and the header shows a mechanic badge.
- **Move limit** -- every level displays `Moves: X / limit` and a `Best: N` par indicator, where `limit = min_moves + 2` using the BFS-computed shortest solution. Exceeding the limit shows a lose message and prompts a reset.
- **Tight difficulty curve** -- minimum 6x6 grids, 2-box tutorial levels scaling to 4-5 box expert levels, with layout-driven progression via interior walls and multi-room structures.

## Setup

### Prerequisites
- Python 3.10+
- OpenAI API key (for live runs; demo mode works without one)

### Installation

```bash
cd PuzzleForge
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Usage

### Demo mode (no API key required)
```bash
python -m src.main --demo
```
Loads a pre-built sample push game and renders it as `outputs/demo_game.html`. A pre-rendered slide demo is available at `outputs/demo_slide_game.html`.

### Live pipeline
```bash
python -m src.main "A push-block puzzle about a robot organizing crates in a warehouse"
```
Outputs: `outputs/game.html` (playable game), `outputs/design_doc.json`, `outputs/trace.json`.

### Streamlit dashboard
```bash
streamlit run src/app.py
```
Interactive UI with game generation, trace viewer, QA results, and architecture reference. The "Demo: Push" and "Demo: Slide" buttons load pre-built games and run the BFS solver to populate the Evaluation tab, so move-limit enforcement works even without an API key.

## Evaluation Results (Phase 3)

Ran 4 live pipeline tests across different concepts (2 push, 2 slide):

| Metric | Result |
|---|---|
| Solvability rate (push) | 90% (9/10 levels) |
| Solvability rate (slide) | 71% (5/7 levels) |
| Solvability rate (overall) | 82% (14/17 levels) |
| Pipeline completion | 100% (4/4 runs) |
| Mechanic selection accuracy | 100% (4/4 correct) |
| Mean tokens per run | 6,448 |
| Mean wall-clock time | 30.9 seconds |
| Debug cycles needed | 0--3 per run |

11 test cases executed (see `eval/test_cases.csv`). 8 failures documented and analyzed (see `eval/failure_log.md`).

### Baseline Comparison (single-LLM vs multi-agent)

| Metric | Single-LLM | Multi-Agent Pipeline |
|---|---|---|
| Slide solvability | **30%** | **71%** (+41 pp) |
| Overall solvability | 65% | 82% |
| Solver verification | None | BFS ground truth |
| Debug loop | None | Up to 3 cycles |

The multi-agent pipeline's debug feedback loop more than doubles slide solvability versus a single LLM call. See `eval/baseline.py` and `eval/baseline_results.json`.

## Summary of Outputs

- **Playable games:** `outputs/game.html` (latest), plus `outputs/run2/`, `run3/`, `run4/` from live test runs.
- **Demo games:** `outputs/demo_game.html` (push, Space Station) and `outputs/demo_slide_game.html` (slide, Arctic) -- pre-rendered and solver-verified, with move limits baked into the HTML.
- **Design documents:** `outputs/design_doc.json` with the full game spec, level definitions, QA report, and routing decisions.
- **Execution traces:** `outputs/trace.json` showing every agent interaction with token counts and timing.
- **Sample configs:** `outputs/sample_traces/sample_game_config.json` (push) and `sample_slide_config.json` (slide) for reproducible demos.

## Repository Structure

```
PuzzleForge/
+-- README.md                    # This file
+-- AI_USAGE.md                  # AI tool usage disclosure
+-- requirements.txt             # Python dependencies
+-- .env.example                 # Environment template
+-- docs/
|   +-- Final Report.pdf         # Phase 3 final report (academic format)
|   +-- architecture_diagram.pdf # System architecture diagram
|   +-- project_summary.pdf      # One-page project summary
|   +-- PuzzleForge_Executive_Summary.pptx  # Executive summary deck
|   \-- screenshots/             # Screenshots with index
+-- media/
|   \-- demo_video_link.txt      # 5-minute video link
+-- src/
|   +-- models.py                # Pydantic data models
|   +-- state.py                 # LangGraph state schema (TypedDict)
|   +-- config.py                # Configuration and thresholds
|   +-- main.py                  # CLI entry point
|   +-- app.py                   # Streamlit dashboard
|   +-- agents/                  # 5 agent implementations
|   |   +-- game_designer.py     # LLM, temp 0.8
|   |   +-- level_designer.py    # LLM, temp 0.7
|   |   +-- developer.py         # Deterministic translate + patch
|   |   +-- qa_tester.py         # BFS solver, no LLM
|   |   \-- debugger.py          # LLM, temp 0.3
|   +-- solver/
|   |   \-- sokoban_solver.py    # BFS with deadlock detection (push + slide)
|   +-- engine/
|   |   +-- template_engine.py   # GameConfig -> playable HTML
|   |   \-- templates/sokoban.html  # Themed renderer with move-limit enforcement
|   +-- orchestrator/
|   |   +-- graph.py             # LangGraph StateGraph (9 nodes)
|   |   \-- routing.py           # 10 deterministic routing rules
|   \-- utils/
|       +-- trace_logger.py      # Append-only trace entries
|       \-- llm.py               # Centralized LLM wrapper
+-- eval/
|   +-- test_cases.csv           # 11 test scenarios with results
|   +-- evaluation_results.csv   # Pipeline + baseline run data
|   +-- evaluation_plan.md       # Evaluation methodology
|   +-- failure_log.md           # 8 documented failures with analysis
|   +-- baseline.py              # Single-LLM baseline script
|   +-- baseline_results.json    # Baseline run results
|   \-- version_notes.md         # Version history
\-- outputs/
    +-- game.html                # Latest generated game
    +-- design_doc.json          # Latest design document
    +-- trace.json               # Latest execution trace
    +-- demo_game.html           # Pre-built push demo (Space Station)
    +-- demo_slide_game.html     # Pre-built slide demo (Arctic)
    +-- run2/ run3/ run4/        # Additional test run outputs
    \-- sample_traces/           # Sample configs for reproducible demos
```

## Known Limitations

- The 200K-state solver cap may be too low for complex 15x15 grids, which can produce a solver timeout (D4) that routes the level back for redesign.
- Slide-mechanic levels remain harder for the LLM to design correctly than push levels (71% vs 90% solvability); the slide-specific prompt guidance only partially closes the gap.
- Level Designer redesigns do not always preserve monotonic difficulty progression; the redesign prompt is not yet aware of the other levels' difficulty ratings.
- Debugger LLM-based fixes occasionally produce invalid patches, caught by the QA re-test on the following cycle.
