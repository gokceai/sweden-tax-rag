import requests
import streamlit as st

from src.core.config import settings

API_URL = settings.API_BASE_URL

st.set_page_config(page_title=settings.PROJECT_NAME, page_icon="SE", layout="centered")

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap');

        .stApp {
            font-family: 'Manrope', sans-serif;
            background: linear-gradient(165deg, #101926 0%, #18263a 100%);
            color: #eef5ff;
        }

        .block-container {
            max-width: 760px;
            padding-top: 3.5rem;
            padding-bottom: 2rem;
        }

        h1 {
            text-align: center;
            letter-spacing: -0.02em;
            margin-bottom: 2rem;
        }

        div[data-testid="stTextInput"] input {
            background: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #e5e7eb !important;
            border-radius: 14px !important;
            min-height: 3rem !important;
        }

        div[data-testid="stTextInput"] label p {
            color: #dce7f6 !important;
            font-weight: 700;
        }

        .stButton > button {
            width: 100%;
            border-radius: 999px;
            border: none;
            background: linear-gradient(135deg, #14b8a6, #0f766e);
            color: #ffffff;
            font-weight: 700;
            min-height: 2.8rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(settings.PROJECT_NAME)

question = st.text_input(
    "Question",
    placeholder="Ask your Swedish tax question...",
    label_visibility="collapsed",
)

if st.button("Ask"):
    if len(question.strip()) < 5:
        st.warning("Question must be at least 5 characters.")
    else:
        try:
            response = requests.post(
                f"{API_URL}/retrieve",
                json={"query": question, "top_k": 2},
                timeout=90,
            )
            if response.status_code == 200:
                payload = response.json()
                st.write(payload.get("answer", ""))
            else:
                st.error(f"Request failed ({response.status_code}).")
        except requests.RequestException as exc:
            st.error(f"API connection error: {exc}")
