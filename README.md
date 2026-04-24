# PuzzleForge

**Agentic Puzzle Game Design and Generation System**

A multi-agent system that transforms a user's high-level game concept into a playable, browser-based Sokoban puzzle game. The Game Designer agent chooses between push and slide mechanics based on the user's concept and designs a complete visual theme (emojis, color scheme, entity names). The system separates creative design from automated verification using 5 coordinated agents across two layers. Every level is checked by a BFS solver that supports both mechanics; unresolved failures are logged instead of hidden. The submitted final artifacts are two solver-verified demo games, one push and one slide, and both ship with a move limit of `shortest_solution + 2`.

**Target user:** solo game designers, prototyping teams, and game-design students who want quick puzzle concepts but need solver-backed evidence that generated levels are playable.

## Team

- **Yixiao Li** -- Game Designer + Level Designer agents, BFS solver
- **Kaizhen Tan** -- QA Tester + Debugger agents, HTML/JS template, Streamlit UI
- **Hanzhe Hong** -- Developer/Orchestrator, LangGraph pipeline, routing logic

**Track:** A (Technical Build)
**Course:** 94-815 Agentic Systems Studio, CMU Heinz College, Spring 2026

## Demo Video

Submitted 5-minute walkthrough: <https://drive.google.com/file/d/1wNfMunlP2ebZKdCsQFUoH5tTV9W9tSeh/view?usp=drive_link>

## Architecture

```
User Input --> Game Designer --> Level Designer --> Developer (translate)
--> QA Tester (BFS solver) --> [route_after_qa]:
    all_pass     --> Finalize (playable HTML game)
    has_failures --> Developer classifies & routes:
        config_bugs  --> Debugger --> Apply Patches --> QA re-test
        design_flaws --> Level Designer (redesign) --> Developer --> QA re-test
    max_cycles   --> Finalize (with failures logged)
    generation_failed / budget / timeout --> Finalize (with terminal status)
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
- **Five schema-supported visual themes** -- dark, earthy, icy, gothic, space. Entities render as emoji chosen per theme, and the header shows a mechanic badge.
- **Move limit** -- every level displays `Moves: X / limit` and a `Best: N` par indicator, where `limit = min_moves + 2` using the BFS-computed shortest solution. Exceeding the limit shows a lose message and prompts a reset.
- **Tight difficulty curve** -- the submitted demos start at 6x6 with 2-box tutorial levels and scale to larger 3-box layouts. Live-generation prompts allow a brief 5x5 or 6x6 tutorial but push later levels toward larger grids, more boxes, and longer solver-verified solutions.

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
Loads a pre-built sample push game and renders it as `outputs/demo_game.html`. A pre-rendered slide demo is available at `outputs/demo_slide_game.html`. These are the portfolio-ready final artifacts included with the repository.

### Live pipeline
```bash
python -m src.main "A push-block puzzle about a robot organizing crates in a warehouse"
```
Outputs, when you run the command locally: `outputs/game.html` (playable game), `outputs/design_doc.json`, `outputs/trace.json`. These generated files are not committed as final artifacts because they change on each live run.

### Streamlit dashboard
```bash
streamlit run src/app.py
```
Interactive UI with game generation, trace viewer, QA results, and architecture reference. The "Demo: Push" and "Demo: Slide" buttons load pre-built games and run the BFS solver to populate the Evaluation tab, so move-limit enforcement works even without an API key.

### Final report
```bash
python -B tools/build_report_pdf.py
```
Regenerates `docs/Final Report.pdf` from `docs/final_report.md`.

## Evaluation Results (Phase 3)

Ran 4 live pipeline tests across different concepts (2 push, 2 slide):

| Metric | Result |
|---|---|
| Acceptance target | >= 80% overall post-QA solvability |
| Solvability rate (push) | 90% (9/10 levels) |
| Solvability rate (slide) | 71% (5/7 levels) |
| Solvability rate (overall) | **82% (14/17 levels), meets acceptance target** |
| Terminal output rate | 100% (4/4 runs reached a final status with saved artifacts) |
| Mechanic selection accuracy | 100% (4/4 correct) |
| Mean tokens per run | 6,448 |
| Mean wall-clock time | 30.8 seconds |
| Debug cycles needed | 0--3 per run |

12 test cases executed (see `eval/test_cases.csv`). 8 failures documented and analyzed (see `eval/failure_log.md`).

### Baseline Comparison (single-LLM vs multi-agent)

The single-LLM baseline is a lighter comparison condition: one prompt generates all levels without solver verification, specialized roles, or a repair loop. It is used to show the value of verification and repair, not to claim a controlled benchmark.

| Metric | Single-LLM | Multi-Agent Pipeline |
|---|---|---|
| Slide solvability | **30%** | **71%** (+41 pp) |
| Overall solvability | 65% | 82% |
| Solver verification | None | BFS ground truth |
| Debug loop | None | Up to 3 cycles |

The multi-agent pipeline shows the clearest lift on slide levels, where verification and repair raise solvability from 30% to 71%. See `eval/baseline.py` and `eval/baseline_results.json`.

## Summary of Outputs

- **Final playable demos:** `outputs/demo_game.html` (push, Space Station) and `outputs/demo_slide_game.html` (slide, Arctic) -- pre-rendered and solver-verified, with move limits baked into the HTML.
- **Live evaluation evidence:** `outputs/run1/`, `run2/`, `run3/`, and `run4/` include the saved games, design documents, and traces from the Phase 3 live runs.
- **Sample configs:** `outputs/sample_traces/sample_game_config.json` (push), `outputs/sample_traces/sample_slide_config.json` (slide), and `outputs/sample_traces/sample_interaction_trace.json` for reproducible demos.

## Repository Structure

```
PuzzleForge/
+-- README.md                    # This file
+-- AI_USAGE.md                  # AI tool usage disclosure
+-- requirements.txt             # Python dependencies
+-- .env.example                 # Environment template
+-- docs/
|   +-- Final Report.pdf         # Phase 3 final report (academic format)
|   +-- final_report.md          # Markdown source for final report
|   +-- architecture_diagram.pdf # System architecture diagram
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
|   +-- test_cases.csv           # 12 test scenarios with results
|   +-- evaluation_results.csv   # Pipeline + baseline run data
|   +-- evaluation_plan.md       # Evaluation methodology
|   +-- failure_log.md           # 8 documented failures with analysis
|   +-- baseline.py              # Single-LLM baseline script
|   +-- baseline_results.json    # Baseline run results
|   \-- version_notes.md         # Version history
\-- outputs/
    +-- demo_game.html           # Final push demo (Space Station)
    +-- demo_slide_game.html     # Final slide demo (Arctic)
    +-- run1/ run2/ run3/ run4/  # Live test run evidence
    \-- sample_traces/           # Sample configs and sample trace
```

## Known Limitations

- The 500K-state solver cap handles the Phase 3 demo levels but may still be too low for complex 15x15 grids, which can produce a solver timeout (D4) that routes the level back for redesign.
- Slide-mechanic levels remain harder than push levels (71% vs 90% solvability). The prompt guidance improves the result, but the remaining gap is a clear next engineering target.
- The live evaluation includes two level-count contract failures: RUN-02 produced 4/5 levels and RUN-04 produced 3/5 levels. These are counted directly in the evaluation rather than hidden behind the bundled demos.
- Level Designer redesigns do not always preserve monotonic difficulty progression; the redesign prompt is not yet aware of the other levels' difficulty ratings.
- Debugger LLM-based fixes can fail in two ways: malformed patches are rejected or escalated by Pydantic validation, while structurally valid but ineffective patches are caught by the QA re-test on the following cycle.
