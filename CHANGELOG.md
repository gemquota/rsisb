# CHANGELOG

## [0.0.9] — 2026-07-11

### Added (Cycle 3)
- **RRP Protocol Engine** — Full Recursive Refinement Protocol deployment:
  - `rrp/state_machine.py` — Deterministic RRPState with 4D ambiguity tracking, constraint locking, decision capture, contradiction detection, checkpoints/fork/rollback, and Telemetry v2.0 (TokenBudget, QuestionQualityIndex, SatisfactionDelta, TemporalVelocity, 8-bit TopicCoverage, TransactionLedger)
  - `rrp/protocol.py` — RRPEngine with process_user_input(), apply_semantic_ambiguity_json(), add_decision(), early_termination v2.1
  - `rrp/compact.py` — ~60-80 char state encoding for LLM context windows (e.g., `v2.1|U4M1D3|E0|B:0%|A:0.25→|C:[ARC,SEC,DAT,SCA,TES]|!ACT|Q:1/6|S:0.90`)
  - `rrp/persistence.py` — Atomic JSON session snapshots with isolation
  - `rrp/cli.py` — Full CLI: init, call (process-input, rate-ambiguity, add-decision, check-termination), list, show, delete
  - **6 use cases**: Alignment, Ideation, Convergence, Stress Testing, Data Mapping, Determinism
  - **3 execution modes**: Hybrid, Batch, Pulse
  - **3 depth levels**: Shallow, Standard, Deep
- **7 RRP API routes** — Init, process, ambiguity, decision, state, compact, sessions list. Total: 36 routes.

### Integrated
- RRP session `rsis_refine` initialized with 3 commitment decisions encoding core RSIS invariants (zero-deletion, AST diffs, 4-phase evaluation)
- 3 value axioms reinforced (stability, identity, robustness)
- L6 metrics updated: value_reinforcement (50), identity_stability (60)

### Verified
- 70 pytest tests passing across 6 test modules (evaluator, codegen, state_machine, recovery, l3_self_direction, rrp)
- 4 identity snapshots captured across all build cycles
- 4 pulse logs with full cycle metadata
- All 36 API routes verified operational

## Prior history

See previous cycles:
- **Cycle 2**: L3 Self-Direction loop, identity core expansion, crisis resolution
- **Cycle 1**: evaluator, codegen, state machine, recovery manager, telemetry API, frontend portal, L2 cycle
- **Cycle 0**: Scaffold, modular docs, rack/, pulse-001 RRP alignment
