from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from playwright.sync_api import sync_playwright
import time
import base64
import pandas as pd
import io
import re

app = FastAPI()

# ================= CONFIG =================
VALID_SECRET = "YOLO"
VALID_EMAIL = "25ds1000082@ds.study.iitm.ac.in"

PAGE_TIMEOUT = 15000  # ms

# ================= MODELS =================
class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

# ================= HELPERS =================
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

# ================= SOLVER =================
def solve_quiz_once(url, email, secret):
    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = browser.new_page()
            page.set_default_timeout(PAGE_TIMEOUT)

            # SAFE LOAD (no hanging)
            page.goto(url, wait_until="domcontentloaded")

            html = page.content()
            decoded = extract_decoded_text(html)
            combined = decoded + "\n" + html

            urls = extract_urls(combined)
            submit_url = next((u for u in urls if "submit" in u.lower()), None)
            file_url = next((u for u in urls if any(ext in u.lower() for ext in [".csv", ".json", ".pdf"])), None)

            answer = "42"

            if file_url and file_url.endswith(".csv"):
                r = requests.get(file_url, timeout=8)
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

            if not submit_url:
                return {"correct": False, "reason": "Submit URL not found"}

            payload = {
                "email": email,
                "secret": secret,
                "url": url,
                "answer": answer
            }

            res = requests.post(submit_url, json=payload, timeout=10)
            return res.json()

    except Exception as e:
        return {"correct": False, "reason": str(e)}

    finally:
        if browser:
            browser.close()

# ================= API =================
@app.post("/submit")
def submit(req: QuizRequest):
    if req.secret != VALID_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    if req.email != VALID_EMAIL:
        raise HTTPException(status_code=403, detail="Invalid email")

    start = time.time()
    result = solve_quiz_once(req.url, req.email, req.secret)

    result["execution_time"] = round(time.time() - start, 2)
    return result

@app.get("/health")
def health():
    return {"status": "ok"}

# ================= LOCAL =================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
