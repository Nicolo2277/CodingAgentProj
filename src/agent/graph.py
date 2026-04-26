from langgraph.graph import StateGraph, START, END
from src.agent.state import AgentState
from src.agent.nodes import node_scan_repo, node_analyze_file, node_save_results
from src.agent.edges import should_continue


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("scan_repo", node_scan_repo)
    graph.add_node("analyze_file", node_analyze_file)
    graph.add_node("save_results", node_save_results)

    # add static edges
    graph.add_edge(START, "scan_repo")
    graph.add_edge("scan_repo", "analyze_file")
    graph.add_edge("save_results", END)

    # conditional edges
    graph.add_conditional_edges(
        "analyze_file",
        should_continue,
        {
            "analyze": "analyze_file",  # repeat
            "done":    "save_results",  # end of the cycle
        }
    )

    return graph.compile()