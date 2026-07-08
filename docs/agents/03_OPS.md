# Module 3: Pipeline Operations & Execution Workflows

This module provides the functional runtime manual for executing improvement cycles, processing objectives through the state machine, and verifying repository health.

## 3.1 The Integrated Optimization Loop

The interaction between the macro planning engine (L4) and individual execution sessions (L2) runs according to a deterministic execution chain.

```
[L4 Cycle Inception] ────► Gather Signals (Stubs, Failures, Regressions)
                                 │
                                 ▼
                           Generate Goals (Max 30 targets per run)
                                 │
                                 ▼
                     [L2 Session Execution]
                     ├── 1. Analyze Context & AST Architecture
                     ├── 2. Render Template via CodeGen Engine
                     ├── 3. Execute Two-Tier Evaluation Checklist
                     └── 4. On Pass ──► Git Apply ──► Pytest Verification
```

## 3.2 The Lifecycle State Machine

Every task processing through the system transitions through a strict state architecture protected by structural guards.

```
  ┌──────────┐      ┌──────────┐      ┌───────────┐      ┌───────────┐
  │ PROPOSED ├─────►│  QUEUED  ├─────►│ EXECUTING ├─────►│ COMPLETED │
  └──────────┘      └────┬─────┘      └─────┬─────┘      └─────┬─────┘
                         ▲                  │                  │
                         │             (On Failure)            ▼
                         │                  │             ┌───────────┐
                         └─── Retry Limit ──┴────────────►│ ARCHIVED  │
                                                          └───────────┘
```

- **Task Retention Guardrails:** Tasks are configured with a maximum allocation of 3 execution attempts.
- **Eviction Protocols:** If the priority queue fills to maximum capacity, lower-ranked tasks are automatically evicted and given an ARCHIVED status flag to preserve memory efficiency.

## 3.3 Templates & Codegen

The system uses Jinja2-based templates for stub replacement. Available templates include:

| Template | Target Pattern | Output |
|---|---|---|
| `fix_stub.j2` | `pass`, `...`, `raise NotImplementedError` | Full function implementation |
| `add_method.j2` | Class body | New method injection |
| `patch_import.j2` | Module header | Missing import insertion |

## 3.4 Test-Driven Development Protocols

The test environment represents the ultimate verification of system changes. No change is accepted into the main code base without complete validation from the test runner.

```bash
# Execute global verification run (All 388 tests must pass cleanly)
python3 -m pytest tests/ -q

# Execute isolated target file checks with immediate short stack traces
python3 -m pytest tests/test_codegen.py -q --tb=short

# Target an isolated test matrix block for granular verification
python3 -m pytest tests/test_core.py::TestMemoryManager::test_record_improvement -q --tb=short
```

> **Rollback Policy:** If any test fails following a file mutation step, the RecoveryManager executes an immediate rollback using `git checkout` to return the project state to the last verified commit milestone. No code adjustments may persist in a broken environment state.
