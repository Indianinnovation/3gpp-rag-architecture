"""
3GPP Document Q&A — POC Streamlit Application.
Upload 3GPP specs and ask questions via multi-agent system.
"""

import streamlit as st
import tempfile
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="3GPP RAG POC", page_icon="📡", layout="wide")
st.title("📡 3GPP Multi-Agent RAG — Proof of Concept")

with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("XAI API Key", type="password", value=os.environ.get("XAI_API_KEY", ""))
    if api_key:
        os.environ["XAI_API_KEY"] = api_key
    st.divider()
    st.caption("DB: localhost:5432/knowledge_base_3gpp")

# Phase 1: Upload & Ingest
st.header("1️⃣ Upload & Ingest 3GPP Document")
col1, col2 = st.columns([2, 1])
with col1:
    uploaded_file = st.file_uploader("Upload 3GPP PDF", type="pdf")
with col2:
    release = st.selectbox("Release", ["rel-15", "rel-16", "rel-17", "rel-18", "rel-19"], index=2)

if uploaded_file and st.button("🚀 Ingest Document", type="primary"):
    with st.spinner("Processing..."):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name
        try:
            from ingest import ingest
            ingest(tmp_path, release)
            st.success(f"✅ Ingested into {release} knowledge base!")
        except Exception as e:
            st.error(f"❌ {e}")
        finally:
            os.unlink(tmp_path)

st.divider()

# Phase 2: Multi-Agent Q&A
st.header("2️⃣ Ask Questions (Multi-Agent)")
release_filter = st.selectbox("Filter by Release", ["All", "rel-15", "rel-16", "rel-17", "rel-18"])

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if question := st.chat_input("Ask about 3GPP specifications..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("🧠 Agents reasoning..."):
            try:
                from agents.graph import build_graph
                graph = build_graph()
                result = graph.invoke({
                    "question": question,
                    "release_filter": "" if release_filter == "All" else release_filter,
                    "plan": "", "retrieved_chunks": [], "agent_response": "",
                    "gatekeeper_pass": False, "auditor_pass": False,
                    "final_answer": "", "retry_count": 0,
                })
                answer = result.get("final_answer", "No answer generated.")
                with st.expander("🔍 Agent Trace"):
                    st.json({"plan": result.get("plan"), "chunks": len(result.get("retrieved_chunks", [])),
                             "gatekeeper": result.get("gatekeeper_pass"), "auditor": result.get("auditor_pass"),
                             "retries": result.get("retry_count")})
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"❌ {e}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})
