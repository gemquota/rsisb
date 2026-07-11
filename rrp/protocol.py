"""RRP Protocol Engine — Command dispatch and user input processing.

Wraps RRPState with high-level operations: process_user_input(),
apply_semantic_ambiguity_json(), check_early_termination(), etc.
"""

import re
import math
from typing import Optional

from rrp.state_machine import (
    RRPState, AmbiguityVector, Decision, DecisionType,
    UseCase, ExecutionMode, TopicCoverage,
)


class RRPEngine:
    """High-level protocol operations wrapping RRPState."""

    def __init__(self, state: Optional[RRPState] = None):
        self.state = state or RRPState()

    def init_session(self, session_id: str = "default",
                     use_case: int = 1, mode: int = 1,
                     max_rounds: int = 5, depth: int = 2,
                     questions_per_round: int = 3,
                     mcq_options: int = 3) -> 'RRPEngine':
        """Initialize a new RRP session."""
        self.state = RRPState(
            session=RRPState.__dataclass_fields__["session"].type(
                session_id=session_id,
                use_case=UseCase(use_case),
                execution_mode=ExecutionMode(mode),
                max_rounds=max_rounds,
                depth=depth,
                open_questions_per_round=questions_per_round,
                mcq_options_per_question=mcq_options,
            ),
            status="initialized",
            rrp_version="2.1",
        )
        self.state.telemetry.velocity.start_time = __import__("time").time()
        return self

    def process_user_input(self, text: str, source: str = "user") -> dict:
        """Process user input: extract constraints, detect contradictions, update state.

        Returns a processing result dict with extracted data.
        """
        self.state.next_round()
        self.state.round_inputs.append(text)
        result = {
            "round": self.state.current_round,
            "extracted_constraints": [],
            "detected_contradictions": 0,
            "topics_covered": [],
        }

        # Extract constraints using pattern matching
        constraint_patterns = [
            (r"(?:must|shall|should|need to|required to|have to)\s+(\w+)\s+(\S+)", 1, 2),
            (r"(?:no |not |never |without )\s*(\w+)", 1, "prohibited"),
            (r"(?:use|using|with)\s+(\w+)(?:\s+(?:for|as|to))?\s+(\w+)", 1, 2),
            (r"(?:in|on|at)\s+(\w+)\s+(\w+)", 1, 2),
        ]

        for pattern, key_group, val_group in constraint_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                key = match[key_group - 1] if isinstance(match, tuple) else match
                val = match[val_group - 1] if isinstance(match, tuple) else val_group
                if isinstance(val, str) and val == "prohibited":
                    val = f"no_{key}"
                self.state.add_constraint(key.lower(), str(val).lower(), source=source)
                result["extracted_constraints"].append(f"{key.lower()}={str(val).lower()}")

        result["detected_contradictions"] = len(self.state.contradictions)

        # Detect topic coverage from keywords
        topic_keywords = {
            "ARCH": r"architect(ure|ural)?|structure|layout|component|module|layer|api|endpoint|route|service",
            "SEC": r"secur(e|ity)?|auth|permission|encrypt|vulnerab|token|secret|password",
            "DATA": r"data|database|schema|model|entity|storage|persist|table|record",
            "PERF": r"perfor|speed|latency|throughput|optimize|fast|slow|cache",
            "SCAL": r"scalab|scale|load|concurr|distribut|horizont|vert",
            "TEST": r"test|assert|mock|coverage|verif|valid|spec",
            "DEPL": r"deploy|release|ci|cd|pipeline|container|env|docker|kubernet",
            "UX": r"ux|ui|user|interface|experien|frontend|dashboard|design",
        }
        for topic, pattern in topic_keywords.items():
            if re.search(pattern, text, re.IGNORECASE):
                self.state.telemetry.topic_coverage.set_topic(topic)
                result["topics_covered"].append(topic)

        # Check if max rounds reached
        if self.state.current_round >= self.state.session.max_rounds:
            self.state.status = "completed"

        self.state.auto_compile_summary()
        return result

    def apply_semantic_ambiguity_json(self, requirements: Optional[float] = None,
                                       data_model: Optional[float] = None,
                                       edge_case: Optional[float] = None,
                                       determinism: Optional[float] = None,
                                       text_density: Optional[str] = None) -> 'RRPEngine':
        """Hybrid calibration: semantic JSON values with NLP density fallback."""
        self.state.set_ambiguity(
            requirements=requirements,
            data_model=data_model,
            edge_case=edge_case,
            determinism=determinism,
        )

        # NLP density fallback for any unset dimensions
        if text_density and all(v is None for v in [requirements, data_model, edge_case, determinism]):
            words = text_density.split()
            num_words = len(words)
            unique_ratio = len(set(w.lower() for w in words)) / max(num_words, 1)
            density = max(0.0, min(1.0, 1.0 - unique_ratio))
            self.state.set_ambiguity(
                requirements=density,
                data_model=density,
                edge_case=density,
                determinism=density,
            )

        return self

    def add_decision(self, decision_type: str, description: str,
                     reasoning: str = "", confidence: float = 0.8) -> 'RRPEngine':
        """Record a decision by type name."""
        try:
            dt = DecisionType(decision_type)
        except ValueError:
            dt = DecisionType.CLARIFICATION
        self.state.add_decision(dt, description, reasoning, confidence)
        return self

    def set_satisfaction(self, delta: float) -> 'RRPEngine':
        """Record user satisfaction delta."""
        self.state.telemetry.satisfaction.cumulative += delta
        self.state.telemetry.satisfaction.deltas.append(delta)
        return self

    def log_transaction(self, action: str, detail: str = "") -> 'RRPEngine':
        """Append to the immutable transaction ledger."""
        self.state.telemetry.transaction_ledger.append({
            "round": self.state.current_round,
            "action": action,
            "detail": detail,
            "timestamp": __import__("time").time(),
        })
        return self

    def check_early_termination(self) -> bool:
        """Delegate to state's early termination logic."""
        return self.state.check_early_termination()

    def get_state_dict(self) -> dict:
        """Return serializable state dict."""
        return self.state.to_dict()
