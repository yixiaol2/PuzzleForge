# -*- coding: utf-8 -*-
"""
PuzzleForge -- Streamlit Dashboard

Interactive UI for running the PuzzleForge pipeline, viewing traces,
and inspecting generated games.

Run: streamlit run src/app.py
"""

from __future__ import annotations
import json
import os
import sys
import time

import streamlit as st

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _demo_trace() -> list:
    """Generate a demo trace for display purposes."""
    return [
        {"step": 1, "agent": "Game Designer", "action": "generate_game_spec",
         "input_summary": "User concept: A robot organizing cargo pods in a space station",
         "output_summary": "Generated spec: sokoban, theme='space station', mechanic=push, 5 levels",
         "tokens_used": 1250, "duration_seconds": 2.3, "timestamp": "2026-04-05T14:30:00"},
        {"step": 2, "agent": "Level Designer", "action": "design_all_levels",
         "input_summary": "Game spec: space station, 5 levels, mechanic: push",
         "output_summary": "Designed 5 levels, grids: ['5x5', '6x5', '7x6', '7x7', '8x7']",
         "tokens_used": 2800, "duration_seconds": 4.1, "timestamp": "2026-04-05T14:30:03"},
        {"step": 3, "agent": "Developer", "action": "translate_to_config",
         "input_summary": "Translating 5 level defs + game spec",
         "output_summary": "Produced GameConfig with 5 levels",
         "tokens_used": 0, "duration_seconds": 0.01, "timestamp": "2026-04-05T14:30:07"},
        {"step": 4, "agent": "QA Tester", "action": "test_all_levels",
         "input_summary": "Testing 5 levels from game config",
         "output_summary": "4/5 levels solvable. Difficulty curve monotonic: True. Diversity issues: 0.",
         "tokens_used": 0, "duration_seconds": 0.5, "timestamp": "2026-04-05T14:30:07"},
        {"step": 5, "agent": "Developer", "action": "classify_and_route_failures",
         "input_summary": "Classifying 1 failed levels",
         "output_summary": "Config bugs: [3], Design flaws: []",
         "tokens_used": 0, "duration_seconds": 0.01, "timestamp": "2026-04-05T14:30:08"},
        {"step": 6, "agent": "Debugger", "action": "fix_config_bugs",
         "input_summary": "Fixing levels [3] flagged as config bugs",
         "output_summary": "Debugger processed 1 levels: 1 patched, 0 escalated to redesign",
         "tokens_used": 850, "duration_seconds": 1.8, "timestamp": "2026-04-05T14:30:08"},
        {"step": 7, "agent": "Developer", "action": "apply_debug_patches",
         "input_summary": "Applying 1 patches",
         "output_summary": "Patched levels: [3]",
         "tokens_used": 0, "duration_seconds": 0.01, "timestamp": "2026-04-05T14:30:10"},
        {"step": 8, "agent": "QA Tester", "action": "test_all_levels",
         "input_summary": "Testing 5 levels from game config (re-test after debug)",
         "output_summary": "5/5 levels solvable. Difficulty curve monotonic: True. Diversity issues: 0.",
         "tokens_used": 0, "duration_seconds": 0.4, "timestamp": "2026-04-05T14:30:10"},
        {"step": 9, "agent": "Developer", "action": "finalize_game",
         "input_summary": "Packaging final game output",
         "output_summary": "HTML: 4823 chars, design doc compiled",
         "tokens_used": 0, "duration_seconds": 0.02, "timestamp": "2026-04-05T14:30:11"},
    ]


st.set_page_config(page_title="PuzzleForge", page_icon=":jigsaw:", layout="wide")

st.title("PuzzleForge")
st.caption("Agentic Puzzle Game Design and Generation System")

