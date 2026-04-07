# KP-Index Monitor — Aurora Watch

Echtzeit-Überwachung des geomagnetischen KP-Index für Deutschland. Zeigt an, ob und wo Polarlichter sichtbar sind — als Web-Dashboard oder Terminal-UI.

Daten: [GFZ Potsdam](https://kp.gfz.de) (historisch, CC BY 4.0) + [NOAA SWPC](https://www.swpc.noaa.gov) (Echtzeit). Kein API-Key erforderlich.

---

## KP-Skala (Deutschland)

| KP | Stufe | Sichtbarkeit |
|----|-------|-------------|
| 0–4 | Ruhig / Aktiv | Nicht sichtbar |
| 5 | G1 Kleiner Sturm | Nordseeküste (~60°N) |
| 6 | G2 Mäßiger Sturm | Norddeutschland (~55°N) |
| 7 | G3 Starker Sturm | Mitteldeutschland (~50°N) |
| 8–9 | G4–G5 Schwer/Extrem | Ganz Deutschland |

---

## Starten

### Voraussetzungen

Python 3.12+

```bash
pip install -r requirements.txt
```

### Web-Dashboard

```bash
python web.py
```

Öffne [http://localhost:8000](http://localhost:8000).

### Terminal-UI

```bash
python tui.py
```

| Taste | Aktion |
|-------|--------|
| `r` | Sofort aktualisieren |
| `1` / `3` / `7` | Zeitraum 24h / 3d / 7d |
| `q` | Beenden |

### Docker

```bash
docker build -t kp-monitor .
docker run -p 8000:8000 kp-monitor
```

---

## Projektstruktur

```
kp/             Gemeinsames Daten-Package (Web + TUI)
  models.py     Pydantic-Modelle, Hilfsfunktionen
  cache.py      TTL-Cache (kein externer Dependency)
  client.py     HTTP-Abruf von GFZ + NOAA, Merge-Logik
web/
  server.py     FastAPI-Backend (/api/kp/current, /api/kp/history)
  static/       Frontend (HTML, CSS, Chart.js)
tui.py          Textual Terminal-UI
web.py          Uvicorn-Launcher
Dockerfile      Docker-Deployment
```

## Lizenz

MIT
