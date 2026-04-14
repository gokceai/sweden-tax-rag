import logging

import gradio as gr

from src.core.config import settings

logger = logging.getLogger(__name__)


def ask_question(question: str) -> tuple[str, str]:
    """Call RAG + LLM directly — no HTTP roundtrip needed in single-container deployment."""
    prompt = (question or "").strip()
    if len(prompt) < 5:
        return "", "Question must be at least 5 characters."
    try:
        from src.core.dependencies import get_answer_generator, get_rag_engine  # noqa: PLC0415

        contexts = get_rag_engine().retrieve_context(
            prompt,
            top_k=settings.RETRIEVAL_TOP_K,
        )
        if not contexts:
            return settings.WARNING_PROMPT, ""
        answer = get_answer_generator().generate_answer(prompt, contexts)
        return answer, ""
    except Exception as exc:
        logger.exception("ask_question failed: %s", exc)
        return "", f"Error: {exc}"


def _toggle(enabled: bool):
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

        def _bind(event):
            return (
                event(fn=lambda: _toggle(False), outputs=[ask_btn, question], queue=False)
                .then(ask_question, inputs=[question], outputs=[answer, error])
                .then(fn=lambda: _toggle(True), outputs=[ask_btn, question], queue=False)
            )

        _bind(ask_btn.click)
        _bind(question.submit)

    return demo
