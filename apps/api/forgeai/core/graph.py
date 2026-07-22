from typing import Any

from langgraph.graph import END, START, StateGraph

from forgeai.agents import register_builtin_plugins
from forgeai.agents.state import ForgeState
from forgeai.plugins import registry

register_builtin_plugins()


def should_continue(state: dict[str, Any]) -> str:
    return "halt" if state.get("halted") else "continue"


def build_forge_graph():
    graph = StateGraph(ForgeState)
    for plugin_name in [
        "planner",
        "repo-rag",
        "coder",
        "approval-gate",
        "testing",
        "vision",
        "security",
        "review",
        "docs",
        "deployment",
        "memory",
    ]:
        if plugin_name == "approval-gate":
            from forgeai.agents.builtins import approval_gate_node

            graph.add_node(plugin_name, approval_gate_node)
            continue
        plugin = registry.get(plugin_name)
        if plugin.node_builder is None:
            raise RuntimeError(f"Plugin has no graph node: {plugin_name}")
        graph.add_node(plugin_name, plugin.node_builder())

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "repo-rag")
    graph.add_edge("repo-rag", "coder")
    graph.add_edge("coder", "approval-gate")
    graph.add_conditional_edges(
        "approval-gate",
        should_continue,
        {"halt": END, "continue": "testing"},
    )
    graph.add_edge("testing", "vision")
    graph.add_edge("vision", "security")
    graph.add_edge("security", "review")
    graph.add_edge("review", "docs")
    graph.add_edge("docs", "deployment")
    graph.add_conditional_edges(
        "deployment",
        should_continue,
        {"halt": END, "continue": "memory"},
    )
    graph.add_edge("memory", END)
    return graph.compile()
