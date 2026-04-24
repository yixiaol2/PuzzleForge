# AI Usage Disclosure

**Project:** PuzzleForge -- Agentic Puzzle Game Design and Generation System
**Course:** 94-815 Agentic Systems Studio, CMU Heinz College, Spring 2026
**Team:** Yixiao Li, Kaizhen Tan, Hanzhe Hong

---

## AI Tools Used in Project Development

### 1. Claude Code (Anthropic Claude Opus 4)

| Field | Detail |
|---|---|
| **Tool name and version** | Claude Code, Claude Opus 4 |
| **What we used it for** | Code scaffolding for Python modules (agent classes, Pydantic models, Streamlit UI layout). Brainstorming prompt templates for LLM agents. Reviewing solver algorithm for edge cases. In Phase 3: diagnosing live pipeline bugs, writing evaluation documentation, generating PDF report. |
| **Exact prompts / tasks** | Phase 2: "Help implement a BFS Sokoban solver with corner and wall-line deadlock detection." "Review the routing criteria for completeness." "Scaffold a Streamlit dashboard with tabs." Phase 3: "Read all project files and understand Phase 3 requirements." Assisted with running live pipeline tests, diagnosing 3 bugs found during testing, and updating evaluation files. |
| **What we changed manually** | All architectural decisions (LangGraph choice, state schema design, routing criteria, agent role boundaries) were designed by the team before any AI assistance. Solver algorithm designed from first principles; AI output used as starting point then rewritten for correctness. Routing criteria (10 rules) defined entirely by the team. Core agent prompts were written by the team and later edited for validation, retry, and level-count reliability. Bug fixes (F-004, F-005, F-006) were identified through live testing and diagnosed collaboratively. |
| **What we verified independently** | Solver correctness: tested against 6 hand-solved Sokoban puzzles (100% agreement). Deadlock detection: manually constructed corner, wall-line, and freeze deadlock cases. Routing criteria: tested each of 10 criteria with synthetic levels. Pipeline flow: traced execution manually through each node. Bug fixes verified by re-running the full pipeline (4 live runs; 4/4 reached terminal status with saved artifacts, 14/17 levels solvable, with remaining failures logged). |

### 2. GPT-4o (OpenAI) -- As Pipeline Component

| Field | Detail |
|---|---|
| **Tool name and version** | GPT-4o (gpt-4o-2024-08-06) via OpenAI API |
| **What we used it for** | Runtime LLM backend for three agents inside the PuzzleForge pipeline: Game Designer (generates game specs), Level Designer (generates level layouts), Debugger (generates minimal config fixes). |
| **Exact prompts / tasks** | System prompts and user prompts defined in `src/agents/game_designer.py`, `src/agents/level_designer.py`, and `src/agents/debugger.py`. Each prompt includes constraints, output format specifications, and operating rules. |
| **What we changed manually** | LLM outputs are not used as-is. Game specifications, level definitions, game configs, and debug patches pass through Pydantic validation before downstream use. Every accepted evaluation level is independently verified by the BFS solver. Invalid LLM outputs trigger automatic retry with error feedback. The LLM is a tool within the system, not the system's designer. |
| **What we verified independently** | Solvability verified by deterministic BFS solver -- zero reliance on LLM claims. Difficulty ratings computed from solver metrics (min_moves, states_explored), not LLM estimates. Routing decisions use formal criteria code, not LLM classification. |

### 3. GitHub Copilot

| Field | Detail |
|---|---|
| **Tool name and version** | GitHub Copilot (VS Code extension) |
| **What we used it for** | Inline code completion suggestions during development |
| **What we changed manually** | All suggestions reviewed, accepted/rejected per-line, modified for project conventions |
| **What we verified independently** | Accepted suggestions were checked through targeted compile checks, solver verification on bundled demo configs, pipeline evidence review, and manual inspection of changed files. |

### 4. OpenAI Codex (GPT-5)

| Field | Detail |
|---|---|
| **Tool name and version** | OpenAI Codex, GPT-5 |
| **What we used it for** | Final Phase 3 consistency audit and remediation: checked rubric coverage, found stale final outputs, fixed retry and validation logic, cleaned duplicate output files, regenerated demo HTML files, and updated documentation to match the actual artifacts. |
| **Exact prompts / tasks** | The team asked Codex to inspect the Phase 3 folder against the course requirements, score the work, identify every missing or inconsistent requirement, then "fix everything" while keeping useful evidence files and deleting misleading unused outputs. |
| **What we changed manually** | The team reviewed the recommendations and aligned the final artifact, evaluation, and failure descriptions with the files in the repository. Code changes were limited to runtime configuration loading, generation failure handling, exact level-count validation, and terminal status preservation. Documentation changes were limited to making the final artifact and evidence descriptions match the submitted artifacts. |
| **What we verified independently** | Re-ran Python compile checks, LangGraph graph construction, BFS verification for both bundled demo configs, rendered both demo HTML files, checked evaluation CSV parsing, and rebuilt the final report PDF from Markdown. |

---

## Key Principle: AI as Tool-in-the-Loop, Not Decision-Maker

The distinction between "AI as a development aid" and "AI as a component of the system" is maintained throughout:

- **Development aid:** Claude Code and Copilot helped write code faster. All design decisions, architecture choices, and evaluation criteria were made by the team.
- **System component:** GPT-4o runs inside the pipeline as the reasoning engine for three agents. Its outputs are always validated (Pydantic) and verified (BFS solver). Critical decisions (solvability, routing, iteration caps) are never delegated to the LLM.

No AI-generated content appears in reports without human review and verification.
