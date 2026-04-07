"""
KP-Index Monitor — Terminal UI
Run with: python tui.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Label, RichLog, Static
from textual_plotext import PlotextPlot

from kp.client import fetch_merged
from kp.models import KpReading, kp_to_aurora_text, kp_to_color, kp_to_storm_label

REFRESH_SECONDS = 180

# ─── Textual CSS ──────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: #070a12;
    layers: base overlay;
}

/* ── Layout ── */
#main-layout {
    height: 1fr;
    layout: horizontal;
}

#left-panel {
    width: 28;
    background: #0d1525;
    border-right: solid #1c2d48;
    padding: 1 1;
    align: center top;
}

#right-panel {
    width: 1fr;
    layout: vertical;
}

#chart-container {
    height: 1fr;
    background: #0d1525;
    border-bottom: solid #1c2d48;
    padding: 0;
}

#table-container {
    height: 12;
    background: #070a12;
    padding: 0 1;
}

#log-container {
    height: 3;
    background: #070a12;
    border-top: solid #1c2d48;
    padding: 0 1;
}

/* ── Left panel widgets ── */
#kp-title {
    text-align: center;
    color: #3d5a7a;
    text-style: bold;
    margin-bottom: 1;
    width: 100%;
}

#kp-big {
    text-align: center;
    text-style: bold;
    width: 100%;
    height: 5;
    content-align: center middle;
}

#kp-storm {
    text-align: center;
    text-style: bold;
    width: 100%;
    margin-top: 1;
}

#kp-aurora {
    text-align: center;
    color: #6b90b8;
    width: 100%;
    margin-top: 1;
}

#kp-source {
    text-align: center;
    color: #3d5a7a;
    width: 100%;
    margin-top: 1;
}

#kp-updated {
    text-align: center;
    color: #3d5a7a;
    width: 100%;
    margin-top: 1;
}

#kp-refresh {
    text-align: center;
    color: #3d5a7a;
    width: 100%;
    margin-top: 2;
}

/* ── KP color classes ── */
.kp-quiet     { color: #22c55e; }
.kp-unsettled { color: #84cc16; }
.kp-active    { color: #eab308; }
.kp-minor     { color: #f97316; }
.kp-moderate  { color: #ef4444; }
.kp-strong    { color: #dc2626; }
.kp-severe    { color: #b91c1c; }
.kp-extreme   { color: #7c3aed; }

/* ── Table ── */
DataTable {
    background: #070a12;
    color: #ddeeff;
    height: 100%;
}

DataTable > .datatable--header {
    background: #0d1525;
    color: #6b90b8;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #172540;
    color: #ddeeff;
}

/* ── Chart ── */
PlotextPlot {
    height: 100%;
    width: 100%;
}

/* ── Log ── */
RichLog {
    background: #070a12;
    color: #3d5a7a;
    height: 100%;
}

/* ── Header / Footer ── */
Header {
    background: #0d1525;
    color: #ddeeff;
    border-bottom: solid #1c2d48;
}

Footer {
    background: #0d1525;
    color: #3d5a7a;
    border-top: solid #1c2d48;
}
"""

ALL_COLOR_CLASSES = [
    "kp-quiet", "kp-unsettled", "kp-active", "kp-minor",
    "kp-moderate", "kp-strong", "kp-severe", "kp-extreme",
]


def _set_kp_class(widget: Static, color: str) -> None:
    for cls in ALL_COLOR_CLASSES:
        widget.remove_class(cls)
    widget.add_class(f"kp-{color}")


# ─── App ──────────────────────────────────────────────────────────────────────

