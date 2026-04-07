from datetime import datetime
from pydantic import BaseModel


class KpReading(BaseModel):
    timestamp: datetime
    kp: float
    source: str        # "gfz" or "noaa"
    status: str | None = None  # "def", "prov", "real-time"


class KpResponse(BaseModel):
    readings: list[KpReading]
    fetched_at: datetime


def kp_to_color(kp: float) -> str:
    """Return a named color class for a KP value (used by both web CSS and TUI)."""
    if kp < 3:
        return "quiet"
    if kp < 4:
        return "unsettled"
    if kp < 5:
        return "active"
    if kp < 6:
        return "minor"
    if kp < 7:
        return "moderate"
    if kp < 8:
        return "strong"
    if kp < 9:
        return "severe"
    return "extreme"


def kp_to_storm_label(kp: float) -> str:
    """Short storm level label."""
    if kp < 3:
        return "Ruhig"
    if kp < 4:
        return "Unruhig"
    if kp < 5:
        return "Aktiv"
    if kp < 6:
        return "G1 Kleiner Sturm"
    if kp < 7:
        return "G2 Mäßiger Sturm"
    if kp < 8:
        return "G3 Starker Sturm"
    if kp < 9:
        return "G4 Schwerer Sturm"
    return "G5 Extremer Sturm"


def kp_to_aurora_text(kp: float) -> str:
    """Human-readable aurora visibility hint for Germany."""
    if kp < 5:
        return "Kein Polarlicht in Deutschland sichtbar"
    if kp < 6:
        return "Sichtbar: Nordseeküste (~60°N)"
    if kp < 7:
        return "Sichtbar: Norddeutschland (~55°N)"
    if kp < 8:
        return "Sichtbar: Mitteldeutschland (~50°N)"
    return "Sichtbar: Ganz Deutschland"
