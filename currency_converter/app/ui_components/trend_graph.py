"""
trend_graph.py – Embeds an interactive Matplotlib chart inside the CustomTkinter window.

Chart types
───────────
• Sparkline (line)   – default view for 1D / 1W
• Candlestick        – available for 1W / 1M when OHLC data exists

Timeframe toggle buttons (1D | 1W | 1M) are rendered as CTk buttons above
the chart canvas.  When the currency pair or timeframe changes, the chart
redraws without creating a new Matplotlib Figure (fast, flicker-free).
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional

import customtkinter as ctk
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import FancyBboxPatch

matplotlib.use("TkAgg")   # must be set before any other plt call

# Colour palette – synced with app theme
DARK_BG    = "#1c1c1e"
DARK_PANEL = "#2c2c2e"
LIGHT_BG   = "#f5f5f7"
LIGHT_PANEL= "#ffffff"

UP_COLOR   = "#22cc66"
DOWN_COLOR = "#ff4455"
FLAT_COLOR = "#4d9fff"
GRID_ALPHA = 0.12


def _theme_colors(mode: str) -> dict:
    dark = mode == "Dark"
    return {
        "bg":    DARK_BG    if dark else LIGHT_BG,
        "panel": DARK_PANEL if dark else LIGHT_PANEL,
        "text":  "#e5e5ea"  if dark else "#1c1c1e",
        "grid":  "#3a3a3c"  if dark else "#d1d1d6",
        "spine": "#3a3a3c"  if dark else "#c7c7cc",
    }


class TrendGraph(ctk.CTkFrame):
    """
    A self-contained chart widget.  Call `update_data(df, from_code, to_code)`
    to push new OHLC data; call `set_timeframe(tf)` to change the window.
    """

    TIMEFRAMES = ["1D", "1W", "1M"]

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=16, **kwargs)

        self._current_tf   = "1W"
        self._df: Optional[pd.DataFrame] = None
        self._from_code    = "USD"
        self._to_code      = "EUR"
        self._loading      = False

        self._build_controls()
        self._build_canvas()

    # ── UI Construction ────────────────────────────────────────────

    def _build_controls(self) -> None:
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(side="top", fill="x", padx=16, pady=(14, 6))

        ctk.CTkLabel(
            ctrl,
            text="Price Trend",
            font=ctk.CTkFont(family="Georgia", size=15, weight="bold"),
        ).pack(side="left")

        self._pair_label = ctk.CTkLabel(
            ctrl,
            text="USD / EUR",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60"),
        )
        self._pair_label.pack(side="left", padx=(10, 0), pady=(2, 0))

        # Timeframe toggle buttons (right-aligned)
        tf_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
        tf_frame.pack(side="right")

        self._tf_buttons: dict[str, ctk.CTkButton] = {}
        for tf in self.TIMEFRAMES:
            btn = ctk.CTkButton(
                tf_frame,
                text=tf,
                width=42,
                height=26,
                corner_radius=8,
                font=ctk.CTkFont(size=12),
                command=lambda t=tf: self._on_tf_click(t),
                fg_color=("gray80", "gray25"),
                hover_color=("gray70", "gray35"),
                text_color=("gray20", "gray90"),
            )
            btn.pack(side="left", padx=2)
            self._tf_buttons[tf] = btn

        self._set_tf_active("1W")

        # Loading label (shown while fetching)
        self._loading_label = ctk.CTkLabel(
            self,
            text="Loading chart data…",
            font=ctk.CTkFont(size=13),
            text_color=("gray50", "gray60"),
        )

    def _build_canvas(self) -> None:
        """Create the Matplotlib figure and embed it in the frame."""
        mode = ctk.get_appearance_mode()
        col  = _theme_colors(mode)

        self._fig, self._ax = plt.subplots(figsize=(6, 3.2), dpi=96)
        self._fig.patch.set_facecolor(col["panel"])
        self._ax.set_facecolor(col["panel"])

        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=(0, 14))
        self._canvas.get_tk_widget().configure(bg=col["panel"])

        self._draw_placeholder()

    # ── Data updates ──────────────────────────────────────────────

    def show_loading(self) -> None:
        self._loading = True
        self._loading_label.place(relx=0.5, rely=0.55, anchor="center")

    def hide_loading(self) -> None:
        self._loading = False
        self._loading_label.place_forget()

    def update_data(
        self,
        df: Optional[pd.DataFrame],
        from_code: str,
        to_code: str,
        days: int,
    ) -> None:
        """Receive new OHLC dataframe and redraw the chart."""
        self._df        = df
        self._from_code = from_code
        self._to_code   = to_code
        self._pair_label.configure(text=f"{from_code} / {to_code}")
        self.hide_loading()

        if df is None or df.empty:
            self._draw_no_data()
            return

        # Slice to the requested window
        df_slice = df.tail(days) if len(df) > days else df
        self._draw_chart(df_slice)

    def set_timeframe(self, tf: str, days: int) -> None:
        self._current_tf = tf
        self._set_tf_active(tf)
        if self._df is not None:
            df_slice = self._df.tail(days) if len(self._df) > days else self._df
            self._draw_chart(df_slice)

    def refresh_theme(self) -> None:
        """Called when user toggles light/dark mode."""
        mode = ctk.get_appearance_mode()
        col  = _theme_colors(mode)
        self._fig.patch.set_facecolor(col["panel"])
        self._ax.set_facecolor(col["panel"])
        self._canvas.get_tk_widget().configure(bg=col["panel"])
        if self._df is not None:
            self._draw_chart(self._df)
        else:
            self._draw_placeholder()

    # ── Drawing helpers ───────────────────────────────────────────

    def _draw_placeholder(self) -> None:
        self._ax.clear()
        mode = ctk.get_appearance_mode()
        col  = _theme_colors(mode)

        self._ax.set_facecolor(col["panel"])
        self._ax.text(
            0.5, 0.5,
            "Select a currency pair to see the trend",
            ha="center", va="center",
            transform=self._ax.transAxes,
            fontsize=11,
            color=col["text"],
            alpha=0.45,
        )
        self._ax.axis("off")
        self._fig.tight_layout(pad=1.0)
        self._canvas.draw_idle()

    def _draw_no_data(self) -> None:
        self._ax.clear()
        mode = ctk.get_appearance_mode()
        col  = _theme_colors(mode)

        self._ax.set_facecolor(col["panel"])
        self._ax.text(
            0.5, 0.5,
            "No historical data available\n(check your internet connection)",
            ha="center", va="center",
            transform=self._ax.transAxes,
            fontsize=11,
            color=col["text"],
            alpha=0.45,
        )
        self._ax.axis("off")
        self._fig.tight_layout(pad=1.0)
        self._canvas.draw_idle()

    def _draw_chart(self, df: pd.DataFrame) -> None:
        self._ax.clear()
        mode = ctk.get_appearance_mode()
        col  = _theme_colors(mode)

        self._ax.set_facecolor(col["panel"])
        self._fig.patch.set_facecolor(col["panel"])

        closes = df["close"].values
        first, last = closes[0], closes[-1]
        rising = last >= first
        line_color = UP_COLOR if rising else DOWN_COLOR

        # ── Sparkline area fill ───────────────────────────────────
        dates_num = mdates.date2num(df["date"].values)

        self._ax.plot(
            dates_num, closes,
            color=line_color,
            linewidth=2.0,
            solid_capstyle="round",
            zorder=3,
        )
        self._ax.fill_between(
            dates_num,
            closes,
            closes.min(),
            alpha=0.15,
            color=line_color,
            zorder=2,
        )

        # ── Candlestick overlay for 1W / 1M if enough data ────────
        if len(df) >= 5 and self._current_tf in ("1W", "1M"):
            self._draw_candlesticks(df, dates_num, col)

        # ── Start / End markers ───────────────────────────────────
        self._ax.scatter(
            [dates_num[0], dates_num[-1]],
            [closes[0],    closes[-1]],
            color=line_color,
            s=40,
            zorder=5,
        )

        # ── Annotations: last price ───────────────────────────────
        self._ax.annotate(
            f"{last:.4f}",
            xy=(dates_num[-1], closes[-1]),
            xytext=(8, 0),
            textcoords="offset points",
            fontsize=9,
            color=line_color,
            fontweight="bold",
            va="center",
        )

        # ── Axes formatting ───────────────────────────────────────
        self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        self._ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=7))
        plt.setp(self._ax.get_xticklabels(), rotation=0, fontsize=8, color=col["text"])
        plt.setp(self._ax.get_yticklabels(), fontsize=8, color=col["text"])

        for spine in self._ax.spines.values():
            spine.set_edgecolor(col["spine"])
            spine.set_linewidth(0.5)

        self._ax.grid(
            axis="y",
            color=col["grid"],
            linewidth=0.6,
            linestyle="--",
        )
        self._ax.set_xlabel("")
        self._ax.set_ylabel(
            f"{self._from_code}/{self._to_code}",
            fontsize=9,
            color=col["text"],
            alpha=0.6,
        )

        # Pair / timeframe watermark
        self._ax.text(
            0.02, 0.97,
            f"{self._from_code}/{self._to_code}  ·  {self._current_tf}",
            transform=self._ax.transAxes,
            fontsize=8,
            color=col["text"],
            alpha=0.35,
            va="top",
        )

        self._fig.tight_layout(pad=1.2)
        self._canvas.draw_idle()

    def _draw_candlesticks(
        self,
        df: pd.DataFrame,
        dates_num: np.ndarray,
        col: dict,
    ) -> None:
        """Draw OHLC candlesticks on top of the sparkline."""
        width = (dates_num[-1] - dates_num[0]) / len(dates_num) * 0.6

        for i, row in enumerate(df.itertuples()):
            o, h, l, c = row.open, row.high, row.low, row.close
            clr = UP_COLOR if c >= o else DOWN_COLOR

            # Wick (high-low line)
            self._ax.plot(
                [dates_num[i], dates_num[i]],
                [l, h],
                color=clr,
                linewidth=0.8,
                zorder=4,
            )

            # Body (open-close rectangle)
            body_bottom = min(o, c)
            body_height = abs(c - o) or 0.0001
            rect = FancyBboxPatch(
                (dates_num[i] - width / 2, body_bottom),
                width, body_height,
                boxstyle="square,pad=0",
                facecolor=clr,
                edgecolor=clr,
                alpha=0.7,
                linewidth=0,
                zorder=4,
            )
            self._ax.add_patch(rect)

    # ── Internal helpers ──────────────────────────────────────────

    def _on_tf_click(self, tf: str) -> None:
        """Delegate timeframe change upward via the parent's method."""
        # We fire an event that main.py listens to via after-hook
        self.event_generate("<<TimeframeChanged>>", when="tail")
        self._current_tf = tf
        self._set_tf_active(tf)
        # The controller in main.py will call set_timeframe() with the right days

    def _set_tf_active(self, active: str) -> None:
        for tf, btn in self._tf_buttons.items():
            if tf == active:
                btn.configure(
                    fg_color=("#1a6aff", "#2d7dff"),
                    text_color="white",
                )
            else:
                btn.configure(
                    fg_color=("gray80", "gray25"),
                    text_color=("gray20", "gray90"),
                )

    def get_current_tf(self) -> str:
        return self._current_tf
