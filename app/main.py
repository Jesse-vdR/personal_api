from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(title="jesse-api", version="0.0.1")


@app.get("/")
def root():
    return {"service": "jesse-api", "version": app.version}


@app.get("/v1/health")
def health():
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}
