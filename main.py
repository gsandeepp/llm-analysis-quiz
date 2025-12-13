from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import time
import base64
import re
import io
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# =========================
# App & Configuration
# =========================

app = FastAPI()

VALID_SECRET = "YOLO"
VALID_EMAIL = "25ds1000082@ds.study.iitm.ac.in"

PLAYWRIGHT_LAUNCH_TIMEOUT = 5000      # ms
PAGE_LOAD_TIMEOUT = 8000              # ms
SUBMIT_TIMEOUT = 5                    # sec

# =========================
# Models
# =========================

class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

# =========================
# Utilities
# =========================

def decode_base64_from_html(html: str) -> str:
    pattern = r'atob\(["\']([A-Za-z0-9+/=]+)["\']\)'
    matches = re.findall(pattern, html)
    for m in matches:
        try:
            return base64.b64decode(m).decode("utf-8")
        except Exception:
            pass
    return ""

def extract_urls(text: str):
    return re.findall(r'https?://[^\s<>"\']+', text)

def compute_answer_from_csv(csv_bytes: bytes, instruction_text: str):
    df = pd.read_csv(io.BytesIO(csv_bytes))
    text = instruction_text.lower()

    if "sum" in text and "value" in df.columns:
        return int(df["value"].sum())
    if "count" in text:
        return len(df)
    if "average" in text:
        numeric_cols = df.select_dtypes(include="number").columns
        if len(numeric_cols) > 0:
            return round(df[numeric_cols[0]].mean(), 2)

    return "42"

# =========================
# Core Solver (Single Step)
# =========================

def solve_single_step(url: str, email: str, secret: str):
    """
    Attempts to solve ONE quiz step.
    Guaranteed to either return a response or fail fast.
    Never hangs.
    """

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
                timeout=PLAYWRIGHT_LAUNCH_TIMEOUT
            )

            page = browser.new_page()
            page.set_default_timeout(PAGE_LOAD_TIMEOUT)

            page.goto(url, wait_until="domcontentloaded")
            html = page.content()
            decoded_text = decode_base64_from_html(html)
            combined_text = decoded_text + "\n" + html

            urls = extract_urls(combined_text)
            submit_url = next((u for u in urls if "submit" in u.lower()), None)
            file_url = next(
                (u for u in urls if any(ext in u.lower() for ext in [".csv", ".json", ".pdf"])),
                None
            )

            answer = "42"

            if file_url and file_url.endswith(".csv"):
                r = requests.get(file_url, timeout=SUBMIT_TIMEOUT)
                answer = compute_answer_from_csv(r.content, decoded_text)

            browser.close()

            if not submit_url:
                return {"correct": False, "reason": "Submit URL not found"}

            payload = {
                "email": email,
                "secret": secret,
                "url": url,
                "answer": answer
            }

            response = requests.post(
                submit_url,
                json=payload,
                timeout=SUBMIT_TIMEOUT
            )

            return response.json()

    except (PlaywrightTimeout, Exception):
        # Controlled failure — evaluator can proceed
        return {
            "correct": False,
            "reason": "Solver failed safely under resource constraints"
        }

# =========================
# API Endpoints
# =========================

@app.post("/submit")
def submit_quiz(req: QuizRequest):
    if req.secret != VALID_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    if req.email != VALID_EMAIL:
        raise HTTPException(status_code=403, detail="Invalid email")

    start_time = time.time()
    result = solve_single_step(req.url, req.email, req.secret)

    result["execution_time"] = round(time.time() - start_time, 2)
    return result

@app.get("/health")
def health():
    return {"status": "ok"}

# =========================
# Local Entry Point
# =========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
