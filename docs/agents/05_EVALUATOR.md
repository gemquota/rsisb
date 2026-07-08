# Module 5: The Oracle Protocol: Manual Evaluation & Telemetry

This module functions as the mandatory operating directive for running evaluation cycles, structuring manual inference inputs, and formatting pulse logs.

## 5.1 Manual LLM Evaluator Requirement

Because EvaluatorClient runs in `mode="local"` and the core AI evaluation logic within `evaluator/evaluator.py` is an unmapped placeholder stub, the system cannot execute automated external API checks. Consequently, **the operating agent must step into the loop and manually act as the LLM Evaluator during every validation pass**.

When an optimization script executes an evaluation cycle, you must manually inspect the context, verify constraints, and render a rigid 4-phase reasoning report:

```json
{
  "phase": "goal_analysis",
  "reasoning": "Examine target functions, adjacent modules, and structural intent within the file.",
  "conclusion": "Clear baseline understanding of structural dependencies and code requirements."
}
{
  "phase": "constraint_extraction",
  "reasoning": "Identify explicit RRP rule matches. Map out requirements like error handling or type definitions.",
  "constraints": {"error_handling": "LOCKED", "type_safety": "REQUIRED"}
}
{
  "phase": "ambiguity_assessment",
  "reasoning": "Isolate unmapped behaviors, structural gaps, or missing variable inputs.",
  "ambiguity": {"requirements": 0.1, "data_model": 0.0}
}
{
  "phase": "evaluation",
  "reasoning": "Final synthesis of changes against test expectations and architectural principles.",
  "decision": "PASS",
  "confidence": 0.95,
  "suggestion": "Proceed with patch application; track downstream test suite behavior."
}
```

Valid evaluation decision outputs are restricted to: **PASS**, **DISMISS**, or **HOLD**.

## 5.2 Pulse Logging and Context State

Every distinct processing iteration must generate a sequential telemetry log file matching the path pattern `rack/pulses/pulse-NNN.json`. A precise duplicate or symbolic link must simultaneously overwrite `rack/pulses/latest.json` to maintain a single-file pointer for system processes.

The current system tracking baseline as of **2026-07-07** is captured below:

```
System Version Baseline: 0.0.9
Accumulated Metrics:    120 Total Attempts, 9 Successful Applications (7.5% Success Rate)
Identity Trackers:      48 Snapshots, 800 Raw KG Nodes (7 Consolidated / Useful Nodes)
Active Layer Metrics:
  - L1 (Execution):     83/100  (Pipeline Activity: 100, Execution Reliability: 45)
  - L2 (Planning):      43/100  (Test Stability: 90, Apply Success Rate: 26)
  - L3 (Self-Direct):   19/100  (Signal Coverage: 1, Queue Health: 15)
  - L4 (Evolution):     45/100  (Strategy Evolution: 100, Insight Utilization: 0)
  - L5 (Optimizer):     42/100  (Experimentation: 100, Parameter Tuning: 20)
  - L6 (Identity):      92/100  (Value Adherence: 100, Self Knowledge: 70)
```

Critical optimization targets include fixing `signal_coverage` (1.2 / 100) and `insight_utilization` (0.0 / 100), where the system currently fails to detect incoming file changes or leverage knowledge graph data.
