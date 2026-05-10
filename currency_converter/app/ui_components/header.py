"""
header.py – Top navigation bar: logo, app title, clock, and theme toggle.
"""

from __future__ import annotations

import time
import tkinter as tk
from typing import Callable

import customtkinter as ctk

from app.utils import friendly_timestamp


class Header(ctk.CTkFrame):
    """
    Slim top bar with:
    • Logo mark + app name on the left
    • Live UTC clock in the centre
    • Light/Dark toggle + 'Refresh' button on the right
    """

    def __init__(
        self,
        master,
        on_theme_toggle: Callable[[], None],
        on_refresh: Callable[[], None],
        **kwargs,
    ):
        super().__init__(master, height=56, corner_radius=0, **kwargs)
        self.pack_propagate(False)

        self._on_theme_toggle = on_theme_toggle
        self._on_refresh      = on_refresh

        self._build()
        self._tick()   # start the live clock

    # ── Layout ────────────────────────────────────────────────────

    def _build(self) -> None:
        # Left: logo + title
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=18, pady=8)

        ctk.CTkLabel(
            left,
            text="◈",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=("#1a6aff", "#4d9fff"),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            left,
            text="FX Pulse",
            font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            left,
            text="  Real-time Currency Converter",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
        ).pack(side="left", pady=(3, 0))

        # Centre: live clock
        self._clock_var = tk.StringVar(value="")
        centre = ctk.CTkFrame(self, fg_color="transparent")
        centre.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            centre,
            textvariable=self._clock_var,
            font=ctk.CTkFont(family="Courier New", size=12),
            text_color=("gray45", "gray65"),
        ).pack()

        # Right: theme toggle + refresh
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=18, pady=8)

        self._theme_btn = ctk.CTkButton(
            right,
            text="☾ Dark",
            width=84,
            height=30,
            corner_radius=15,
            font=ctk.CTkFont(size=12),
            command=self._toggle_theme,
            fg_color=("gray80", "gray25"),
            hover_color=("gray70", "gray35"),
            text_color=("gray20", "gray90"),
        )
        self._theme_btn.pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            right,
            text="⟳ Refresh",
            width=90,
            height=30,
            corner_radius=15,
            font=ctk.CTkFont(size=12),
            command=self._on_refresh,
            fg_color=("#1a6aff", "#2d7dff"),
            hover_color=("#0055e0", "#1a6aff"),
        ).pack(side="right")

    def _toggle_theme(self) -> None:
        self._on_theme_toggle()
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            self._theme_btn.configure(text="☀ Light")
        else:
            self._theme_btn.configure(text="☾ Dark")

    # ── Live clock ────────────────────────────────────────────────

    def _tick(self) -> None:
        self._clock_var.set(friendly_timestamp())
        self.after(30_000, self._tick)   # update every 30 s

    def set_status(self, text: str) -> None:
        """Override clock text temporarily (e.g. 'Fetching rates…')."""
        self._clock_var.set(text)
