import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kp.client import fetch_merged
from kp.models import kp_to_aurora_text, kp_to_color, kp_to_storm_label

log = logging.getLogger("kp.server")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm cache so the first web request is not cold
    try:
        await fetch_merged(days_back=7)
    except Exception:
        pass
    yield


app = FastAPI(title="KP-Index Monitor", lifespan=lifespan)


# --- API routes (must be defined BEFORE the static file mount) ---


@app.get("/api/kp/current")
async def get_current():
    """Returns the most recent KP reading."""
    try:
        data = await fetch_merged(days_back=2)
    except Exception as e:
        log.error("fetch_merged failed: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail=str(e))

    if not data.readings:
        raise HTTPException(status_code=404, detail="No data available")

    latest = data.readings[-1]
    return {
        "kp": latest.kp,
        "timestamp": latest.timestamp.isoformat(),
        "source": latest.source,
        "color": kp_to_color(latest.kp),
        "storm_label": kp_to_storm_label(latest.kp),
        "aurora_visibility": kp_to_aurora_text(latest.kp),
    }


@app.get("/api/kp/history")
async def get_history(days: int = 7):
    """Returns historical KP readings (1–30 days)."""
    days = min(max(days, 1), 30)
    try:
        data = await fetch_merged(days_back=days)
    except Exception as e:
        log.error("fetch_merged failed: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail=str(e))

    return {
        "readings": [
            {
                "timestamp": r.timestamp.isoformat(),
                "kp": r.kp,
                "source": r.source,
                "color": kp_to_color(r.kp),
            }
            for r in data.readings
        ],
        "fetched_at": data.fetched_at.isoformat(),
        "count": len(data.readings),
    }


# --- Static files and SPA fallback (must come AFTER API routes) ---

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve index.html for all non-API routes (SPA catch-all)."""
    return FileResponse(STATIC_DIR / "index.html")
