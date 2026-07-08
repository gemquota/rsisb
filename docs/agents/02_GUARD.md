# Module 2: The Guardian Protocol & Structural Invariants

This module governs the immutable constraints of RSIS. Security, versioning stability, and structural integrity take absolute priority over localized optimization gains.

## 2.1 State Conservation & Integrity Guardrails

The state stored within `rack/` represents the long-term memory and self-conception of RSIS. Accidental deletion or mutation of these directories triggers catastrophic identity loss.

- **Zero-Deletion Directive:** Under no circumstances are agents permitted to run destructive operations (such as `rm -rf`) on `rack/`, `.rsis/`, or any nested files.
- **Volatile Cache Exclusions:** Unlike build artifacts, compiled files, or temporary testing directories, the state engines must never be included in global clean-up tasks.
- **Bypassing Prohibition:** Changes must pass through the evaluation and telemetry pipeline. Direct modification of `self_model.json` to alter capability scores without completing real improvement cycles is treated as an active anomaly.

## 2.2 The Anti-Bloat Code Generation Standard

To avoid historical code expansion bugs — such as wrapping entire modules inside docstrings or duplicating active class structures — all code generation must follow a strict surgical replacement standard.

```
┌────────────────────────────────────────────────────────┐
│                   Original File AST                    │
│   ┌───────────────┐ ┌───────────────┐ ┌────────────┐   │
│   │ Function A    │ │ Stub Function │ │ Function B │   │
│   └───────────────┘ └───────┬───────┘ └────────────┘   │
└─────────────────────────────┼──────────────────────────┘
                              │
                    AST Target Matching
                              │
                              ▼
┌────────────────────────────────────────────────────────┐
│                   Targeted Diff Only                   │
│                     ┌───────────────┐                  │
│                     │ Implemented   │                  │
│                     │ Function Code │                  │
│                     └───────────────┘                  │
└────────────────────────────────────────────────────────┘
```

- **Template Constraints:** The `fix_stub.j2` engine is restricted to processing the target block. It must output exactly `{{ original_code }}` with AST replacements injected, completely avoiding global file wrappers.
- **AST Integrity:** Prior to generating patch files, the generation engine must execute an AST parse on the destination script to isolate the code coordinates of stubs (`pass`, `...`, `raise NotImplementedError`, or empty placeholder returns).

## 2.3 Version Evolution & Documentation Parity

System progression is strictly bound to semantic versioning patterns and complete documentation updates.

- **Patch Increments (0.0.Z):** Automatically performed upon every successful, verified execution cycle.
- **Minor Changes (0.Y.0):** Requires explicit, structural verification and direct confirmation from the user.
- **Major Milestone (X.0.0):** Reserved entirely for complete development sign-off.
- **Documentation Parity Rule:** Code changes are fundamentally incomplete without simultaneous updates to relevant module notes, docstrings, and a correctly structured entry in CHANGELOG.md detailing **Added**, **Changed**, **Fixed**, or **Verified** attributes.