class KpMonitorApp(App):
    """Aurora / KP-Index Monitor — Terminal UI."""

    TITLE = "KP-Index Monitor"
    SUB_TITLE = "Aurora Watch · Deutschland"
    CSS = CSS

    BINDINGS = [
        Binding("r", "refresh", "Aktualisieren", show=True),
        Binding("q", "quit", "Beenden", show=True),
        Binding("1", "set_range_1", "24h", show=False),
        Binding("3", "set_range_3", "3 Tage", show=False),
        Binding("7", "set_range_7", "7 Tage", show=False),
    ]

    days_back: reactive[int] = reactive(3)
    countdown: reactive[int] = reactive(REFRESH_SECONDS)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main-layout"):
            # ── Left panel: current KP ──
            with Vertical(id="left-panel"):
                yield Label("KP-INDEX", id="kp-title")
                yield Static("—", id="kp-big")
                yield Static("", id="kp-storm")
                yield Static("", id="kp-aurora")
                yield Static("", id="kp-source")
                yield Static("", id="kp-updated")
                yield Static("", id="kp-refresh")

            # ── Right panel: chart + table ──
            with Vertical(id="right-panel"):
                with Container(id="chart-container"):
                    yield PlotextPlot(id="kp-chart")
                with Container(id="table-container"):
                    yield DataTable(id="kp-table", cursor_type="row", zebra_stripes=True)

        with Container(id="log-container"):
            yield RichLog(id="status-log", highlight=True, markup=True, max_lines=3)

        yield Footer()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        table = self.query_one("#kp-table", DataTable)
        table.add_columns("Zeit (CET)", "KP", "Stufe", "Polarlicht-Sichtbarkeit")

        self.run_worker(self._refresh_data(), exclusive=True, name="initial_load")
        self.set_interval(1, self._tick_countdown)

    # ── Workers ───────────────────────────────────────────────────────────────

    async def _refresh_data(self) -> None:
        log = self.query_one("#status-log", RichLog)
        now = datetime.now().strftime("%H:%M:%S")
        log.write(f"[dim]{now}[/] Lade Daten... (letzten {self.days_back} Tage)")

        try:
            data = await fetch_merged(days_back=self.days_back)
        except Exception as exc:
            log.write(f"[red]Fehler:[/] {exc}")
            return

        if not data.readings:
            log.write("[yellow]Keine Daten verfügbar.[/]")
            return

        self._update_left_panel(data.readings[-1])
        self._update_chart(data.readings)
        self._update_table(data.readings)

        log.write(
            f"[green]OK[/] {len(data.readings)} Messwerte geladen "
            f"· Quelle: GFZ + NOAA"
        )
        self.countdown = REFRESH_SECONDS

    # ── UI Updates ────────────────────────────────────────────────────────────

    def _update_left_panel(self, latest: KpReading) -> None:
        kp = latest.kp
        color = kp_to_color(kp)

        big = self.query_one("#kp-big", Static)
        big.update(f"{kp:.1f}")
        _set_kp_class(big, color)

        storm = self.query_one("#kp-storm", Static)
        storm.update(kp_to_storm_label(kp))
        _set_kp_class(storm, color)

        self.query_one("#kp-aurora", Static).update(kp_to_aurora_text(kp))
        self.query_one("#kp-source", Static).update(f"Quelle: {latest.source.upper()}")

        local_ts = latest.timestamp.astimezone()
        self.query_one("#kp-updated", Static).update(
            local_ts.strftime("Stand: %d.%m.%Y %H:%M")
        )

    def _update_chart(self, readings: list[KpReading]) -> None:
        plot_widget = self.query_one("#kp-chart", PlotextPlot)
        plt = plot_widget.plt
        plt.clear_figure()

        if not readings:
            return

        # Show a reasonable number of bars for the terminal width
        recent = readings[-56:]
        total = len(recent)
        step = max(1, total // 14)  # label at most ~14 ticks

        times: list[str] = []
        for i, r in enumerate(recent):
            if i % step == 0:
                times.append(r.timestamp.astimezone().strftime("%d/%m %H:%M"))
            else:
                times.append("")

        values = [r.kp for r in recent]

        plt.bar(times, values, orientation="vertical", width=0.85)
        plt.title("KP-Index · Verlauf")
        plt.ylabel("KP")
        plt.ylim(0, 9)
        plt.theme("dark")
        plt.hline(5, "orange")   # G1 threshold
        plt.hline(7, "red")      # G3 threshold

        plot_widget.refresh()

    def _update_table(self, readings: list[KpReading]) -> None:
        table = self.query_one("#kp-table", DataTable)
        table.clear()

        for r in reversed(readings[-14:]):
            local_ts = r.timestamp.astimezone()
            table.add_row(
                local_ts.strftime("%d.%m.%Y %H:%M"),
                f"{r.kp:.2f}",
                kp_to_storm_label(r.kp),
                kp_to_aurora_text(r.kp),
            )

    # ── Countdown ─────────────────────────────────────────────────────────────

    def _tick_countdown(self) -> None:
        self.countdown -= 1
        m = self.countdown // 60
        s = self.countdown % 60
        label = f"[{m}:{s:02d}] Autom. Refresh" if m > 0 else f"[{s}s] Autom. Refresh"
        self.query_one("#kp-refresh", Static).update(label)

        if self.countdown <= 0:
            self.countdown = REFRESH_SECONDS
            self.run_worker(self._refresh_data(), exclusive=True, name="auto_refresh")

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self.run_worker(self._refresh_data(), exclusive=True, name="manual_refresh")

    def action_set_range_1(self) -> None:
        self.days_back = 1
        self.action_refresh()

    def action_set_range_3(self) -> None:
        self.days_back = 3
        self.action_refresh()

    def action_set_range_7(self) -> None:
        self.days_back = 7
        self.action_refresh()


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = KpMonitorApp()
    app.run()
