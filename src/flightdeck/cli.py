import argparse
import json
from pathlib import Path
import sys

from .core import Controller, ContractError, audit_run
from .policies import RulePolicy, JevPolicy, OllamaPolicy
from .report import render


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a reviewed experiment; recover artifact contracts; verify frozen evidence.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("manifest")
    run.add_argument("--out", required=True)
    run.add_argument("--policy", choices=["strict", "rules", "jev", "ollama", "hybrid"], default="rules")
    run.add_argument("--model", help="Installed Ollama model for ollama/hybrid")
    run.add_argument("--jev-model", default="jev-1.13.0")
    run.add_argument("--confidence", type=float, default=0.7)
    run.add_argument("--max-steps", type=int, default=10)
    run.add_argument("--allow-local-exec", action="store_true", help="Acknowledge this executes reviewed Python code locally, without OS isolation")
    audit = sub.add_parser("audit")
    audit.add_argument("directory")
    replay = sub.add_parser("replay")
    replay.add_argument("directory")
    try:
        args = parser.parse_args(argv)
        if args.command in {"audit", "replay"}:
            result = audit_run(args.directory)
            if args.command == "replay":
                path = Path(args.directory)
                render(json.loads((path / "summary.json").read_text(encoding="utf-8")), path / "report.html")
            print(json.dumps(result))
            return 0
        if not args.allow_local_exec:
            raise ContractError("Review the listed inputs, then pass --allow-local-exec. This runner is not a sandbox.")
        if args.policy in {"rules", "strict"}:
            policy = RulePolicy(strict=args.policy == "strict")
        elif args.policy == "ollama":
            policy = OllamaPolicy(args.model)
        else:
            fallback = OllamaPolicy(args.model) if args.policy == "hybrid" else None
            policy = JevPolicy(args.jev_model, args.confidence, fallback=fallback)
        result = Controller(args.manifest, args.out, policy, args.max_steps).run()
        print(json.dumps({k: result[k] for k in ("id", "status", "policy", "result", "failure")}, indent=2))
        print("Replay: " + str(Path(args.out).resolve() / "report.html"))
        return 0 if result["status"] == "verified" else 1
    except (ContractError, OSError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
