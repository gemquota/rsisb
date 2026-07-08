# Module 6: Macro Evolution & The Rebirth Engine

This module establishes the lifecycle cleanup protocol, structural index pruning, and macro analytical consolidation rules.

## 6.1 The Rebirth Operational Cycle

When execution logs hit dense volume limits, the system triggers a Rebirth phase to compress runtime files and reset the operational horizon. This process moves transient history into deep storage while retaining core metrics.

```
  [60 Pulses Reached] ──► Extract Macro Behavioural Patterns & Failures
                                  │
                                  ▼
                  Consolidate Rules into KG Nodes
                                  │
                                  ▼
                  Archive Pulse Files to rack/lifecycles/*
                                  │
                                  ▼
                Reset Pulse Operational ID Counter to 001
                                  │
                                  ▼
                 Publish rack/rebirth_manifesto.json
```

## 6.2 Structural Thresholds and Triggers

The execution of a Rebirth operation is strictly bound to clear architectural boundaries:

- **Pulse Caps:** The local pulse directory contains exactly 60 completed operational files.
- **Knowledge Graph Bloat:** Total nodes within the KG scale past 800 entries while maintaining a utility efficiency density below 10%.
- **Structural Redirection:** Major architectural refactoring or core framework changes are requested.

## 6.3 Pulse 001 Bootstrapping Protocol

Following a Rebirth reset, the newly instantiated `pulse-001.json` follows an analytical path: **no automated code modifications or patch generations are allowed to execute**.

Pulse 001 is dedicated to a structured RRP alignment conversation. The operating agent must fulfill two analytical roles simultaneously:

1. **The Domain Expert Role:** Formally details current platform errors, defines the architectural goals for the new lifecycle, and establishes explicit constraint bounds.
2. **The System Evaluator Role:** Breaks down the stated goals, extracts active constraints, flags areas of architectural ambiguity, and logs the baseline directional strategy.

> **Memory Preservation Invariant:** While local pulse histories are condensed and archived during Rebirth, the underlying `self_model.json` remains completely intact. Historical capability scores, value reinforcement counts, and snapshot trajectories scale continuously across lifecycles to preserve the system's long-term memory.
