import argparse
from pathlib import Path
from src.agent.graph import build_graph
from src.logger import get_logger

logger = get_logger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze a python file to find bugs")
    parser.add_argument("path", help="path of the repo/folder to analyze")
    return parser.parse_args()    


if __name__ == "__main__":
    args = parse_args()

    agent = build_graph()
    final_state = agent.invoke({
        "repo_path":       Path(args.path),
        "files_to_analyze": [],
        "files_analyzed":  [],
        "files_failed":    [],
        "reports":         {},
        "total_bugs":      0,
    })