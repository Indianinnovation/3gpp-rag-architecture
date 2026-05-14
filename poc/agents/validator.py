"""
Validation Agents — Gatekeeper (release correctness) and Auditor (grounding check).
"""


def gatekeeper_check(state: dict) -> dict:
    response = state.get("agent_response", "")
    release_filter = state.get("release_filter", "")
    chunks = state.get("retrieved_chunks", [])
    question = state["question"]

    # Check: non-empty response
    if len(response.strip()) < 20:
        state["gatekeeper_pass"] = False
        state["retry_count"] = state.get("retry_count", 0) + 1
        return state

    # Check: release alignment
    if release_filter and chunks:
        correct = [c for c in chunks if c.get("release") == release_filter]
        if len(correct) < len(chunks) * 0.5:
            state["gatekeeper_pass"] = False
            state["retry_count"] = state.get("retry_count", 0) + 1
            return state

    # Check: question relevance
    overlap = set(question.lower().split()) & set(response.lower().split())
    if len(overlap) < 2:
        state["gatekeeper_pass"] = False
        state["retry_count"] = state.get("retry_count", 0) + 1
        return state

    state["gatekeeper_pass"] = True
    return state


def auditor_check(state: dict) -> dict:
    response = state.get("agent_response", "")
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        state["auditor_pass"] = True
        return state

    all_context = " ".join(c["content"].lower() for c in chunks)
    context_words = set(all_context.split())
    sentences = response.split(".")

    grounded = sum(
        1 for s in sentences
        if s.strip() and len(set(s.lower().split()) & context_words) / max(len(s.split()), 1) > 0.3
    )

    state["auditor_pass"] = grounded / max(len(sentences), 1) >= 0.4
    if not state["auditor_pass"]:
        state["retry_count"] = state.get("retry_count", 0) + 1

    return state
