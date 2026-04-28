from langgraph.graph import StateGraph, START, END
from src.agent.state import AgentState
from src.agent.nodes import node_think, node_act, node_save_results
from src.agent.edges import should_continue


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("think",        node_think)
    graph.add_node("act",          node_act)
    graph.add_node("save_results", node_save_results)

    graph.add_edge(START,          "think")
    graph.add_edge("think",        "act")
    graph.add_edge("save_results", END)

    graph.add_conditional_edges(
        "act",
        should_continue,
        {
            "continue": "think",
            "done":     "save_results",
        }
    )

    return graph.compile()