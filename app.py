"""StudyMate AI - Streamlit user interface.

Run with:  streamlit run app.py
"""
import streamlit as st

from ai.model import ModelError, check_model_status
from config import HISTORY_CONTEXT_MESSAGES, MAX_FILE_SIZE_MB, MODEL_NAME
from database.db import clear_messages, init_db, load_messages, save_message
from services.chat import answer_general_question
from services.document_qa import answer_document_question
from services.pdf_handler import PDFError, process_pdf
from services.summarizer import summarize_document

AI_NOTICE = "AI-generated - may be inaccurate, please verify."
MODE_GENERAL = "General chat"
MODE_DOCUMENT = "Ask about PDF"

st.set_page_config(page_title="StudyMate AI", page_icon=":books:", layout="wide")


# ---------- session state & callbacks ----------

def init_session_state() -> None:
    defaults = {
        "document": None,
        "processed_file_id": None,
        "upload_error": None,
        "uploader_key": 0,
        "model_status": None,
        "flash": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def refresh_model_status() -> None:
    st.session_state.model_status = check_model_status()


def clear_document() -> None:
    st.session_state.document = None
    st.session_state.processed_file_id = None
    st.session_state.upload_error = None
    st.session_state.uploader_key += 1  # new key resets the file uploader widget
    st.session_state.flash = "Current document cleared."


def clear_history() -> None:
    clear_messages()
    st.session_state.flash = "Chat history cleared."


def handle_upload(uploaded_file) -> None:
    """Validate and extract a newly uploaded PDF (only once per file)."""
    file_id = f"{uploaded_file.name}-{uploaded_file.size}"
    if file_id == st.session_state.processed_file_id:
        return
    st.session_state.processed_file_id = file_id
    st.session_state.document = None
    st.session_state.upload_error = None
    with st.spinner("Reading PDF..."):
        try:
            st.session_state.document = process_pdf(uploaded_file.name, uploaded_file.getvalue())
        except PDFError as error:
            st.session_state.upload_error = str(error)


# ---------- rendering helpers ----------

def render_message(role: str, content: str, mode: str, timestamp: str | None = None) -> None:
    with st.chat_message(role):
        st.markdown(content)
        parts = ["Document" if mode == "document" else "General"]
        if timestamp:
            parts.append(timestamp)
        if role == "assistant":
            parts.append(AI_NOTICE)
        st.caption(" | ".join(parts))


def render_sidebar() -> None:
    with st.sidebar:
        st.header(":gear: Model status")
        if st.session_state.model_status is None:
            refresh_model_status()
        ready, message = st.session_state.model_status
        (st.success if ready else st.error)(message)
        st.button("Re-check connection", on_click=refresh_model_status)

        st.header(":page_facing_up: Study document")
        uploaded = st.file_uploader(
            f"Upload a text-based PDF (max {MAX_FILE_SIZE_MB} MB)",
            type=["pdf"],
            key=f"uploader_{st.session_state.uploader_key}",
        )
        if uploaded is not None:
            handle_upload(uploaded)

        if st.session_state.upload_error:
            st.error(st.session_state.upload_error)

        document = st.session_state.document
        if document:
            st.success(
                f"Loaded **{document['name']}** - {document['pages']} page(s), "
                f"{document['word_count']:,} words, {len(document['chunks'])} chunk(s)."
            )
            with st.expander("Preview extracted text"):
                preview = document["text"][:1500]
                st.text(preview + ("..." if len(document["text"]) > 1500 else ""))
        if document or st.session_state.upload_error:
            st.button("Clear current document", on_click=clear_document)

        st.header(":card_index_dividers: History")
        st.caption("Messages are saved locally and survive restarts.")
        st.button("Clear chat history", on_click=clear_history)


def render_history() -> None:
    messages = load_messages()
    if not messages:
        st.info("No messages yet. Ask a question below, or upload a PDF from the sidebar.")
    for message in messages:
        render_message(message["role"], message["content"], message["mode"], message["created_at"])


# ---------- actions ----------

def run_summary(document: dict) -> None:
    request = f"Summarize the document **{document['name']}**."
    save_message("user", request, "document")
    render_message("user", request, "document")

    with st.chat_message("assistant"):
        progress = st.empty()
        try:
            with st.spinner("Summarizing... local models can take a minute."):
                result = summarize_document(
                    document["text"],
                    on_progress=lambda done, total: progress.caption(
                        f"Reading section {done} of {total}..."
                    ),
                )
        except ModelError as error:
            progress.empty()
            st.error(f"Error: {error}")
            return
        progress.empty()

        summary = result["summary"]
        if result["truncated"]:
            summary += (
                f"\n\n_Note: this document is long, so only the first {result['sections_used']} "
                f"of {result['sections_total']} sections were summarized._"
            )
        st.markdown(summary)
        st.caption(f"Document | {AI_NOTICE}")
    save_message("assistant", summary, "document")


def format_document_answer(result: dict, document_name: str) -> str:
    if not result["sources"]:
        return result["answer"]
    excerpt_numbers = ", ".join(str(index + 1) for index, _ in result["sources"])
    return f"{result['answer']}\n\n_Source: {document_name}, excerpt(s) {excerpt_numbers}_"


def handle_prompt(prompt: str, mode_label: str, document: dict | None) -> None:
    question = prompt.strip()
    if not question:
        st.warning("Please type a question before sending.")
        return
    if mode_label == MODE_DOCUMENT and document is None:
        st.warning("Upload a PDF first (sidebar), or switch to General chat.")
        return

    mode = "document" if mode_label == MODE_DOCUMENT else "general"
    history = load_messages(limit=HISTORY_CONTEXT_MESSAGES * 2)
    save_message("user", question, mode)
    render_message("user", question, mode)

    result = None
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking... local models can be slow."):
                if mode == "general":
                    reply = answer_general_question(question, history)
                else:
                    result = answer_document_question(question, document["chunks"])
                    reply = format_document_answer(result, document["name"])
        except ModelError as error:
            st.error(f"Error: {error}")
            return

        st.markdown(reply)
        st.caption(f"{'Document' if mode == 'document' else 'General'} | {AI_NOTICE}")
        if result and result["sources"]:
            with st.expander("Show source excerpts used"):
                for index, chunk in result["sources"]:
                    st.markdown(f"**Excerpt {index + 1}**")
                    st.caption(chunk[:600] + ("..." if len(chunk) > 600 else ""))
    save_message("assistant", reply, mode)


# ---------- page ----------

def main() -> None:
    init_db()
    init_session_state()
    render_sidebar()

    st.title(":books: StudyMate AI")
    st.caption(f"Your local study assistant | {MODEL_NAME} via Ollama | {AI_NOTICE}")

    if st.session_state.flash:
        st.toast(st.session_state.flash)
        st.session_state.flash = None

    document = st.session_state.document
    col_mode, col_summary = st.columns([3, 1])
    with col_mode:
        mode_label = st.radio("Mode", [MODE_GENERAL, MODE_DOCUMENT], horizontal=True)
    with col_summary:
        summarize_clicked = st.button(
            "Summarize document",
            disabled=document is None,
            help="Upload a PDF to enable" if document is None else None,
        )

    render_history()

    if summarize_clicked and document:
        run_summary(document)

    placeholder = (
        "Ask a question about your PDF..." if mode_label == MODE_DOCUMENT
        else "Ask any academic question..."
    )
    prompt = st.chat_input(placeholder)
    if prompt is not None:
        handle_prompt(prompt, mode_label, document)


main()