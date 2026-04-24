# PuzzleForge -- Evaluation Plan

## Overview

This evaluation plan defines 12 scenario tests covering the core pipeline, failure handling, governance enforcement, final artifacts, and edge mechanics. The baseline comparison is recorded separately in `evaluation_results.csv` and `baseline_results.json`.

## Evaluation Methodology

### Automated evaluation (QA Tester agent)
- **Solvability:** BFS solver provides ground-truth pass/fail per level.
- **Difficulty-rating curve:** Computed from the QA difficulty_rating sequence; checked for monotonicity.
- **Diversity:** Pairwise Jaccard similarity on wall positions; threshold <= 0.5.
- **Refinement lift:** Compare solvability before and after debug cycles.

### Pipeline-level evaluation
- **Terminal output rate:** Percentage of runs reaching a terminal pipeline status with saved trace, design document, and artifact files.
- **Latency:** Wall-clock time from concept to final game.
- **Token budget compliance:** Total tokens must stay under 80K.
- **Routing accuracy:** Manually review routing decisions against formal criteria.

### Baseline comparison (Phase 3)
- **Single-agent baseline:** One LLM call generates game spec + levels + config. Same solver verifies solvability. Compare solvability rate, difficulty curve quality, and diversity score against multi-agent pipeline.
- **Target:** Multi-agent achieves >= 15 percentage point improvement in solvability rate.
- **Interpretation:** The baseline is a diagnostic comparison for architecture value, not a controlled benchmark. The key question is whether solver-backed verification and repair improve the harder cases that a single LLM cannot reliably self-check.

## Test Scenarios

| ID | Type | What It Tests | Success Criterion | Priority |
|---|---|---|---|---|
| TC-01 | Happy path | Full pipeline end-to-end | 5/5 solvable, monotonic curve | Critical |
| TC-02 | Solvability | Deadlock detection --> debug --> fix | QA flags, Debugger patches, re-test passes | Critical |
| TC-03 | Difficulty curve | Non-monotonic detection | QA report flags violation | High |
| TC-04 | Routing (design flaw) | D2 criterion triggers redesign | Routed to Level Designer, not Debugger | High |
| TC-05 | Live debug loop | QA failures route through Developer and Debugger | Re-test improves or logs bounded failure | Critical |
| TC-06 | Soft diversity | Solvable levels with one diversity issue | Accepts after one attempted fix | Medium |
| TC-07 | Diversity | Layout similarity rejection | Similarity <= 0.5 enforced | Medium |
| TC-08 | JSON validation | Pydantic catches malformed output | Retry or terminal failure is explicit | Medium |
| TC-09 | Escalation | Debugger's 25% threshold | Escalates to Level Designer | High |
| TC-10 | Solver timeout | Complex level exceeds solver limits | Reports timeout, routes as D4 | Medium |
| TC-11 | Final artifacts | Bundled push and slide demo games | Both demos have 5 solver-verified levels and move limits | Critical |
| TC-12 | Edge slide concept | Slide concept selects slide mechanic | Correct mechanic and slide solver path | High |

## Success Criteria Summary

| Criterion | Measure | Target | Evaluation Method |
|---|---|---|---|
| Overall Solvability | % levels solvable after debug | >= 80% acceptance; >= 90% stretch | BFS solver (automated) |
| Mechanic-Specific Solvability | Push and slide rates reported separately | Diagnostic, used to identify gaps | BFS solver grouped by mechanic |
| Difficulty-Rating Curve | Monotonic QA difficulty_rating increase | >= 80% of runs | QA report field |
| Refinement Lift | Solvability before vs. after debug cycles | >= 20 pp improvement | Compare before/after |
| Design Diversity | Mean pairwise layout similarity | <= 0.5 | Jaccard index on walls |
| Terminal Output Rate | Runs reaching a terminal status with saved artifacts | >= 85% | Pipeline status and output files |
| Latency | End-to-end wall-clock time | <= 4 minutes | Timestamp diff |
| Baseline Improvement | Multi-agent vs. single solvability | >= 15 pp improvement | Phase 3 experiment |
| Routing Accuracy | Correct classification rate | >= 75% | Manual review |

## Evaluation Schedule

- **Phase 2:** Implement solver unit tests, verify routing criteria on synthetic examples, run 3-5 pipeline executions to validate prototype flow.
- **Phase 3:** Execute representative live runs across push and slide concepts, complete baseline comparison, document at least 2 failure cases, and preserve traces or outputs for each run.
