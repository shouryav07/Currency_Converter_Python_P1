"""
main.py – FX Pulse: Real-time Currency Converter
─────────────────────────────────────────────────
Entry point and main controller.  Owns the window, orchestrates all
UI components, and routes data between the API client and the widgets.

Layout (left → right):
┌──────────────────────────────────────────────────────┐
│                     HEADER BAR                        │
├──────────┬──────────────────────┬────────────────────┤
│          │   CONVERTER CARD     │                    │
│ SIDEBAR  │  (hero input area)   │   TREND GRAPH      │
│ (quick   │──────────────────────│   (Matplotlib)     │
│  pairs)  │   RATE DETAILS       │                    │
│          │   (info strip)       │                    │
└──────────┴──────────────────────┴────────────────────┘
"""

from __future__ import annotations

import sys
import os
import tkinter as tk
from pathlib import Path
from typing import Optional

# ── Path fix so `app.*` imports work when running from project root ──────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import customtkinter as ctk

from app.api_client import async_fetch_rates, async_fetch_history, get_rate
from app.ui_components.header        import Header
from app.ui_components.converter_card import ConverterCard
from app.ui_components.trend_graph   import TrendGraph
from app.ui_components.sidebar       import Sidebar
from app.utils import (
    TIMEFRAME_DAYS,
    POPULAR_PAIRS,
    trend_direction,
    friendly_timestamp,
)


