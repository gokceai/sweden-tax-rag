import requests
import gradio as gr

from src.core.config import settings

API_URL = settings.API_BASE_URL


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
    theme = gr.themes.Soft(
        primary_hue="teal",
        secondary_hue="slate",
        font=gr.themes.GoogleFont("Manrope"),
    )
    with gr.Blocks(title=settings.PROJECT_NAME, theme=theme) as demo:
        gr.Markdown(f"## ⚖️ {settings.PROJECT_NAME}")
        gr.Markdown("Ask your Swedish tax question below.")

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
