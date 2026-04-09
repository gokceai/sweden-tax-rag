import requests
import streamlit as st
from src.core.config import settings

API_URL = settings.API_BASE_URL

st.set_page_config(page_title=settings.PROJECT_NAME, page_icon="SE", layout="wide")


def _admin_headers(admin_key: str) -> dict:
    headers = {}
    if admin_key.strip():
        headers["X-Admin-Key"] = admin_key.strip()
    return headers


def _read_error(response: requests.Response) -> str:
    request_id = response.headers.get("X-Request-ID")
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code} | request_id={request_id or '-'} | raw={response.text}"

    detail = payload.get("detail")
    if isinstance(detail, dict):
        message = detail.get("message", "Unknown error")
        error_code = detail.get("error_code", "unknown")
        category = detail.get("error_category", "unknown")
        rid = detail.get("request_id", request_id or "-")
        return f"{message} | code={error_code} | category={category} | request_id={rid}"
    return f"HTTP {response.status_code} | request_id={request_id or '-'} | detail={detail}"

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap');

        :root {
            --bg-a: #f4f7f9;
            --bg-b: #e7edf1;
            --ink: #11202d;
            --muted: #4c6172;
            --brand: #0f766e;
            --brand-soft: #d7eeeb;
            --card: rgba(255, 255, 255, 0.78);
        }

        .stApp {
            font-family: 'Manrope', sans-serif;
            background:
                radial-gradient(circle at 8% 8%, rgba(23, 131, 117, 0.09), transparent 22%),
                radial-gradient(circle at 88% 2%, rgba(17, 24, 39, 0.08), transparent 25%),
                linear-gradient(160deg, var(--bg-a), var(--bg-b));
            color: var(--ink);
        }

        .block-container {
            max-width: 1120px;
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .hero {
            padding: 1.4rem 1.5rem;
            border-radius: 1.1rem;
            background: var(--card);
            border: 1px solid rgba(17, 32, 45, 0.08);
            box-shadow: 0 12px 32px rgba(17, 32, 45, 0.08);
            margin-bottom: 1rem;
        }

        .hero-kicker {
            display: inline-block;
            padding: 0.28rem 0.6rem;
            border-radius: 999px;
            background: var(--brand-soft);
            color: var(--brand);
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .hero-title {
            margin: 0.65rem 0 0.4rem 0;
            font-size: 2rem;
            line-height: 1.08;
            letter-spacing: -0.02em;
        }

        .hero-copy {
            margin: 0;
            color: var(--muted);
            font-size: 0.98rem;
            line-height: 1.6;
        }

        .panel {
            padding: 1rem;
            border-radius: 1rem;
            background: var(--card);
            border: 1px solid rgba(17, 32, 45, 0.08);
            margin-top: 0.6rem;
            box-shadow: 0 8px 24px rgba(17, 32, 45, 0.07);
        }

        div[data-testid="stTextInput"] label p,
        div[data-testid="stTextArea"] label p,
        div[data-testid="stSlider"] label p {
            color: #234055 !important;
            font-weight: 700;
        }

        div[data-testid="stTextInput"] p,
        div[data-testid="stTextArea"] p,
        div[data-testid="stSlider"] p {
            color: #315266 !important;
        }

        div[data-testid="stMetricLabel"] p {
            color: #234055 !important;
            font-weight: 700;
        }

        div[data-testid="stMetricValue"] {
            color: #315266 !important;
            font-weight: 700;
        }

        .stButton > button {
            border-radius: 999px;
            border: none;
            background: linear-gradient(135deg, #178375, #0f766e);
            color: #ffffff;
            font-weight: 700;
            min-height: 2.8rem;
        }

        .stButton > button:hover {
            background: linear-gradient(135deg, #147064, #0c5f59);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <section class="hero">
        <span class="hero-kicker">Secure RAG Workspace</span>
        <h1 class="hero-title">{settings.PROJECT_NAME}</h1>
        <p class="hero-copy">
            Ingest source text, run semantic retrieval, and generate grounded responses.
            Encrypted chunks stay in document storage while vectors stay in Chroma.
        </p>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Connection")
    st.caption(f"API base: `{API_URL}`")
    if st.button("Check API Health"):
        try:
            health = requests.get(API_URL.replace("/api/v1", ""), timeout=10)
            if health.status_code == 200:
                st.success("API is reachable")
            else:
                st.warning(f"API responded with {health.status_code}")
        except requests.RequestException:
            st.error("API is not reachable")

    admin_api_key = st.text_input("Admin API Key", type="password", help="Required when ENFORCE_ADMIN_AUTH=true")

    st.markdown("---")
    st.subheader("Consistency")
    if st.button("Run Reconcile"):
        try:
            reconcile_resp = requests.get(
                f"{API_URL}/reconcile",
                headers=_admin_headers(admin_api_key),
                timeout=30,
            )
            if reconcile_resp.status_code == 200:
                report = reconcile_resp.json()
                if report.get("is_consistent"):
                    st.success("Chroma and Dynamo are consistent.")
                else:
                    st.warning(
                        f"Drift found | only_in_chroma={len(report.get('only_in_chroma', []))}, "
                        f"only_in_dynamo={len(report.get('only_in_dynamo', []))}"
                    )
            else:
                st.error(_read_error(reconcile_resp))
        except requests.RequestException as exc:
            st.error(f"Reconcile connection error: {exc}")

    if st.button("Repair (Delete Chroma Orphans + Rehydrate Dynamo)"):
        try:
            repair_resp = requests.post(
                f"{API_URL}/reconcile/repair",
                json={
                    "only_in_chroma_action": "delete",
                    "only_in_dynamo_action": "rehydrate",
                },
                headers=_admin_headers(admin_api_key),
                timeout=60,
            )
            if repair_resp.status_code == 200:
                repair_report = repair_resp.json()
                post = repair_report.get("post_reconcile", {})
                if post.get("is_consistent"):
                    st.success("Repair completed. Stores are now consistent.")
                else:
                    st.warning("Repair completed with remaining drift. Check API logs/report.")
            else:
                st.error(_read_error(repair_resp))
        except requests.RequestException as exc:
            st.error(f"Repair connection error: {exc}")

    if st.button("Show Last Reconcile"):
        try:
            last_resp = requests.get(
                f"{API_URL}/reconcile/last",
                headers=_admin_headers(admin_api_key),
                timeout=30,
            )
            if last_resp.status_code == 200:
                payload = last_resp.json()
                result = payload.get("result")
                if result is None:
                    st.info(payload.get("message", "No reconcile result yet."))
                else:
                    report = payload.get("report", {})
                    st.caption(f"Checked at: {payload.get('checked_at')} ({payload.get('source')})")
                    st.write(
                        {
                            "is_consistent": report.get("is_consistent"),
                            "only_in_chroma": len(report.get("only_in_chroma", [])),
                            "only_in_dynamo": len(report.get("only_in_dynamo", [])),
                        }
                    )
            else:
                st.error(_read_error(last_resp))
        except requests.RequestException as exc:
            st.error(f"Last reconcile connection error: {exc}")

if settings.ENABLE_INGEST_UI:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.subheader("Document Ingest")
    source_name = st.text_input("Source name", value="skatteverket_guide.txt")
    document_text = st.text_area(
        "Document text",
        height=260,
        placeholder="Paste source content here...",
    )

    if st.button("Upload", type="primary"):
        if len(document_text.strip()) < 10:
            st.warning("Document text must be at least 10 characters.")
        else:
            try:
                response = requests.post(
                    f"{API_URL}/ingest",
                    json={"document_text": document_text, "source_name": source_name},
                    headers=_admin_headers(admin_api_key),
                    timeout=60,
                )
                if response.status_code == 200:
                    payload = response.json()
                    st.success(
                        f"{payload.get('chunks_processed', 0)} chunks processed for {payload.get('source', source_name)}."
                    )
                else:
                    st.error(_read_error(response))
            except requests.RequestException as exc:
                st.error(f"API connection error: {exc}")
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("Ingest UI is disabled. This workspace is running in question-only mode.")

query = st.text_input("Question", placeholder="What VAT rate applies to hotel stays?")
top_k = st.slider("Top K contexts", min_value=1, max_value=5, value=2)

if st.button("Generate Answer"):
    if len(query.strip()) < 5:
        st.warning("Question must be at least 5 characters.")
    else:
        try:
            response = requests.post(
                f"{API_URL}/retrieve",
                json={"query": query, "top_k": top_k},
                timeout=90,
            )
            if response.status_code == 200:
                payload = response.json()
                answer = payload.get("answer", "")
                contexts = payload.get("contexts")

                st.markdown("### Answer")
                st.write(answer)

                if isinstance(contexts, list):
                    if contexts:
                        st.markdown("### Retrieved Context")
                        for idx, context in enumerate(contexts, start=1):
                            with st.expander(f"Context {idx}"):
                                st.write(context)
                    else:
                        st.info("No context matched this question.")
                else:
                    st.caption("Context visibility is disabled by server configuration.")
            else:
                st.error(_read_error(response))
        except requests.RequestException as exc:
            st.error(f"API connection error: {exc}")
