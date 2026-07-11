"""Compact State Encoding — ~80-120 character strings for LLM context windows.

Encodes the core RRP state into a dense, human-readable string that can
be efficiently passed in LLM context.

Format:
  v2|U3M2D3|E2C:SOFT|B:84%|A:0.22↓|C:[CON,SEC]|H:!HALT|Q:4/5|S:0.89
"""

from typing import Optional
from rrp.state_machine import RRPState


def encode_compact(state: RRPState) -> str:
    """Encode an RRPState into a ~80-120 char compact string."""
    parts = []

    # Version
    parts.append(f"v{state.rrp_version}")

    # Use case, mode, depth
    u = state.session.use_case.value
    m = state.session.execution_mode.value
    d = state.session.depth
    parts.append(f"U{u}M{m}D{d}")

    # Errors (contradictions)
    ec = len(state.contradictions)
    if ec > 0:
        # Show top constraint conflict
        c = state.contradictions[0]
        parts.append(f"E{ec}C:{c.constraint_a[:4]}/{c.constraint_b[:4]}")
    else:
        parts.append("E0")

    # Budget saturation
    sat = state.telemetry.token_budget.saturation_percent()
    parts.append(f"B:{int(sat)}%")

    # Ambiguity average + trend
    avg = state.ambiguity.average()
    trend = _ambiguity_trend(state)
    parts.append(f"A:{avg:.2f}{trend}")

    # Topic coverage
    covered = state.telemetry.topic_coverage.covered_topics()
    if covered:
        code = ",".join(t[:3] for t in covered)
        parts.append(f"C:[{code}]")
    else:
        parts.append("C:[]")

    # Status
    status_map = {"initialized": "!INIT", "active": "!ACT", "completed": "!DONE",
                  "early_term": "!ET", "halted": "!HALT"}
    parts.append(status_map.get(state.status, f"!{state.status.upper()}"))

    # Round progress
    parts.append(f"Q:{state.current_round}/{state.session.max_rounds}")

    # Confidence (average of last decisions)
    if state.decisions:
        avg_conf = sum(d.confidence for d in state.decisions) / len(state.decisions)
        parts.append(f"S:{avg_conf:.2f}")
    else:
        parts.append("S:0.00")

    result = "|".join(parts)
    # Enforce length
    if len(result) > 130:
        result = result[:127] + "..."
    return result


def decode_compact(encoded: str) -> dict:
    """Decode a compact state string into a dictionary of values."""
    result = {}
    segments = encoded.split("|")
    for seg in segments:
        seg = seg.strip()
        if seg.startswith("v"):
            result["version"] = seg[1:]
        elif seg.startswith("U") and "M" in seg and "D" in seg:
            import re
            m = re.match(r"U(\d+)M(\d+)D(\d+)", seg)
            if m:
                result["use_case"] = int(m.group(1))
                result["execution_mode"] = int(m.group(2))
                result["depth"] = int(m.group(3))
        elif seg.startswith("E"):
            if "C:" in seg:
                e_part, c_part = seg.split("C:", 1)
                result["contradictions"] = int(e_part[1:]) if e_part[1:].isdigit() else 0
                result["conflict"] = c_part
            else:
                result["contradictions"] = int(seg[1:]) if seg[1:].isdigit() else 0
        elif seg.startswith("B:"):
            result["budget_saturation"] = seg[2:]
        elif seg.startswith("A:"):
            a_part = seg[2:]
            trend = "→"
            if a_part.endswith("↑"):
                trend = "↑"
                a_part = a_part[:-1]
            elif a_part.endswith("↓"):
                trend = "↓"
                a_part = a_part[:-1]
            elif a_part.endswith("→"):
                trend = "→"
                a_part = a_part[:-1]
            try:
                result["ambiguity_avg"] = float(a_part)
            except ValueError:
                result["ambiguity_avg"] = 0.0
            result["ambiguity_trend"] = trend
        elif seg.startswith("C:["):
            topics = seg[2:].strip("[]")
            result["topics_covered"] = [t.strip() for t in topics.split(",")] if topics else []
        elif seg.startswith("!"):
            status_map = {"INIT": "initialized", "ACT": "active", "DONE": "completed",
                         "ET": "early_term", "HALT": "halted"}
            result["status"] = status_map.get(seg[1:], seg[1:].lower())
        elif seg.startswith("Q:"):
            parts = seg[2:].split("/")
            try:
                result["round"] = int(parts[0])
                result["max_rounds"] = int(parts[1]) if len(parts) > 1 else 0
            except ValueError:
                pass
        elif seg.startswith("S:"):
            try:
                result["confidence"] = float(seg[2:])
            except ValueError:
                result["confidence"] = 0.0
    return result


def _ambiguity_trend(state: RRPState) -> str:
    """Determine ambiguity trend from history (↑, ↓, →)."""
    if len(state.ambiguity_history) < 2:
        return "→"
    recent = state.ambiguity_history[-2:]
    avg_current = sum(recent[-1]["ambiguity"].values()) / 4 if isinstance(recent[-1].get("ambiguity"), dict) else 0
    avg_prev = sum(recent[0]["ambiguity"].values()) / 4 if isinstance(recent[0].get("ambiguity"), dict) else 0
    diff = avg_prev - avg_current
    if diff > 0.05:
        return "↓"  # Ambiguity decreasing = good
    elif diff < -0.05:
        return "↑"  # Ambiguity increasing = bad
    return "→"
