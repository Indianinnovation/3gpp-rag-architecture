"""
TS Analyzer Agent — Generates answers from retrieved 3GPP specification chunks.
"""

from langchain_xai import ChatXAI
from dotenv import load_dotenv
import os

load_dotenv()


def analyze_spec(state: dict) -> dict:
    question = state["question"]
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        state["agent_response"] = "No relevant information found in the knowledge base."
        return state

    context = "\n\n".join(
        f"[Source {i}: {c['spec_number']} | {c['release']} | {c['section_hierarchy']}]\n{c['content']}"
        for i, c in enumerate(chunks, 1)
    )

    api_key = os.getenv("XAI_API_KEY")
    if api_key:
        llm = ChatXAI(model="grok-4", api_key=api_key)
        prompt = (
            f"You are a 3GPP technical standards expert. Answer using ONLY the context below. "
            f"Cite sources as [Source N].\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        )
        response = llm.invoke(prompt)
        state["agent_response"] = response.content
    else:
        state["agent_response"] = f"Based on retrieved specs:\n\n{context}\n\n(Set XAI_API_KEY for synthesized answers.)"

    return state
