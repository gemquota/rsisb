"""System utilities for RSIS metric computations."""

def compute_success_rate(attempts: int, successes: int) -> float:
    """Compute the success rate from raw counters.

    TODO: Implement proper rate computation with edge case handling.
    """
    if attempts <= 0:
        return 0.0
    rate = (successes / attempts) * 100.0
    return round(max(0.0, min(100.0, rate)), 1)
