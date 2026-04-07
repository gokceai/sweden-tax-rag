import streamlit as st
import requests
import sys
import os


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.core.config import settings

API_URL = settings.API_BASE_URL

st.set_page_config(page_title=settings.PROJECT_NAME, page_icon="🇸🇪", layout="wide")

st.title(f"🇸🇪 {settings.PROJECT_NAME}")
# st.markdown("""
# **Hugging Face Showcase & Enterprise RAG Architecture**
# """)

col1, col2 = st.columns([1, 2])

with col1:
    st.header("Document Upload (Ingest)")
    st.info("Enter a text containing Swedish tax regulations..")
    
    source_name = st.text_input("Document Source (Name)", value="skatteverket_guide.txt")
    document_text = st.text_area("Document Text", height=200, placeholder="Paste the tax laws here...")
    
    if st.button("Upload and Encrypt", type="primary"):
        if len(document_text) < 10:
            st.warning("Please enter a text of at least 10 characters.")
        else:
            with st.spinner("With LangChain, it is broken down, encrypted, and stored..."):
                try:
                    response = requests.post(
                        f"{API_URL}/ingest",
                        json={"document_text": document_text, "source_name": source_name}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.success(f"{data['chunks_processed']} The data was successfully processed and securely written to the databases!")
                    else:
                        st.error(f"Server Error: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("The API is unreachable. Please ensure the FastAPI server (port 8080) is open.")

with col2:
    st.header("Smart Search (Retrieve)")
    st.info("Ask questions about the laws you uploaded to the system.")
    
    query = st.text_input("Your question:", placeholder="Ex: What is the VAT rate for books?")
    top_k = st.slider("Number of Contexts to be Retrieved", min_value=1, max_value=5, value=2)
    
    if st.button("Search for answers"):
        if len(query) < 5:
            st.warning("Please ask a sensible question.")
        else:
            # The process will take a while now that it's running the LLM.
            with st.spinner("Llama 3.2 is thinking and generating an answer (This may take a few seconds)...."):
                try:
                    response = requests.post(
                        f"{API_URL}/retrieve",
                        json={"query": query, "top_k": top_k}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        answer = data.get("answer", "")
                        contexts = data.get("contexts", [])
                        
                        if not contexts:
                            st.warning("No legal context was found in the database for this question.")
                        else:
                            # AI's Answer in Its Own Words
                            st.success(" AI Oracle Answer:")
                            st.write(f"**{answer}**")
                            
                            st.divider()
                            
                            #  Reference Sources
                            st.markdown("###  Source (Decoded Contexts):")
                            for i, ctx in enumerate(contexts):
                                st.info(f"**Reference {i+1}:** {ctx}")
                    else:
                        st.error(f"Server Error: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("The API is unreachable. Please ensure the FastAPI server (port 8080) is open.")