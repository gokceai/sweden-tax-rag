import streamlit as st
import requests
import sys
import os


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.core.config import settings

API_URL = settings.API_BASE_URL

st.set_page_config(page_title=settings.PROJECT_NAME, page_icon="SE", layout="wide")


st.markdown(
    """
    <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(197, 225, 245, 0.9), transparent 28%),
                radial-gradient(circle at top right, rgba(228, 233, 240, 0.95), transparent 30%),
                linear-gradient(180deg, #f8fafc 0%, #edf2f7 100%);
            color: #17202d;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 2.4rem;
            padding-bottom: 2.8rem;
        }

        .hero-shell {
            padding: 2.8rem 2.5rem;
            border-radius: 36px;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.58));
            border: 1px solid rgba(255, 255, 255, 0.72);
            box-shadow: 0 18px 45px rgba(30, 41, 59, 0.08);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            margin-bottom: 1.5rem;
        }

        .hero-kicker {
            display: inline-block;
            padding: 0.45rem 0.9rem;
            border-radius: 999px;
            background: rgba(126, 155, 184, 0.14);
            color: #5f81a8;
            font-size: 0.82rem;
            font-weight: 700;
            margin-bottom: 1rem;
        }

        .hero-title {
            margin: 0 0 0.8rem 0;
            font-size: 3rem;
            line-height: 1.02;
            font-weight: 700;
            letter-spacing: -0.03em;
        }

        .hero-copy {
            margin: 0;
            max-width: 760px;
            color: #637082;
            font-size: 1.03rem;
            line-height: 1.75;
        }

        .mini-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.95rem;
            margin: 1.2rem 0 2rem 0;
        }

        .mini-card {
            padding: 1rem 1.05rem;
            border-radius: 22px;
            background: rgba(255, 255, 255, 0.74);
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }

        .mini-label {
            color: #637082;
            font-size: 0.8rem;
            margin-bottom: 0.3rem;
        }

        .mini-value {
            color: #17202d;
            font-size: 1rem;
            font-weight: 600;
        }

        .panel-card {
            background: rgba(255, 255, 255, 0.74);
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 30px;
            padding: 1.2rem 1.2rem 1.35rem 1.2rem;
            box-shadow: 0 18px 45px rgba(30, 41, 59, 0.08);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            margin-bottom: 0.9rem;
        }

        .panel-title {
            color: #17202d;
            font-size: 1.35rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
        }

        .panel-copy {
            color: #637082;
            font-size: 0.96rem;
            line-height: 1.65;
            margin-bottom: 0;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {
            background: rgba(255, 255, 255, 0.96);
            color: #17202d;
        }

        div[data-testid="stTextInput"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stSlider"] label,
        div[data-testid="stMarkdownContainer"] label {
            color: #17202d !important;
        }

        div[data-testid="stTextInput"] p,
        div[data-testid="stTextArea"] p,
        div[data-testid="stSlider"] p {
            color: #17202d !important;
            font-weight: 600;
        }

        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus {
            border-color: rgba(95, 129, 168, 0.45);
            box-shadow: 0 0 0 1px rgba(95, 129, 168, 0.18);
        }

        .stButton > button {
            width: 100%;
            min-height: 3rem;
            border: none;
            border-radius: 999px;
            background: linear-gradient(135deg, #91acc7, #7091b5);
            color: #ffffff;
            font-weight: 600;
            box-shadow: 0 12px 24px rgba(95, 129, 168, 0.24);
            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 16px 28px rgba(95, 129, 168, 0.3);
        }

        div[data-testid="stAlert"] {
            border-radius: 20px;
            border: 1px solid rgba(15, 23, 42, 0.06);
        }

        .answer-card {
            padding: 1.15rem 1.2rem;
            border-radius: 24px;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(245, 248, 251, 0.93));
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 16px 34px rgba(30, 41, 59, 0.08);
            margin-top: 0.8rem;
            margin-bottom: 1rem;
        }

        .answer-eyebrow {
            color: #5f81a8;
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.55rem;
        }

        .answer-copy {
            color: #17202d;
            font-size: 1rem;
            line-height: 1.75;
            margin: 0;
        }

        .context-card {
            padding: 1rem;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.74);
            border: 1px solid rgba(15, 23, 42, 0.07);
            margin-bottom: 0.8rem;
        }

        .context-title {
            color: #5f81a8;
            font-size: 0.84rem;
            font-weight: 700;
            margin-bottom: 0.4rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }

        .context-copy {
            color: #17202d;
            font-size: 0.95rem;
            line-height: 1.72;
            margin: 0;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <section class="hero-shell">
        <div class="hero-kicker">Private RAG Workspace</div>
        <h1 class="hero-title">{settings.PROJECT_NAME}</h1>
        <p class="hero-copy">
            A calm, refined workspace for ingesting Swedish tax material, retrieving the most relevant
            encrypted context, and generating concise grounded answers with a local language model.
        </p>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="mini-grid">
        <div class="mini-card">
            <div class="mini-label">Storage Pattern</div>
            <div class="mini-value">Vectors in ChromaDB, encrypted text in DynamoDB</div>
        </div>
        <div class="mini-card">
            <div class="mini-label">Retrieval Style</div>
            <div class="mini-value">Semantic search powered by local embeddings</div>
        </div>
        <div class="mini-card">
            <div class="mini-label">Answer Layer</div>
            <div class="mini-value">Local Llama-compatible response generation</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

left_col, right_col = st.columns([1.02, 1.28], gap="large")

with left_col:
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Document Ingest</div>
            <div class="panel-copy">
                Add source text to the knowledge base. The service splits the content into chunks,
                generates embeddings, and stores the original text in encrypted form.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    source_name = st.text_input("Document Source", value="skatteverket_guide.txt")
    document_text = st.text_area(
        "Document Text",
        height=290,
        placeholder="Paste Swedish tax rules, policy notes, or source excerpts here...",
    )

    if st.button("Upload Securely", type="primary"):
        if len(document_text) < 10:
            st.warning("Please enter at least 10 characters of source text.")
        else:
            with st.spinner("Splitting, embedding, encrypting, and storing the document..."):
                try:
                    response = requests.post(
                        f"{API_URL}/ingest",
                        json={"document_text": document_text, "source_name": source_name},
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.success(f"{data['chunks_processed']} chunks were processed and stored securely.")
                    else:
                        st.error(f"Server error: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("The API is unreachable. Please ensure the FastAPI server on port 8080 is running.")

with right_col:
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Ask The Knowledge Base</div>
            <div class="panel-copy">
                Search the ingested material semantically, retrieve the most relevant context,
                and generate a direct answer grounded in the retrieved text.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    query = st.text_input("Your Question", placeholder="For example: What VAT rate applies to hotel stays?")
    top_k = st.slider("Retrieved Context Count", min_value=1, max_value=5, value=2)

    if st.button("Generate Answer"):
        if len(query) < 5:
            st.warning("Please enter a more complete question.")
        else:
            with st.spinner("Retrieving context and generating an answer..."):
                try:
                    response = requests.post(
                        f"{API_URL}/retrieve",
                        json={"query": query, "top_k": top_k},
                    )
                    if response.status_code == 200:
                        data = response.json()
                        answer = data.get("answer", "")
                        contexts = data.get("contexts", [])

                        if not contexts:
                            st.warning("No matching legal context was found for this question.")
                        else:
                            st.markdown(
                                f"""
                                <div class="answer-card">
                                    <div class="answer-eyebrow">AI Assistant Answer</div>
                                    <p class="answer-copy">{answer}</p>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            st.markdown("### Retrieved Context")
                            for index, context in enumerate(contexts, start=1):
                                st.markdown(
                                    f"""
                                    <div class="context-card">
                                        <div class="context-title">Reference {index}</div>
                                        <p class="context-copy">{context}</p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                    else:
                        st.error(f"Server error: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("The API is unreachable. Please ensure the FastAPI server on port 8080 is running.")
