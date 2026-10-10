import argparse
import json
import csv
from pathlib import Path
from .model import PRESETS, Scenario
from .validation import compare, campaign
from .server import serve


def main():
    parser = argparse.ArgumentParser(description="TorqueGuard hybrid control validation lab")
    sub = parser.add_subparsers(dest="command", required=True)
    ui = sub.add_parser("serve", help="Launch local telemetry dashboard")
    ui.add_argument("--port", type=int, default=8765)
    replay = sub.add_parser("replay", help="Compare controllers and export full traces")
    replay.add_argument("--scenario", choices=PRESETS, default="wet_concertina")
    replay.add_argument("--input", type=Path, help="Replay a scenario JSON or campaign witness JSON")
    replay.add_argument("--output", type=Path)
    replay.add_argument("--csv", type=Path, help="Export paired telemetry to CSV")
    scan = sub.add_parser("campaign", help="Run reproducible sampled trajectory validation")
    scan.add_argument("--cases", type=int, default=100)
    scan.add_argument("--seed", type=int, default=2026)
    scan.add_argument("--output", type=Path)
    scan.add_argument("--fail-on", choices=("faulty", "corrected", "none"), default="corrected")
    args = parser.parse_args()
    if args.command == "serve":
        serve(args.port)
        return
    try:
        if args.command == "replay":
            scenario = PRESETS[args.scenario]
            if args.input:
                raw = json.loads(args.input.read_text())
                if "first_counterexample" in raw:
                    raw = raw["first_counterexample"]
                if raw is None:
                    raise ValueError("Report contains no counterexample")
                scenario = Scenario(**raw.get("scenario", raw))
            result = compare(scenario)
            if args.csv:
                args.csv.parent.mkdir(parents=True, exist_ok=True)
                rows = [{"variant": v, **x} for v, run in result["runs"].items() for x in run["trace"]]
                with args.csv.open("w", newline="") as file:
                    writer = csv.DictWriter(file, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
        else:
            result = campaign(args.seed, args.cases)
        serialized = json.dumps(result, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized + "\n")
            print(f"Report: {args.output.resolve()}")
            if args.command == "campaign":
                print(json.dumps({k: result[k] for k in ("seed", "cases", "failures", "rescued_cases")}, indent=2))
        else:
            print(serialized)
        if args.command == "campaign" and args.fail_on != "none" and result["failures"][args.fail_on]:
            raise SystemExit(1)
    except (ValueError, TypeError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
