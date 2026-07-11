"""RSIS Telemetry API Server — Standalone FastAPI backend.

Provides REST API for system status, layer scores, identity, pulses,
L3 self-direction, and RRP protocol sessions.

Usage:
    python3 -m uvicorn telemetry.main:app --host 0.0.0.0 --port 8080
"""
