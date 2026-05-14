"""
LangGraph Multi-Agent Orchestration for 3GPP Q&A.
Planner → Specialized Agents → Gatekeeper → Auditor → Response
"""

from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from agents.planner import plan_query
from agents.ts_analyzer import analyze_spec
from agents.validator import gatekeeper_check, auditor_check


class AgentState(TypedDict):
    question: str
    release_filter: str
    plan: str
    retrieved_chunks: list
    agent_response: str
    gatekeeper_pass: bool
    auditor_pass: bool
    final_answer: str
    retry_count: int


def route_after_plan(state: AgentState) -> Literal["ts_analyzer", "release_comparator"]:
    if "compare" in state.get("plan", "").lower():
        return "release_comparator"
    return "ts_analyzer"


def route_after_gatekeeper(state: AgentState) -> Literal["auditor", "planner"]:
    if state.get("gatekeeper_pass") or state.get("retry_count", 0) >= 2:
        return "auditor"
    return "planner"


def route_after_auditor(state: AgentState) -> Literal["respond", "planner"]:
    if state.get("auditor_pass") or state.get("retry_count", 0) >= 2:
        return "respond"
    return "planner"


def respond(state: AgentState) -> AgentState:
    state["final_answer"] = state.get("agent_response", "Unable to answer.")
    return state


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("planner", plan_query)
    graph.add_node("ts_analyzer", analyze_spec)
    graph.add_node("release_comparator", analyze_spec)
    graph.add_node("gatekeeper", gatekeeper_check)
    graph.add_node("auditor", auditor_check)
    graph.add_node("respond", respond)

    graph.set_entry_point("planner")
    graph.add_conditional_edges("planner", route_after_plan)
    graph.add_edge("ts_analyzer", "gatekeeper")
    graph.add_edge("release_comparator", "gatekeeper")
    graph.add_conditional_edges("gatekeeper", route_after_gatekeeper)
    graph.add_conditional_edges("auditor", route_after_auditor)
    graph.add_edge("respond", END)

    return graph.compile()
