"""
sidebar.py – The "Quick Conversions" sidebar panel.

Shows popular currency pairs with live rates and a coloured trend arrow.
Clicking a pair selects it in the converter card.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from app.utils import POPULAR_PAIRS, format_rate, short_label


class Sidebar(ctk.CTkFrame):
    """
    Left sidebar listing popular currency pairs.
    `on_pair_selected(from_code, to_code)` is called when a row is clicked.
    """

    def __init__(
        self,
        master,
        on_pair_selected: Callable[[str, str], None],
        **kwargs,
    ):
        super().__init__(master, corner_radius=0, width=200, **kwargs)
        self.pack_propagate(False)

        self._on_pair_selected = on_pair_selected
        self._row_frames: list[ctk.CTkFrame] = []
        self._rate_labels: dict[tuple, ctk.CTkLabel] = {}
        self._arrow_labels: dict[tuple, ctk.CTkLabel] = {}

        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(
            self,
            text="QUICK PAIRS",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray55"),
        ).pack(anchor="w", padx=16, pady=(20, 8))

        for from_code, to_code in POPULAR_PAIRS:
            self._add_row(from_code, to_code)

        # Spacer
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # Bottom info
        ctk.CTkLabel(
            self,
            text="Rates via ExchangeRate-API\n& yfinance",
            font=ctk.CTkFont(size=9),
            text_color=("gray60", "gray50"),
            justify="center",
        ).pack(pady=12)

    def _add_row(self, from_code: str, to_code: str) -> None:
        pair = (from_code, to_code)

        row = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        row.pack(fill="x", padx=8, pady=2)

        # Hover highlight
        row.bind("<Enter>", lambda e, r=row: r.configure(fg_color=("gray88", "gray22")))
        row.bind("<Leave>", lambda e, r=row: r.configure(fg_color="transparent"))
        row.bind("<Button-1>", lambda e, f=from_code, t=to_code: self._on_pair_selected(f, t))

        # Pair label
        pair_lbl = ctk.CTkLabel(
            row,
            text=f"{from_code}/{to_code}",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        pair_lbl.pack(side="left", padx=(10, 0), pady=8)
        pair_lbl.bind("<Button-1>", lambda e, f=from_code, t=to_code: self._on_pair_selected(f, t))

        # Arrow
        arrow = ctk.CTkLabel(
            row,
            text="→",
            font=ctk.CTkFont(size=12),
            text_color=("gray60", "gray55"),
        )
        arrow.pack(side="right", padx=(0, 8))
        arrow.bind("<Button-1>", lambda e, f=from_code, t=to_code: self._on_pair_selected(f, t))

        # Rate
        rate_lbl = ctk.CTkLabel(
            row,
            text="—",
            font=ctk.CTkFont(size=12),
            text_color=("gray45", "gray60"),
            anchor="e",
        )
        rate_lbl.pack(side="right", padx=(0, 4))
        rate_lbl.bind("<Button-1>", lambda e, f=from_code, t=to_code: self._on_pair_selected(f, t))

        self._rate_labels[pair]  = rate_lbl
        self._arrow_labels[pair] = arrow
        self._row_frames.append(row)

    def update_rate(
        self,
        from_code: str,
        to_code: str,
        rate: float,
        direction: str = "flat",   # "up" | "down" | "flat"
    ) -> None:
        """Push a new rate + direction into the matching sidebar row."""
        pair = (from_code, to_code)
        if pair not in self._rate_labels:
            return

        self._rate_labels[pair].configure(text=format_rate(rate))

        arrow_map = {
            "up":   ("▲", "#22cc66"),
            "down": ("▼", "#ff4455"),
            "flat": ("→", ("gray60", "gray55")),
        }
        symbol, colour = arrow_map.get(direction, ("→", ("gray60", "gray55")))
        self._arrow_labels[pair].configure(text=symbol, text_color=colour)

    def bulk_update(self, rates_map: dict[tuple[str, str], tuple[float, str]]) -> None:
        """
        rates_map: { (from, to): (rate, direction) }
        Used for a mass-update after fetching all rates at startup.
        """
        for pair, (rate, direction) in rates_map.items():
            self.update_rate(pair[0], pair[1], rate, direction)
