"""RRP CLI — Command-line interface for RRP session management.

Usage:
  python3 rrp/cli.py init --id my_session --u 4 --m 1 --z 5 --depth 3
  python3 rrp/cli.py call process-input text="My problem..."
  python3 rrp/cli.py call rate-ambiguity requirements=0.3 data-model=0.2
  python3 rrp/cli.py call next-round
  python3 rrp/cli.py list
  python3 rrp/cli.py show
"""

import argparse
import json
import sys
import shlex
from pathlib import Path

from rrp.state_machine import UseCase
from rrp.protocol import RRPEngine
from rrp.persistence import RRPPersistence
from rrp.compact import encode_compact

PERSISTENCE = RRPPersistence()


def cmd_init(args):
    engine = RRPEngine().init_session(
        session_id=args.id,
        use_case=args.u,
        mode=args.m,
        max_rounds=args.z,
        depth=args.depth,
        questions_per_round=args.x or 3,
        mcq_options=args.y or 3,
    )
    PERSISTENCE.save(engine)
    print(f"Session '{args.id}' initialized (U{args.u} M{args.m} Z{args.z} D{args.depth})")
    print(f"  Compact: {encode_compact(engine.state)}")


def cmd_call(args):
    engine = PERSISTENCE.load(args.id)
    if not engine:
        print(f"Session '{args.id}' not found. Use 'init' first.")
        sys.exit(1)

    command = args.command
    kwargs = {}
    if args.args:
        for arg in args.args:
            if "=" in arg:
                k, v = arg.split("=", 1)
                # Try to parse as number
                try:
                    v = float(v) if "." in v else int(v)
                except ValueError:
                    pass
                kwargs[k] = v

    result = None
    if command == "process-input":
        text = kwargs.get("text", "")
        result = engine.process_user_input(text)

    elif command == "rate-ambiguity":
        engine.apply_semantic_ambiguity_json(
            requirements=kwargs.get("requirements"),
            data_model=kwargs.get("data_model"),
            edge_case=kwargs.get("edge_case"),
            determinism=kwargs.get("determinism"),
        )
        result = {"ambiguity": engine.state.ambiguity.to_dict()}

    elif command == "next-round":
        engine.state.next_round()
        result = {"round": engine.state.current_round}

    elif command == "add-decision":
        engine.add_decision(
            decision_type=kwargs.get("type", "clarification"),
            description=kwargs.get("description", ""),
            reasoning=kwargs.get("reasoning", ""),
        )
        result = {"decisions": len(engine.state.decisions)}

    elif command == "add-constraint":
        engine.state.add_constraint(
            key=kwargs.get("key", ""),
            value=kwargs.get("value", ""),
        )
        result = {"constraints": len(engine.state.constraints)}

    elif command == "check-termination":
        result = {"should_terminate": engine.check_early_termination()}

    elif command == "compact":
        result = {"compact": encode_compact(engine.state)}

    elif command == "summary":
        result = {"summary": engine.state.auto_compile_summary()}

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

    PERSISTENCE.save(engine)
    if result:
        print(json.dumps(result, indent=2))


def cmd_list(args):
    sessions = PERSISTENCE.list_sessions()
    if not sessions:
        print("No sessions found.")
        return
    print(f"{'ID':<20} {'Status':<12} {'Rounds':<8} {'U':<4} {'Dec':<5} {'Con':<5} {'Amb':<6}")
    print("-" * 65)
    for s in sessions:
        print(f"{s['session_id']:<20} {s['status']:<12} {s['rounds']}/{s['max_rounds']:<5} {s['use_case']:<4} {s['decisions']:<5} {s['constraints']:<5} {s['ambiguity_avg']:<6}")


def cmd_show(args):
    engine = PERSISTENCE.load(args.id)
    if not engine:
        print(f"Session '{args.id}' not found.")
        return
    print(json.dumps(engine.get_state_dict(), indent=2))
    print(f"\n--- Compact ---")
    print(encode_compact(engine.state))


def cmd_delete(args):
    PERSISTENCE.delete_session(args.id)
    print(f"Session '{args.id}' deleted.")


def main():
    parser = argparse.ArgumentParser(description="RRP — Recursive Refinement Protocol CLI")
    parser.add_argument("--id", "-i", default="default", help="Session ID")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_p = subparsers.add_parser("init", help="Initialize a new session")
    init_p.add_argument("--u", type=int, default=1, choices=range(1, 7), help="Use case (1-6)")
    init_p.add_argument("--m", type=int, default=1, choices=range(1, 4), help="Execution mode (1-3)")
    init_p.add_argument("--z", type=int, default=5, help="Max rounds")
    init_p.add_argument("--depth", type=int, default=2, choices=range(1, 4), help="Depth (1-3)")
    init_p.add_argument("--x", type=int, default=3, help="Questions per round")
    init_p.add_argument("--y", type=int, default=3, help="MCQ options per question")

    # call
    call_p = subparsers.add_parser("call", help="Call a protocol command")
    call_p.add_argument("command", help="Command name")
    call_p.add_argument("args", nargs="*", help="key=value arguments")

    # list
    subparsers.add_parser("list", help="List all sessions")

    # show
    show_p = subparsers.add_parser("show", help="Show session state")
    show_p.add_argument("id", nargs="?", default="default")

    # delete
    del_p = subparsers.add_parser("delete", help="Delete a session")
    del_p.add_argument("id", nargs="?", default="default")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "call":
        cmd_call(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "delete":
        cmd_delete(args)


if __name__ == "__main__":
    main()
