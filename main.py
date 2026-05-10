import argparse
from pathlib import Path

from src.agent.graph import build_graph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ReAct agent for Python repo analysis")
    parser.add_argument("path",        help="Path to the repo")
    parser.add_argument("--max-steps", type=int, default=20)
    return parser.parse_args()


if __name__ == "__main__":
    args  = parse_args()
    agent = build_graph()

    final_state = agent.invoke({
        "repo_path":       Path(args.path),
        # file tracking
        "available_files": [],
        "files_analyzed":  [],
        "files_failed":    [],
        "files_run":       [],
        "files_verified":  [],
        # ReAct
        "action_history":  [],
        "current_step":    0,
        "max_steps":       args.max_steps,
        "finished":        False,
        # results
        "reports":          {},
        "run_results":      {},
        "verified_reports": {},
        # metadata
        "total_bugs":      0,
        "confirmed_bugs":  0,
        "summary":         "",
    })  # type: ignore[arg-type]

    plan  = final_state.get("plan")
    steps = len(plan.steps) if plan else "?"

    total     = final_state.get("total_bugs",     0)
    confirmed = final_state.get("confirmed_bugs",  0)
    rate      = f"{confirmed / total:.0%}" if total else "n/a"

    print(f"\n{'=' * 50}")
    print(f"Plan            : {steps} files planned")
    print(f"Files analysed  : {len(final_state.get('files_analyzed', []))}")
    print(f"Files run       : {len(final_state.get('files_run',      []))}")
    print(f"Files verified  : {len(final_state.get('files_verified', []))}")
    print(f"Total bugs      : {total}")
    print(f"Confirmed bugs  : {confirmed}  ({rate} confirmation rate)")
    print(f"Summary         : {final_state.get('summary', 'N/A')}")
    print(f"{'=' * 50}")