# main.py
import argparse
from pathlib import Path
from src.agent.graph import build_graph


def parse_args():
    parser = argparse.ArgumentParser(description="ReAct agent for Python repo analysis")
    parser.add_argument("path",         help="Path to the repo")
    parser.add_argument("--max-steps",  type=int, default=20)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    agent = build_graph()
    final_state = agent.invoke({
        "repo_path":      Path(args.path),
        "files_analyzed": [],
        "files_failed":   [],
        "files_run":      [],
        "action_history": [],
        "current_step":   0,
        "max_steps":      args.max_steps,
        "finished":       False,
        "reports":        {},
        "run_results":    {},
        "total_bugs":     0,
        "summary":        "",
    }) # type: ignore

    print(f"\n{'='*40}")
    print(f"Summary: {final_state.get('summary', 'N/A')}")
    print(f"Files analyzed: {len(final_state.get('files_analyzed', []))}")
    print(f"Files run      : {len(final_state.get('files_run', []))}")
    print(f"Total bugs: {final_state.get('total_bugs', 0)}")