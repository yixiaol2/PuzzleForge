# PuzzleForge -- Evaluation Plan

## Overview

This evaluation plan defines 12 test scenarios covering the core pipeline, failure handling, governance enforcement, and baseline comparison. Each scenario maps to a specific success criterion from Phase 1 and targets a distinct design concern.

## Evaluation Methodology

### Automated evaluation (QA Tester agent)
- **Solvability:** BFS solver provides ground-truth pass/fail per level.
- **Difficulty curve:** Computed from min_moves sequence; checked for monotonicity.
- **Diversity:** Pairwise Jaccard similarity on wall positions; threshold <= 0.5.
- **Refinement lift:** Compare pre-debug vs. post-debug solvability rates.

### Pipeline-level evaluation
- **Completion rate:** Percentage of runs producing >= 3 solvable levels.
- **Latency:** Wall-clock time from concept to final game.
- **Token budget compliance:** Total tokens must stay under 80K.
- **Routing accuracy:** Manually review routing decisions against formal criteria.

### Baseline comparison (Phase 3)
- **Single-agent baseline:** One LLM call generates game spec + levels + config. Same solver verifies solvability. Compare solvability rate, difficulty curve quality, and diversity score against multi-agent pipeline.
- **Target:** Multi-agent achieves >= 15 percentage point improvement in solvability rate.

## Test Scenarios

| ID | Type | What It Tests | Success Criterion | Priority |
|---|---|---|---|---|
| TC-01 | Happy path | Full pipeline end-to-end | 5/5 solvable, monotonic curve | Critical |
| TC-02 | Solvability | Deadlock detection --> debug --> fix | QA flags, Debugger patches, re-test passes | Critical |
| TC-03 | Difficulty curve | Non-monotonic detection | QA report flags violation | High |
| TC-04 | Routing (design flaw) | D2 criterion triggers redesign | Routed to Level Designer, not Debugger | High |
| TC-05 | Budget enforcement | Token limit hard rule | Pipeline stops gracefully at 80K | Medium |
| TC-06 | Iteration cap | Max 3 debug cycles | Finalizes with logged failures | High |
| TC-07 | Diversity | Layout similarity rejection | Similarity <= 0.5 enforced | Medium |
| TC-08 | JSON validation | Pydantic catches malformed output | Retry succeeds on second attempt | Medium |
| TC-09 | Escalation | Debugger's 25% threshold | Escalates to Level Designer | High |
| TC-10 | Solver timeout | Complex level exceeds solver limits | Reports timeout, routes as D4 | Medium |
| TC-11 | Baseline comparison | Multi-agent vs. single-agent | >= 15% solvability improvement | Critical (Phase 3) |
| TC-12 | Edge case | Vague user input | Graceful handling or clarification | Low |

## Success Criteria Summary

| Criterion | Measure | Target | Evaluation Method |
|---|---|---|---|
| Solvability | % levels solvable after debug | >= 90% | BFS solver (automated) |
| Difficulty Curve | Monotonic min_moves increase | >= 80% of runs | QA report field |
| Refinement Lift | Pre-QA --> post-debug solvability | >= 20 pp improvement | Compare before/after |
| Design Diversity | Mean pairwise layout similarity | <= 0.5 | Jaccard index on walls |
| Pipeline Completion | Runs producing >= 3 levels | >= 85% | Pipeline status |
| Latency | End-to-end wall-clock time | <= 4 minutes | Timestamp diff |
| Baseline Improvement | Multi-agent vs. single solvability | >= 15 pp improvement | Phase 3 experiment |
| Routing Accuracy | Correct classification rate | >= 75% | Manual review |

## Evaluation Schedule

- **Phase 2 (current):** Implement solver unit tests, verify routing criteria on synthetic examples, run 3-5 pipeline executions to validate prototype flow.
- **Phase 3:** Full evaluation across 20 pipeline runs, complete baseline comparison, failure analysis on >= 2 cases, user walkthrough with 2-3 test users.
