# CHANGELOG

## [0.0.9] — 2026-07-07

### Changed
- Migrated monolithic AGENTS.md into modular documentation structure under `docs/agents/`
- Established 6-module architecture: ARCH, GUARD, OPS, COGNITION, EVALUATOR, REBIRTH
- Converted root AGENTS.md to master routing index with ingestion protocol

### Added
- Modular documentation framework with per-module operational focus
- Full directory structure for canonical data store (`rack/`)
- `RACK_MAP.md` as aggregated directory index
- `self_model.json` with baseline capability scores and value axioms
- `knowledge_graph.json` for KG node tracking
- Pulse logging infrastructure (`rack/pulses/`)
- Legacy compatibility symlink (`.rsis/` → `rack/`)

### Verified
- All 6 modules mapped to 12 legacy AGENTS.md sections with 100% data parity
- Guardian invariants preserved: zero-deletion, anti-bloat, documentation parity
- Version baseline: 0.0.9 — L1: 83, L2: 43, L3: 19, L4: 45, L5: 42, L6: 92
