from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

app = FastAPI()

STORAGE_DIR = os.environ.get("STORAGE_DIR", "/data")
STORAGE_FILE = os.path.join(STORAGE_DIR, "store.txt")


def ensure_storage_dir():
    os.makedirs(STORAGE_DIR, exist_ok=True)


class SaveRequest(BaseModel):
    content: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "py-app"}


@app.post("/save")
def save(body: SaveRequest):
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="'content' must not be empty")

    ensure_storage_dir()

    with open(STORAGE_FILE, "a") as f:
        f.write(body.content + "\n")
    print("hola clase")
    return {"message": "Content saved", "file": STORAGE_FILE}


@app.get("/read")
def read():
    ensure_storage_dir()

    if not os.path.exists(STORAGE_FILE):
        return {"content": [], "file": STORAGE_FILE}

    with open(STORAGE_FILE, "r") as f:
        lines = [line.rstrip("\n") for line in f.readlines() if line.strip()]

    return {"content": lines, "file": STORAGE_FILE}
