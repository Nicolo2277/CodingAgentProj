from langgraph.graph import StateGraph, START, END
from src.agent.state import AgentState
from src.agent.nodes import node_think_act, node_save_results, node_plan
from src.agent.edges import should_continue


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("plan", node_plan)
    graph.add_node("think_act", node_think_act)
    graph.add_node("save_results", node_save_results)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "think_act")
    graph.add_edge("save_results", END)

    graph.add_conditional_edges(
        "think_act",
        should_continue,
        {
            "continue": "think_act",
            "done":     "save_results",
        }
    )

    return graph.compile()