# -- Sidebar ---------------------------------------------------------------
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    model = st.selectbox("Model", ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"], index=0)
    demo_mode = st.checkbox("Demo Mode (no API key needed)", value=True)

    st.divider()
    st.header("Pipeline Settings")
    max_cycles = st.slider("Max Debug Cycles", 1, 5, 3)
    level_count = st.slider("Number of Levels", 3, 8, 5)

    st.divider()
    st.markdown(
        "**PuzzleForge** - CMU 94-815\n\n"
        "Team: Yixiao Li, Kaizhen Tan, Hanzhe Hong"
    )

# -- Main area -------------------------------------------------------------
tabs = st.tabs(["Generate", "Trace Viewer", "Evaluation", "Architecture"])

# -- Tab 1: Generate -------------------------------------------------------
with tabs[0]:
    concept = st.text_area(
        "Describe your puzzle game concept:",
        placeholder="e.g., A push-block puzzle about a robot organizing crates in a warehouse. "
                    "Start with a simple tutorial level, then increase difficulty with more boxes, "
                    "larger grids, and tighter wall configurations.",
        height=100,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        run_btn = st.button("Generate Game", type="primary", use_container_width=True)
    with col2:
        demo_push_btn = st.button("Demo: Push 🤖", use_container_width=True)
    with col3:
        demo_slide_btn = st.button("Demo: Slide 🐧", use_container_width=True)

    demo_variant = None
    if demo_push_btn or (run_btn and demo_mode):
        demo_variant = "push"
    elif demo_slide_btn:
        demo_variant = "slide"

    if demo_variant:
        with st.spinner("Loading demo game..."):
            from src.engine.template_engine import render_game
            from src.solver.sokoban_solver import SokobanSolver, estimate_difficulty
            # Try loading from sample file first
            sample_file = "sample_slide_config.json" if demo_variant == "slide" else "sample_game_config.json"
            sample_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "outputs", "sample_traces", sample_file,
            )
            if os.path.exists(sample_path):
                import json as _json
                with open(sample_path, "r", encoding="utf-8") as f:
                    game_config = _json.load(f)
            else:
                from src.main import _embedded_demo_config
                game_config = _embedded_demo_config(variant=demo_variant)
            # Run BFS solver on demo levels to produce QA report
            mechanic = game_config.get("primary_mechanic", "push")
            level_reports = []
            for lvl in game_config.get("levels", []):
                solver = SokobanSolver(
                    grid_width=lvl["grid_width"],
                    grid_height=lvl["grid_height"],
                    walls=[tuple(w) for w in lvl["walls"]],
                    boxes=[tuple(b) for b in lvl["boxes"]],
                    targets=[tuple(t) for t in lvl["targets"]],
                    player_start=tuple(lvl["player_start"]),
                    max_states=200_000,
                    mechanic=mechanic,
                )
                r = solver.solve()
                grid_area = lvl["grid_width"] * lvl["grid_height"]
                diff = estimate_difficulty(r.min_moves or 0, r.states_explored or 0, grid_area)
                # Inject min_moves into level so HTML move-limit feature works
                # even if the sample JSON did not include min_moves.
                if r.min_moves and r.min_moves > 0:
                    lvl["min_moves"] = r.min_moves
                level_reports.append({
                    "level_id": lvl["level_id"],
                    "solvable": r.solvable is True,
                    "min_moves": r.min_moves or -1,
                    "states_explored": r.states_explored or 0,
                    "difficulty_rating": diff,
                    "issues": [],
                })
            solvable_count = sum(1 for lr in level_reports if lr["solvable"])
            qa_report = {
                "summary": f"{solvable_count}/{len(level_reports)} levels solvable",
                "level_reports": level_reports,
            }
            # Render AFTER min_moves are populated, so the move limit is baked into the HTML
            html = render_game(game_config)
            st.session_state["game_config"] = game_config
            st.session_state["game_html"] = html
            st.session_state["trace"] = _demo_trace()
            st.session_state["qa_report"] = qa_report
            mechanic_label = mechanic.upper()
            st.success(f"Demo loaded! Mechanic: {mechanic_label} | Theme: {game_config.get('theme', 'default')}")

    elif run_btn and not demo_mode and concept:
        if not api_key:
            st.error("Please provide an OpenAI API key in the sidebar.")
        else:
            os.environ["OPENAI_API_KEY"] = api_key
            os.environ["OPENAI_MODEL"] = model
            os.environ["PUZZLEFORGE_DEMO_MODE"] = "false"

            with st.spinner("Running PuzzleForge pipeline..."):
                from src.orchestrator.graph import run_pipeline
                final_state = run_pipeline(
                    concept,
                    max_debug_cycles=max_cycles,
                    level_count=level_count,
                )
                st.session_state["game_config"] = final_state.get("game_config")
                st.session_state["game_html"] = final_state.get("final_game_html", "")
                st.session_state["trace"] = final_state.get("trace_log", [])
                st.session_state["qa_report"] = final_state.get("qa_report")
                st.session_state["final_state"] = final_state
                st.success(
                    f"Pipeline complete! Status: {final_state.get('pipeline_status')} | "
                    f"Tokens: {final_state.get('total_tokens', 0)} | "
                    f"Debug cycles: {final_state.get('debug_cycle', 0)}"
                )

    # Display game
    if "game_html" in st.session_state and st.session_state["game_html"]:
        st.subheader("Generated Game")
        st.components.v1.html(st.session_state["game_html"], height=650, scrolling=True)

        # Download button
        st.download_button(
            "Download Game (HTML)",
            st.session_state["game_html"],
            file_name="puzzleforge_game.html",
            mime="text/html",
        )

    # Display game config
    if "game_config" in st.session_state and st.session_state["game_config"]:
        with st.expander("Game Configuration JSON"):
            st.json(st.session_state["game_config"])

# -- Tab 2: Trace Viewer ---------------------------------------------------
with tabs[1]:
    st.subheader("Agent Interaction Trace")

    if "trace" in st.session_state and st.session_state["trace"]:
        trace = st.session_state["trace"]
        for entry in trace:
            agent_labels = {
                "Game Designer": "[Design]",
                "Level Designer": "[Layout]",
                "Developer": "[Orch]",
                "QA Tester": "[QA]",
                "Debugger": "[Debug]",
            }
            label = agent_labels.get(entry.get("agent", ""), "[?]")
            with st.expander(
                f"{label} Step {entry['step']}: {entry['agent']} -- {entry['action']}  "
                f"({entry.get('tokens_used', 0)} tokens, {entry.get('duration_seconds', 0)}s)"
            ):
                st.markdown(f"**Input:** {entry.get('input_summary', 'N/A')}")
                st.markdown(f"**Output:** {entry.get('output_summary', 'N/A')}")
                st.markdown(f"**Timestamp:** {entry.get('timestamp', 'N/A')}")
    else:
        st.info("Run the pipeline first to see the interaction trace.")

# -- Tab 3: Evaluation -----------------------------------------------------
with tabs[2]:
    st.subheader("QA Results & Evaluation Metrics")

    if "qa_report" in st.session_state and st.session_state["qa_report"]:
        qa = st.session_state["qa_report"]
        st.markdown(f"**Summary:** {qa.get('summary', 'N/A')}")

        # Level-by-level results
        for lr in qa.get("level_reports", []):
            status = "PASS" if lr.get("solvable") else "FAIL"
            stars = "*" * lr.get("difficulty_rating", 0)
            st.markdown(
                f"[{status}] **Level {lr['level_id']}** -- "
                f"Solvable: {lr['solvable']}, "
                f"Min moves: {lr['min_moves']}, "
                f"Difficulty: {stars}"
            )
            if lr.get("issues"):
                for issue in lr["issues"]:
                    st.markdown(f"  - WARNING: {issue}")

        # Difficulty curve chart
        ratings = [lr.get("difficulty_rating", 0) for lr in qa.get("level_reports", [])]
        if ratings:
            import plotly.graph_objects as go
            fig = go.Figure(data=go.Scatter(
                x=list(range(1, len(ratings)+1)), y=ratings,
                mode='lines+markers', marker=dict(size=10),
                line=dict(color='#e94560'),
            ))
            fig.update_layout(
                title="Difficulty Curve", xaxis_title="Level", yaxis_title="Difficulty (1-5)",
                template="plotly_dark", height=300,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Run the pipeline to see evaluation results.")

# -- Tab 4: Architecture ---------------------------------------------------
with tabs[3]:
    st.subheader("System Architecture")
    st.markdown("""
    ```
    User Input
        |
        v
    +-------------------+
    |  Game Designer    |  Design Layer
    |  (LLM, temp 0.8) |  -- creative generation
    +--------+----------+
             | game_spec (JSON)
             v
    +-------------------+
    |  Level Designer   |  Design Layer
    |  (LLM, temp 0.7) |  -- layout generation
    +--------+----------+
             | level_definitions (JSON array)
             v
    +-------------------+
    |    Developer      |  Implementation Layer
    |  (Orchestrator)   |  -- translate to config
    +--------+----------+
             | game_config (JSON)
             v
    +-------------------+
    |    QA Tester      |  Implementation Layer
    |  (BFS Solver)     |  -- deterministic verification
    +--------+----------+
             |
         +---+---+
    All Pass?   Failures?
         |          |
         v          v
    Finalize   Developer Routes
                   |
              +----+----+
          Config Bug  Design Flaw
              |           |
              v           v
          Debugger    Level Designer
          (LLM 0.3)   (redesign)
              |           |
              +-----+-----+
                    v
               QA Re-test
               (max 3 cycles)
    ```
    """)

    st.markdown("**Routing Criteria** (deterministic, not LLM-based):")
    st.markdown("""
    | ID | Criterion | Routes To |
    |---|---|---|
    | C1 | Default: attempt placement fix | Debugger |
    | C2 | Unsolvable despite adequate floor space (wall blockage) | Debugger |
    | C3 | Player starts on wall/box | Debugger |
    | C4 | Box in corner deadlock (dead square) | Debugger |
    | C5 | Box/target count mismatch | Debugger |
    | D1 | Unsupported mechanics (only push/slide supported) | Level Designer |
    | D2 | Grid too small: floor tiles < boxes x 3 + 2 | Level Designer |
    | D3 | >2 QA issues: structural redesign needed | Level Designer |
    | D4 | Solver timeout (>200K states) | Level Designer |
    | D5 | Layout similarity > 0.5 (diversity) | Level Designer |
    """)


