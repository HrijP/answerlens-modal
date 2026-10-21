# AnswerLens on Modal

Upload a photo or scan of a student's handwritten answer sheet. AnswerLens transcribes the handwriting and returns a structured assessment:

- **Transcription** of everything the student wrote
- **Assessment** of accuracy, completeness, clarity and depth
- **Score** out of 10
- **Feedback** for the student

It runs [Qwen2.5-VL-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) on a cloud GPU through [Modal](https://modal.com) and serves a Gradio web page at a public URL.

**NSF EiR Project · Jackson State University**

---

## What's in this repo

| File | Purpose |
|---|---|
| `modal_app.py` | The whole app: GPU setup, model loading, prompt, and web UI |
| `requirements.txt` | What you need installed **on your own computer** (just the Modal client) |
| `sample/handwritten_test.png` | A test answer sheet to try once it's running |

You don't install PyTorch or the model locally. Modal builds all of that in the cloud.

---

## Setup from scratch

You'll need about 15 minutes, plus a few minutes for the first model download.

### 1. Create the accounts

1. **Modal:** sign up at <https://modal.com/signup> (you can use your GitHub account).
2. **Add a payment method in Modal.** Go to <https://modal.com/settings>, open **Billing**, and add a card. **Modal won't run GPU apps without one**; deploying fails with `Please add a payment method to use A10G GPU functions.` You're billed only while the app is running (see [Costs](#costs)).
3. **Hugging Face:** sign up at <https://huggingface.co/join>, then create a token at <https://huggingface.co/settings/tokens> (**Create new token**, then **Read** type). Copy it somewhere safe. The model is public, so the token only speeds up downloads and avoids rate limits, but the app expects it to exist.

### 2. Install Python

You need Python 3.10 or newer.

- **Windows:** in PowerShell, run
  ```powershell
  winget install --id Python.Python.3.12 -e
  ```
  Then **close and reopen** PowerShell.
  Or download it from <https://www.python.org/downloads/> and tick **"Add python.exe to PATH"** in the installer.
- **macOS:** `brew install python`, or download it from python.org.
- **Linux:** usually already installed; check with `python3 --version`.

Check that it worked:

```bash
python --version
```

(On macOS and Linux, use `python3` wherever this guide says `python`.)

### 3. Get this code

Either click **Code**, then **Download ZIP**, on this GitHub page and unzip it, or with Git:

```bash
git clone https://github.com/HrijP/answerlens-modal.git
cd answerlens-modal
```

Run every command below from inside the `answerlens-modal` folder.

### 4. Install the Modal client

```bash
python -m pip install -r requirements.txt
```

### 5. Log in to Modal

```bash
python -m modal setup
```

A browser window opens. Approve the login, and it saves a token to your computer (`~/.modal.toml`). You only do this once per computer.

> This guide uses `python -m modal …` everywhere because on Windows the plain `modal` command often isn't on your PATH after installing. If `modal --version` works for you, you can use `modal …` instead.

### 6. Store your Hugging Face token in Modal

The app reads the token from a Modal **secret** named `huggingface`, so it never sits in the code. Replace `hf_xxx` with your token:

```bash
python -m modal secret create huggingface HF_TOKEN=hf_xxx
```

To change the token later, run the same command with `--force` on the end.

### 7. Deploy

```bash
python -m modal deploy modal_app.py
```

The first deploy builds the cloud environment (PyTorch, Transformers and so on), which takes a few minutes. When it finishes, it prints your URL:

```
✓ Created Function ui
    └── https://<your-workspace>--answerlens-ui.us-east.modal.run
✓ App deployed! 🎉
```

That URL is your app. Open it in any browser and share it with anyone.

### 8. Try it

1. Open the URL. The **first** page load can take 10–30 seconds while a container starts.
2. Upload `sample/handwritten_test.png` (or any photo of handwriting).
3. Click **Transcribe & Grade →**.

**The very first run takes several minutes.** The app downloads the model (about 16 GB) from Hugging Face into a Modal Volume called `answerlens-hf-cache`. That happens **once**; later runs reuse the cached copy.

---

## Cold starts: what to expect

| Situation | Roughly how long |
|---|---|
| Very first request ever (model download) | Several minutes |
| First request after the app has been idle (container starts, model loads from cache) | 1–2 minutes |
| Requests while the app is warm | About 10–30 seconds per image |

The app **shuts down after 5 minutes with no requests** (`scaledown_window=300` in `modal_app.py`). That saves money, but the next person waits for a cold start. Raise the number to stay warm longer.

---

## Costs

- You pay Modal for **A10G GPU time only while a container is running**, including the 5-minute idle window after the last request. Current prices are at <https://modal.com/pricing>.
- Modal includes some free monthly credit, which covers a fair amount of testing.
- Watch usage on your app's page: <https://modal.com/apps>, then **answerlens**.
- **The URL has no login.** Anyone with the link can run it on your GPU budget, so share it carefully.

---

## Everyday commands

```bash
# Redeploy after editing modal_app.py (same URL)
python -m modal deploy modal_app.py

# Watch live logs (errors, model loading)
python -m modal app logs answerlens

# Take the app offline (stops all billing; deploy again to bring it back)
python -m modal app stop answerlens

# Run a temporary dev copy that auto-reloads when you save the file
python -m modal serve modal_app.py
```

---

## Changing things

All of these are in `modal_app.py`:

- **The grading prompt:** edit `PROMPT`. Keep the `TRANSCRIPTION:`, `ASSESSMENT:`, `SCORE:` and `FEEDBACK:` labels; the app uses them to split the output into the four boxes.
- **GPU type:** `gpu="A10G"`. `"L40S"` or `"A100"` are faster and cost more. The 7B model needs at least about 20 GB of GPU memory.
- **Idle shutdown:** `scaledown_window=300` (in seconds).
- **Response length:** `max_new_tokens=1024`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Please add a payment method to use A10G GPU functions` | Add a card under Billing at <https://modal.com/settings> (step 1). |
| `Secret 'huggingface' not found` | Do step 6, using the exact name `huggingface`. |
| `modal : The term 'modal' is not recognized` | Use `python -m modal …` instead of `modal …`. |
| `Python was not found` (Windows) | Reinstall Python with "Add to PATH" ticked, or reopen PowerShell after installing with winget. |
| `Token missing` / not authenticated | Run `python -m modal setup` again. |
| Page loads, but the button spins for minutes | Normal on the first-ever run or after idle (see [Cold starts](#cold-starts-what-to-expect)). Check `python -m modal app logs answerlens`. |
| Score box empty, score shows inside Assessment | The model formatted its answer unusually; the full text is still in the other boxes. Try again or tighten `PROMPT`. |

---

## Notes on the model's output

Qwen2.5-VL transcribes clean handwriting well, but its grading can be wrong. In testing, it once called a correctly balanced chemical equation "unbalanced". Treat scores and feedback as a first pass for a teacher to review, not a final grade.
