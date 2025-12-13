from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import requests
from playwright.sync_api import sync_playwright
import time
import base64
import pandas as pd
import io
import re
import concurrent.futures

app = FastAPI()

# ================= CONFIG =================
VALID_SECRET = "YOLO"
VALID_EMAIL = "25ds1000082@ds.study.iitm.ac.in"

MAX_TOTAL_TIME = 170  # stay safely under 180s
PAGE_TIMEOUT = 20000  # 20s per page

# ================= MODELS =================
class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

# ================= UTIL =================
def extract_decoded_text(html: str) -> str:
    pattern = r'atob\(["\']([A-Za-z0-9+/=]+)["\']\)'
    matches = re.findall(pattern, html)
    for m in matches:
        try:
            return base64.b64decode(m).decode("utf-8")
        except:
            pass
    return ""

def extract_urls(text: str):
    return re.findall(r'https?://[^\s<>"\']+', text)

# ================= CORE SOLVER =================
def solve_single_quiz(url, email, secret):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)

        page.goto(url, wait_until="networkidle")
        html = page.content()
        decoded = extract_decoded_text(html)
        combined = decoded + "\n" + html

        urls = extract_urls(combined)
        submit_url = next((u for u in urls if "submit" in u.lower()), None)
        file_url = next((u for u in urls if any(ext in u.lower() for ext in [".csv", ".pdf", ".json"])), None)

        answer = "42"  # default fallback

        if file_url and file_url.endswith(".csv"):
            r = requests.get(file_url, timeout=10)
            df = pd.read_csv(io.BytesIO(r.content))
            text = decoded.lower()

            if "sum" in text and "value" in df.columns:
                answer = int(df["value"].sum())
            elif "count" in text:
                answer = len(df)
            elif "average" in text:
                num_cols = df.select_dtypes(include="number").columns
                if len(num_cols) > 0:
                    answer = round(df[num_cols[0]].mean(), 2)

        browser.close()

        if not submit_url:
            return {"correct": False, "reason": "No submit URL found"}

        payload = {
            "email": email,
            "secret": secret,
            "url": url,
            "answer": answer
        }

        res = requests.post(submit_url, json=payload, timeout=10)
        return res.json()

# ================= MAIN ENDPOINT =================
@app.post("/submit")
def submit_quiz(req: QuizRequest):
    if req.secret != VALID_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    if req.email != VALID_EMAIL:
        raise HTTPException(status_code=403, detail="Invalid email")

    start = time.time()
    current_url = req.url
    last_response = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        while time.time() - start < MAX_TOTAL_TIME:
            future = executor.submit(
                solve_single_quiz,
                current_url,
                req.email,
                req.secret
            )

            result = future.result(timeout=60)
            last_response = result

            if not result.get("correct") and "url" not in result:
                return result

            if "url" not in result:
                return result

            current_url = result["url"]

    return {
        "correct": False,
        "reason": "Time limit exceeded",
        "last_response": last_response
    }

# ================= HEALTH =================
@app.get("/health")
def health():
    return {"status": "ok"}

# ================= LOCAL RUN =================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
