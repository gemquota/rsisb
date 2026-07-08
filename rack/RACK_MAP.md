# RACK_MAP.md — Canonical Data Store Directory Index

This file serves as the aggregated directory index and subrack map for the RSIS canonical data store.

## Directory Layout

```
rack/
├── RACK_MAP.md                # This file — directory index
├── L1/                        # Execution Loop telemetry
├── L2/                        # Planning Loop telemetry
├── L3/                        # Self-Direction Loop telemetry
├── L4/                        # Optimizer Loop telemetry
├── L5/                        # Evolution Loop telemetry
├── L6/                        # Identity Layer telemetry
├── shared/                    # Matrix variables & shared system memory
│   ├── self_model.json        # Capability scores & value axioms
│   └── knowledge_graph.json   # KG nodes & relationships
├── project/                   # Standalone non-loop operational metadata
├── archive/                   # Cold storage for deprecated/superseded logic
├── pulses/                    # Sequential pulse operation logs
│   ├── latest.json            # Current system telemetry snapshot
│   └── pulse-NNN.json         # Individual pulse records
└── lifecycles/                # Archived pulse files from Rebirth cycles
```

## Subrack Maps

| Subrack | Contents | Retention Policy |
|---|---|---|
| `L1/` | Execution reliability, failure recovery, pipeline activity metrics | Perpetual |
| `L2/` | Goal analysis, step planning, apply success, stub resolution logs | Perpetual |
| `L3/` | Signal coverage, goal generation, queue health metrics | Perpetual |
| `L4/` | Parameter tuning, experimentation, optimization depth records | Perpetual |
| `L5/` | Pattern detection, strategy evolution, kg growth traces | Perpetual |
| `L6/` | Identity snapshots, value reinforcement, crisis logs | Perpetual |
| `shared/` | Cross-layer matrix variables and system memory | Perpetual |
| `project/` | Non-loop operational metadata | Perpetual |
| `archive/` | Deprecated or superseded logic | Indefinite cold storage |
| `pulses/` | Active pulse operation logs | Until next Rebirth |
| `lifecycles/` | Archived pre-Rebirth pulse sets | Permanent archive |

## System Invariant

The legacy `.rsis/` directory exists only as a logical symlink pointing directly into `rack/`. No state is ever stored outside `rack/`.
