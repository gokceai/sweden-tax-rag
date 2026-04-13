import requests
import gradio as gr

from src.core.config import settings

API_URL = settings.API_BASE_URL

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap');

:root {
  --bg-start: #101926;
  --bg-end: #18263a;
  --text-main: #eef5ff;
  --text-subtle: #dce7f6;
  --button-start: #14b8a6;
  --button-end: #0f766e;
}

.gradio-container {
  font-family: 'Manrope', sans-serif !important;
  background: linear-gradient(165deg, var(--bg-start) 0%, var(--bg-end) 100%);
  color: var(--text-main);
}

#app-title {
  text-align: center;
  letter-spacing: -0.02em;
  margin-bottom: 0.8rem;
}

#app-subtitle {
  text-align: center;
  color: var(--text-subtle);
  margin-bottom: 1.2rem;
}

button.primary {
  border: none !important;
  border-radius: 999px !important;
  background: linear-gradient(135deg, var(--button-start), var(--button-end)) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
}
"""


def _candidate_api_urls() -> list[str]:
    """Try configured URL first; fall back to localhost variants for same-container setups."""
    urls = [API_URL.rstrip("/")]
    # docker-compose: api service hostname
    if "://api:" in API_URL:
        urls.append("http://localhost:8080/api/v1")
    # HF Spaces / single-container: Gradio and API share the same uvicorn process
    for port in (7860, 8080):
        candidate = f"http://localhost:{port}/api/v1"
        if candidate not in urls:
            urls.append(candidate)
    return list(dict.fromkeys(urls))


def ask_question(question: str) -> tuple[str, str]:
    prompt = (question or "").strip()
    if len(prompt) < 5:
        return "", "Question must be at least 5 characters."

    response = None
    last_error = None
    for base_url in _candidate_api_urls():
        try:
            response = requests.post(
                f"{base_url}/retrieve",
                json={"query": prompt, "top_k": 2},
                timeout=300,
            )
            break
        except requests.RequestException as exc:
            last_error = exc

    if response is None:
        return "", f"API connection error: {last_error}"

    if response.status_code != 200:
        return "", f"Request failed ({response.status_code})."

    payload = response.json()
    return payload.get("answer", ""), ""


def _set_inputs_enabled(enabled: bool):
    return gr.update(interactive=enabled), gr.update(interactive=enabled)


def build_app() -> gr.Blocks:
    with gr.Blocks(title=settings.PROJECT_NAME, head=f"<style>{CUSTOM_CSS}</style>") as demo:
        gr.Markdown(f"## {settings.PROJECT_NAME}", elem_id="app-title")
        gr.Markdown("Ask your Swedish tax question through the API.", elem_id="app-subtitle")

        question = gr.Textbox(
            label="Question",
            placeholder="Ask your Swedish tax question...",
            lines=3,
            max_lines=6,
        )
        ask_btn = gr.Button("Ask", variant="primary")

        answer = gr.Markdown(label="Answer")
        error = gr.Markdown(label="Status")

        def bind_query_event(event):
            return (
                event(fn=lambda: _set_inputs_enabled(False), outputs=[ask_btn, question], queue=False)
                .then(ask_question, inputs=[question], outputs=[answer, error])
                .then(fn=lambda: _set_inputs_enabled(True), outputs=[ask_btn, question], queue=False)
            )

        bind_query_event(ask_btn.click)
        bind_query_event(question.submit)

    return demo


app = build_app()


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=8501)