# ── Global appearance defaults ───────────────────────────────────────────────
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class FXPulseApp(ctk.CTk):
    """Top-level application window and controller."""

    WINDOW_TITLE = "FX Pulse – Real-time Currency Converter"
    MIN_W, MIN_H = 1020, 660

    def __init__(self):
        super().__init__()

        self.title(self.WINDOW_TITLE)
        self.minsize(self.MIN_W, self.MIN_H)
        self.geometry(f"{self.MIN_W}x{self.MIN_H}")
        self._center_window()

        # App state
        self._rates_cache:   Optional[dict] = None
        self._current_from   = "USD"
        self._current_to     = "EUR"
        self._current_tf_key = "1W"
        self._current_days   = TIMEFRAME_DAYS["1W"]

        # ── Build layout ─────────────────────────────────────────
        self._build_layout()

        # ── Wire timeframe events from the graph ─────────────────
        self._graph._canvas.get_tk_widget().bind("<<TimeframeChanged>>", self._on_timeframe_event)

        # ── Initial data load ────────────────────────────────────
        self.after(200, self._initial_load)

    # ── Window helpers ────────────────────────────────────────────

    def _center_window(self) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - self.MIN_W) // 2
        y  = (sh - self.MIN_H) // 2
        self.geometry(f"{self.MIN_W}x{self.MIN_H}+{x}+{y}")

    # ── Layout construction ───────────────────────────────────────

    def _build_layout(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        # ── Header (full width, row 0) ────────────────────────────
        self._header = Header(
            self,
            on_theme_toggle=self._toggle_theme,
            on_refresh=self._refresh,
            fg_color=("gray90", "gray12"),
        )
        self._header.grid(row=0, column=0, columnspan=3, sticky="ew")

        # Thin separator line
        sep = ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray20"), corner_radius=0)
        sep.grid(row=1, column=0, columnspan=3, sticky="new")

        # ── Sidebar (col 0) ───────────────────────────────────────
        self._sidebar = Sidebar(
            self,
            on_pair_selected=self._on_sidebar_pair_selected,
            fg_color=("gray94", "gray10"),
        )
        self._sidebar.grid(row=1, column=0, sticky="nsw", rowspan=1)

        # Thin vertical separator
        vsep = ctk.CTkFrame(self, width=1, fg_color=("gray80", "gray20"), corner_radius=0)
        vsep.grid(row=1, column=1, sticky="ns")

        # ── Centre panel (col 2): converter + rate strip ──────────
        centre = ctk.CTkFrame(self, fg_color="transparent")
        centre.grid(row=1, column=2, sticky="nsew", padx=0)
        centre.grid_rowconfigure(0, weight=1)
        centre.grid_columnconfigure(0, weight=1)
        centre.grid_columnconfigure(1, weight=2)

        # Converter card
        self._converter = ConverterCard(
            centre,
            on_pair_change=self._on_pair_change,
            on_amount_change=self._on_amount_change,
            fg_color=("gray96", "gray14"),
        )
        self._converter.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)

        # Trend graph
        self._graph = TrendGraph(
            centre,
            fg_color=("gray96", "gray14"),
        )
        self._graph.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)

    # ── Data loading ──────────────────────────────────────────────

    def _initial_load(self) -> None:
        """Called once after the window is shown."""
        self._header.set_status("Fetching live rates…")
        self._graph.show_loading()
        self._fetch_rates(self._current_from)
        self._fetch_history(self._current_from, self._current_to)

    def _fetch_rates(self, base: str) -> None:
        """Async rate fetch; result delivered to _on_rates_received."""
        async_fetch_rates(base, lambda r: self.after(0, self._on_rates_received, r))

    def _fetch_history(self, from_code: str, to_code: str) -> None:
        """Async history fetch; result delivered to _on_history_received."""
        self._graph.show_loading()
        async_fetch_history(
            from_code,
            to_code,
            self._current_days,
            lambda df: self.after(0, self._on_history_received, df, from_code, to_code),
        )

    # ── Callbacks (always run on main thread via after()) ─────────

    def _on_rates_received(self, rates: Optional[dict]) -> None:
        """Update UI once rates have been fetched."""
        self._header.set_status(friendly_timestamp())

        if rates is None:
            self._converter.set_offline(True)
            return

        self._rates_cache = rates
        self._converter.set_offline(False)

        # Update converter card with new rate
        rate = rates.get(self._current_to)
        if rate:
            # Use yesterday-ish approximation: we don't have a direct prev_rate
            # from the snapshot, so we store it from the last fetch when possible.
            self._converter.update_rate(rate, None)

        # Bulk-update sidebar with popular pairs
        bulk: dict = {}
        for from_c, to_c in POPULAR_PAIRS:
            if from_c == self._current_from and to_c in rates:
                r = rates[to_c]
                bulk[(from_c, to_c)] = (r, "flat")
        self._sidebar.bulk_update(bulk)

    def _on_history_received(self, df, from_code: str, to_code: str) -> None:
        """Deliver historical OHLC to the chart."""
        if from_code != self._current_from or to_code != self._current_to:
            return   # stale response — ignore

        self._graph.update_data(df, from_code, to_code, self._current_days)

        # Update trend indicator and prev_rate using history
        if df is not None and not df.empty and len(df) >= 2:
            closes = df["close"].tolist()
            direction = trend_direction(closes)
            rate = closes[-1]
            prev = closes[-2]
            self._converter.update_rate(rate, prev, closes)

            # Update sidebar direction
            self._sidebar.update_rate(from_code, to_code, rate, direction)

    def _on_pair_change(self, from_code: str, to_code: str) -> None:
        """Called by ConverterCard when user picks new currencies."""
        self._current_from = from_code
        self._current_to   = to_code

        # Instant rate from cache if available
        if self._rates_cache and to_code in self._rates_cache:
            self._converter.update_rate(self._rates_cache[to_code], None)
        else:
            # Trigger a new rates fetch for the new base
            self._fetch_rates(from_code)

        # Always refresh history for the new pair
        self._fetch_history(from_code, to_code)

    def _on_amount_change(self, from_code: str, to_code: str, amount: float) -> None:
        """Called every keystroke; converter card handles display internally."""
        pass   # conversion math lives inside ConverterCard

    def _on_sidebar_pair_selected(self, from_code: str, to_code: str) -> None:
        """User clicked a quick-pair row in the sidebar."""
        self._current_from = from_code
        self._current_to   = to_code

        # Update the converter card menus
        from app.utils import short_label
        self._converter._from_menu.set(short_label(from_code))
        self._converter._to_menu.set(short_label(to_code))

        self._fetch_rates(from_code)
        self._fetch_history(from_code, to_code)

    def _on_timeframe_event(self, event) -> None:
        """Called when a timeframe button is clicked inside TrendGraph."""
        tf = self._graph.get_current_tf()
        self._current_tf_key = tf
        self._current_days   = TIMEFRAME_DAYS[tf]
        self._graph.set_timeframe(tf, self._current_days)
        # Refetch history at new resolution
        self._fetch_history(self._current_from, self._current_to)

    # ── Menu actions ──────────────────────────────────────────────

    def _toggle_theme(self) -> None:
        current = ctk.get_appearance_mode()
        new_mode = "Light" if current == "Dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
        self._graph.refresh_theme()

    def _refresh(self) -> None:
        self._header.set_status("Refreshing…")
        self._fetch_rates(self._current_from)
        self._fetch_history(self._current_from, self._current_to)


# ── Launch ────────────────────────────────────────────────────────

def main() -> None:
    app = FXPulseApp()
    app.mainloop()


if __name__ == "__main__":
    main()
