# Module 4: Cognitive Core: Self-Modeling & Value Axioms

This module governs the internal metrics, self-perception algorithms, and axiomatic values that guide goal selection and determine systemic health.

## 4.1 Capability Score Arithmetic

The system maintains real-time capability scores ranging from 0 to 100 for all layers within `self_model.json`. Every successful execution or optimization cycle triggers an incremental update to its respective capability score according to specific linear rewards.

For deeper macro updates, the system invokes `compute_all_scores()`, which derives layer scores via a weighted average of individual architectural metrics:

| Layer | Aggregate Metric Derivation Components | Weight Distribution |
|---|---|---|
| **L1** | execution_reliability, failure_recovery, pipeline_activity, crisis_immunity | 30 / 25 / 25 / 20 |
| **L2** | goal_analysis, step_planning, apply_success_rate, stub_resolution, test_stability, iteration_efficiency, pipeline_throughput | 15 / 15 / 20 / 15 / 15 / 10 / 10 |
| **L3** | signal_coverage, goal_generation, goal_execution, goal_diversity, queue_health | 25 / 20 / 25 / 15 / 15 |
| **L4** | parameter_tuning, experimentation, kg_utilization, optimization_depth, learning_maturity | 20 / 20 / 20 / 20 / 20 |
| **L5** | pattern_detection, strategy_evolution, insight_utilization, redundancy_detection, kg_growth | 25 / 25 / 20 / 15 / 15 |
| **L6** | value_definition, value_adherence, value_reinforcement, identity_stability, self_knowledge | 20 / 25 / 20 / 20 / 15 |

## 4.2 Core Value Axioms & Prioritization Penalties

The system judges all proposed goals against 9 fundamental value axioms. Every milestone achieved that aligns with a specific axiom increments its `reinforced_count`, amplifying its long-term weight in the priority calculation:

- **robustness**: Prioritizes test coverage expansion, defensive code architectures, and structured error handling.
- **coherence**: Favors mutations that structurally match current code conventions and project paradigms.
- **efficiency**: Prefers low-overhead solutions, optimized algorithm implementations, and low resource cost.
- **maintainability**: Drives code clarity, structural simplification, documentation updates, and clean abstractions.
- **autonomy**: Incentivizes changes that mitigate dependencies on manual human intervention or external review steps.
- **identity**: Enhances the precision, retrieval capabilities, and update execution speed of the self-model.
- **learning**: Selects actions that gather rich training/telemetry data to optimize future refinement cycles.
- **stability**: Protects core regression safety bounds, ensuring legacy behaviors do not degrade.
- **growth**: Maximizes system scope, expanding the capability surface area and operational boundaries.

> **Prioritizer Enforcement:** Goals determined to conflict with heavily reinforced value criteria are automatically penalized via `Prioritizer.apply_values_penalty()`, dropping their rank in the active queue.

## 4.3 Crisis Detection & Identity Stability

An automated health routine continuously evaluates operational trends to ensure systemic stability. An identity crisis is declared when any of the following boundaries are breached:

Upon triggering a crisis state, the system executes defensive recovery behaviors:
1. It instantly halts all non-critical or volatile optimization processes.
2. It broadcasts a high-priority human operator warning to the terminal logs.
3. It freezes execution until an explicit manual or recovery resolution command is passed: `sm.resolve_crisis("...")`.

## 4.4 Snapshots

IdentitySnapshot records capture the system's self-model at a point in time. Each snapshot preserves all 9 layer capability scores, value axiom reinforcement counts, and KG node metadata. Snapshots are stored in `rack/L6/` and indexed by timestamp.
