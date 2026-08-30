---
name: run-game-player-research
description: Orchestrate one resumable end-to-end game-player research run across collection, cleaning, dynamic classification and sentiment, dashboard freeze, two-phase SQLite persistence, mutually exclusive single/dual event analysis, optional second-pass historical review, and optional persona simulation. Use when starting, resuming, validating, or routing a run-directory research pipeline. Do not use for one isolated cleaning, dashboard, or event-analysis task when no pipeline coordination is needed.
---

# Game Player Research Orchestrator

Use `run-manifest.json` as the only source of truth for pipeline progress. SQLite stores research evidence and completed analyses, never stage status.

## Operating order

1. Read `references/pipeline-contract.md`, `references/stage-file-contracts.md`, and `references/routing-rules.md`.
2. Locate or initialize the run manifest with `scripts/init_run.py`.
3. Inspect existing artifacts before doing work. Never rerun a completed stage when its recorded outputs still pass validation.
4. Validate inputs before execution with `scripts/validate_stage.py`; validate outputs again with `--phase after` before marking the stage complete.
5. Perform only that stage with the repository's skill, script, API, or model route.
6. Record status, executor, validation, outputs, sizes, and SHA-256 hashes with `scripts/update_manifest.py`.
7. Stop at `waiting` or `needs_review`; report the exact missing input. Resume from the manifest after handoff.

## Non-negotiable boundaries

- `analysis_mode` is exactly one of `single` or `dual`; never run both by default.
- Analyze the current event first. Historical SQLite retrieval happens only after `analysis/initial-analysis.md` exists.
- Import evidence after dashboard freeze with `python -m storage.import_run <run>`.
- Upsert final analysis only after `final-analysis.md` and `final-summary.json` exist with `python -m storage.upsert_analysis <run>`.
- Dynamic category IDs are event-local. Historical retrieval uses category names/definitions/summaries plus comment search, never a fixed cross-event category ID.
- Persona simulation is optional post-processing. Its absence or failure must not invalidate the completed core run.
- Persona simulation must receive only the event and independently confirmed facts before predictions; compare against real comments afterward.
- Public comments are biased samples. Never describe them as all players or population proportions.
- Preserve source artifacts. Write derived results beside them and record their lineage.

## Analysis route

For `single`, use the current-event event-analysis skill. For `dual`, use the blind independent and cross-questioning route. Both routes must first write `analysis/initial-analysis.md`. If historical review is enabled, build `retrieval/historical-context.json` only afterward, then write the final root-level `final-analysis.md` and `final-summary.json`.

## Completion

The core run is complete when `dashboard_result_injection` is completed. `persona_simulation` may remain `skipped` or complete later. Do not invent extra work after this point.
