from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI

app = FastAPI(title="jesse-api", version="0.0.1")

_version_file = Path(__file__).parent / "version.txt"
SHA = _version_file.read_text().strip() if _version_file.exists() else "dev"


@app.get("/")
def root():
    return {"service": "jesse-api", "version": app.version, "sha": SHA}


@app.get("/v1/health")
def health():
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat(), "sha": SHA}
