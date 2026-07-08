# RSIS — AGENTS.md (Master Index)

This file governs agentic interaction within the RSIS project root. It applies to all files in this directory and any subdirectories. Direct user instructions take precedence where conflicts exist.

⚠️ **CRITICAL ARCHITECTURAL UPDATE:** This documentation has been decentralized into modular segments located within `docs/agents/` to prevent LLM context bloating and maximize parsing efficiency.

---

## 1. Modular Knowledge Rack Index

Agents must read and ingest these modular files sequentially based on their active task phase:

- **Module 1: Architecture Blueprint & System Topography (`docs/agents/01_ARCH.md`)**
  - Defines the repository architecture, file maps, and virtual layer stacks (L1 to L9).
- **Module 2: The Guardian Protocol & Structural Invariants (`docs/agents/02_GUARD.md`)**
  - Enforces untouchable state directives, code duplication prevention, and semantic versioning rules.
- **Module 3: Pipeline Operations & Lifecycle Execution (`docs/agents/03_OPS.md`)**
  - Maps out execution flows of L4/L2 cycles, AST stub replacement mechanics, and test workflows.
- **Module 4: Cognitive Core: Self-Modeling & Value Axioms (`docs/agents/04_COGNITION.md`)**
  - Governs capability score formulas, crisis thresholds, identity snapshots, and the 9 core value axioms.
- **Module 5: The Oracle Protocol: Manual Evaluation & Telemetry (`docs/agents/05_EVALUATOR.md`)**
  - Operating manual for running manual evaluation cycles and structured 4-phase reasoning pulse logs.
- **Module 6: Macro Evolution & The Rebirth Engine (`docs/agents/06_REBIRTH.md`)**
  - Outlines lifecycle rotation protocols, memory consolidation strategies, and pattern extraction.

---

## 2. Core Operational Commitments

- **Immutable State Protections:** Never delete, clear, or modify `rack/` or `.rsis/` directories.
- **Surgical Diffs Only:** Codegen templates must output targeted structural modifications, never wrap full files.
- **Test Suite Absolutism:** All 388 unit tests must pass cleanly before any code change can be finalized.
- **Manual Oracle Mode:** The system currently operates in `mode="local"`; agents must perform manual LLM evaluations.

*For detailed technical context, terminal commands, or runtime telemetry data, proceed directly to the corresponding module in `docs/agents/`.*

---

## 3. Runtime Agent Ingestion Protocol

When an LLM agent boots into the RSIS repository root to execute a new cycle, it should follow this systematic intake procedure:

```
[Agent Initial Boot]
        │
        ▼
Read Root AGENTS.md ──► [Parses Master Index & Primary Guardrails]
        │
        ▼
Scan System Telemetry ──► Read rack/pulses/latest.json
        │
        ▼
Select Module Track
        ├── Goal/Fix Assignment  ──► Ingest docs/agents/01_ARCH.md & 03_OPS.md
        ├── Scoring & Value Edits ──► Ingest docs/agents/04_COGNITION.md
        └── Evaluation Step      ──► Ingest docs/agents/05_EVALUATOR.md
```

1. **Context Loading:** The agent initializes by parsing the root AGENTS.md directory index to instantly absorb high-level operational restrictions.
2. **Telemetry Sync:** The agent queries `rack/pulses/latest.json` to calculate the real-time status of the current system baseline (e.g., confirming version 0.0.9, verifying the current 7.5% success rate, and scanning the active layer weights).
3. **Targeted Module Loading:** Rather than wasting thousands of context tokens loading all architectural maps, memory consolidation policies, and scoring metrics simultaneously, the agent only reads the specific module file relevant to its immediate lifecycle stage.

The modular architecture conversion is complete. The system is structurally optimized for the next evolutionary pulse sequence.
