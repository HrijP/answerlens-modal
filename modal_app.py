"""
AnswerLens – Handwriting Transcription & Assessment
Modal deployment (GPU) — Gradio UI served via ASGI
NSF Excellence in Research Project, Jackson State University
"""

import re

import modal

MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
CACHE_DIR = "/cache"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch==2.5.1",
        "torchvision==0.20.1",
        "transformers==4.51.3",
        "accelerate==1.6.0",
        "qwen-vl-utils==0.0.10",
        "gradio==5.23.3",
        "fastapi[standard]==0.115.12",
        "Pillow",
    )
    .env({"HF_HOME": CACHE_DIR})
)

app = modal.App("answerlens", image=image)

# Model weights are cached here so cold starts don't re-download ~16 GB.
hf_cache = modal.Volume.from_name("answerlens-hf-cache", create_if_missing=True)

PROMPT = """You are reviewing a scanned or photographed student answer sheet.

Step 1 – TRANSCRIPTION
Read every word the student wrote and transcribe it exactly, preserving structure (headings, numbered points, equations, diagrams described in words, etc.). Label this section "TRANSCRIPTION:".

Step 2 – ASSESSMENT
Evaluate the student's answer on:
• Accuracy      – Is the content correct? Identify specific errors.
• Completeness  – Did the student address all parts of the question?
• Clarity       – Is the writing legible and well-organised?
• Depth         – Does the answer show understanding beyond surface recall?
Label this section "ASSESSMENT:".

Step 3 – SCORE
Give a score out of 10 with a one-line justification. Label this "SCORE:".

Step 4 – FEEDBACK
Write 2–4 sentences of constructive feedback the student can act on. Label this "FEEDBACK:"."""


_HEADER = re.compile(
    r"^[\s#*]*(TRANSCRIPTION|ASSESSMENT|SCORE|FEEDBACK)[\s*]*:[\s*]*(.*)$", re.IGNORECASE
)


def _parse(raw: str) -> dict:
    keys = ["TRANSCRIPTION", "ASSESSMENT", "SCORE", "FEEDBACK"]
    out, current = {k: [] for k in keys}, None
    for line in raw.splitlines():
        m = _HEADER.match(line)
        if m:
            # Headers may carry content on the same line, e.g. "**SCORE:** 7/10"
            current = m.group(1).upper()
            if m.group(2).strip():
                out[current].append(m.group(2))
        elif current:
            out[current].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


@app.function(
    gpu="A10G",
    secrets=[modal.Secret.from_name("huggingface")],
    volumes={CACHE_DIR: hf_cache},
    timeout=900,
    scaledown_window=300,
    max_containers=1,  # Gradio needs sticky sessions
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def ui():
    import threading

    import gradio as gr
    import torch
    from fastapi import FastAPI
    from PIL import Image
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    state = {"processor": None, "model": None}
    lock = threading.Lock()

    def _load():
        with lock:
            if state["model"] is not None:
                return
            state["processor"] = AutoProcessor.from_pretrained(MODEL_ID)
            state["model"] = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                MODEL_ID,
                torch_dtype=torch.bfloat16,
                device_map="cuda",
            ).eval()
            hf_cache.commit()

    def run(img: Image.Image):
        if img is None:
            raise gr.Error("Please upload an image first.")
        _load()
        processor, model = state["processor"], state["model"]
        img = img.convert("RGB")
        msgs = [{"role": "user", "content": [
            {"type": "image", "image": img},
            {"type": "text", "text": PROMPT},
        ]}]
        text = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[img], return_tensors="pt").to("cuda")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=1024, do_sample=False)
        raw = processor.batch_decode(
            out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )[0]
        p = _parse(raw)
        return p["TRANSCRIPTION"] or raw, p["SCORE"], p["ASSESSMENT"], p["FEEDBACK"]

    with gr.Blocks(title="AnswerLens – Handwriting Assessment") as demo:
        gr.Markdown(
            "# 📝 AnswerLens\n"
            "AI-powered handwriting transcription and assessment · "
            "NSF Excellence in Research · Jackson State University\n\n"
            "_The first request after idle loads the model and can take a few minutes._"
        )
        with gr.Row(equal_height=False):
            with gr.Column(scale=1):
                image_in = gr.Image(type="pil", label="Upload answer sheet", height=360)
                grade_btn = gr.Button("Transcribe & Grade →", variant="primary")
            with gr.Column(scale=1):
                score_out = gr.Textbox(label="🏅 Score", lines=1, interactive=False)
                transcription_out = gr.Textbox(label="📄 Transcription", lines=10, interactive=False, show_copy_button=True)
                assessment_out = gr.Textbox(label="📊 Assessment", lines=6, interactive=False, show_copy_button=True)
                feedback_out = gr.Textbox(label="💬 Feedback for Student", lines=4, interactive=False, show_copy_button=True)

        grade_btn.click(
            fn=run,
            inputs=[image_in],
            outputs=[transcription_out, score_out, assessment_out, feedback_out],
            api_name="grade",
        )

    demo.queue(default_concurrency_limit=1)
    return gr.mount_gradio_app(app=FastAPI(), blocks=demo, path="/")
