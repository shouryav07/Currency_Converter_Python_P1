"""
converter_card.py – The hero conversion widget.

Features
────────
• Two currency selectors (dropdowns with flag + code)
• Amount entry with real-time conversion as-you-type
• Swap button with a brief rotation animation
• Rate badge showing live rate + % change vs yesterday
• Green/Red trend indicator
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from app.utils import (
    CURRENCY_INFO,
    convert,
    format_amount,
    format_rate,
    pct_label,
    rate_change_pct,
    short_label,
    trend_direction,
)


class ConverterCard(ctk.CTkFrame):
    """
    Main conversion card.  Signals the rest of the app via callbacks:
      on_pair_change(from_code, to_code)   – user picked new currencies
      on_amount_change(from_code, to_code, amount) – user typed an amount
    """

    CURRENCIES = list(CURRENCY_INFO.keys())

    def __init__(
        self,
        master,
        on_pair_change: Callable[[str, str], None],
        on_amount_change: Callable[[str, str, float], None],
        **kwargs,
    ):
        super().__init__(master, corner_radius=16, **kwargs)

        self._on_pair_change   = on_pair_change
        self._on_amount_change = on_amount_change

        self._from_var   = tk.StringVar(value="USD")
        self._to_var     = tk.StringVar(value="EUR")
        self._amount_var = tk.StringVar(value="1")
        self._result_var = tk.StringVar(value="—")
        self._rate_var   = tk.StringVar(value="1 USD = — EUR")
        self._pct_var    = tk.StringVar(value="")
        self._offline    = False

        self._last_rate:     Optional[float] = None
        self._prev_rate:     Optional[float] = None
        self._swap_angle:    int             = 0

        self._build()
        self._bind_trace()

    # ── UI Construction ────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # Title row
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 4))

        ctk.CTkLabel(
            title_row,
            text="Currency Converter",
            font=ctk.CTkFont(family="Georgia", size=16, weight="bold"),
        ).pack(side="left")

        self._offline_badge = ctk.CTkLabel(
            title_row,
            text="  OFFLINE  ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#cc3300",
            text_color="white",
            corner_radius=6,
        )
        # (shown only when offline)

        # ── FROM section ──────────────────────────────────────────
        from_frame = ctk.CTkFrame(self, fg_color="transparent")
        from_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 4))
        from_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            from_frame,
            text="FROM",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray55"),
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        self._from_menu = ctk.CTkOptionMenu(
            from_frame,
            values=[short_label(c) for c in self.CURRENCIES],
            command=self._on_from_changed,
            width=160,
            height=40,
            corner_radius=10,
            font=ctk.CTkFont(size=14),
            dropdown_font=ctk.CTkFont(size=13),
            dynamic_resizing=False,
        )
        self._from_menu.set(short_label("USD"))
        self._from_menu.grid(row=1, column=0, sticky="w", pady=4)

        self._amount_entry = ctk.CTkEntry(
            from_frame,
            textvariable=self._amount_var,
            placeholder_text="Amount",
            font=ctk.CTkFont(size=22, weight="bold"),
            height=48,
            corner_radius=10,
            justify="right",
            border_width=2,
        )
        self._amount_entry.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)

        # ── Swap button ───────────────────────────────────────────
        swap_row = ctk.CTkFrame(self, fg_color="transparent")
        swap_row.grid(row=2, column=0, sticky="ew", padx=20, pady=2)

        # Divider lines flanking the swap button
        div_l = ctk.CTkFrame(swap_row, height=1, fg_color=("gray80", "gray30"))
        div_l.pack(side="left", fill="x", expand=True, pady=12)

        self._swap_btn = ctk.CTkButton(
            swap_row,
            text="⇅",
            width=38,
            height=38,
            corner_radius=19,
            font=ctk.CTkFont(size=18),
            command=self._swap_currencies,
            fg_color=("#1a6aff", "#2d7dff"),
            hover_color=("#0055e0", "#1a6aff"),
        )
        self._swap_btn.pack(side="left", padx=10)

        div_r = ctk.CTkFrame(swap_row, height=1, fg_color=("gray80", "gray30"))
        div_r.pack(side="left", fill="x", expand=True, pady=12)

        # ── TO section ────────────────────────────────────────────
        to_frame = ctk.CTkFrame(self, fg_color="transparent")
        to_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 4))
        to_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            to_frame,
            text="TO",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray55"),
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        self._to_menu = ctk.CTkOptionMenu(
            to_frame,
            values=[short_label(c) for c in self.CURRENCIES],
            command=self._on_to_changed,
            width=160,
            height=40,
            corner_radius=10,
            font=ctk.CTkFont(size=14),
            dropdown_font=ctk.CTkFont(size=13),
            dynamic_resizing=False,
        )
        self._to_menu.set(short_label("EUR"))
        self._to_menu.grid(row=1, column=0, sticky="w", pady=4)

        self._result_label = ctk.CTkLabel(
            to_frame,
            textvariable=self._result_var,
            font=ctk.CTkFont(size=26, weight="bold"),
            anchor="e",
        )
        self._result_label.grid(row=1, column=1, sticky="e", padx=(12, 0), pady=4)

        # ── Rate info bar ─────────────────────────────────────────
        info_bar = ctk.CTkFrame(self, fg_color=("gray92", "gray18"), corner_radius=10)
        info_bar.grid(row=4, column=0, sticky="ew", padx=20, pady=(10, 18))
        info_bar.grid_columnconfigure(0, weight=1)

        self._rate_label = ctk.CTkLabel(
            info_bar,
            textvariable=self._rate_var,
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray65"),
        )
        self._rate_label.grid(row=0, column=0, sticky="w", padx=14, pady=8)

        self._pct_label = ctk.CTkLabel(
            info_bar,
            textvariable=self._pct_var,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="gray",
        )
        self._pct_label.grid(row=0, column=1, sticky="e", padx=14, pady=8)

    # ── Traces & Callbacks ─────────────────────────────────────────

    def _bind_trace(self) -> None:
        """Watch the amount entry for real-time conversion."""
        self._amount_var.trace_add("write", self._on_amount_typed)

    def _on_amount_typed(self, *_) -> None:
        try:
            amount = float(self._amount_var.get().replace(",", ""))
        except ValueError:
            self._result_var.set("—")
            return
        if self._last_rate is not None:
            result = convert(amount, self._last_rate)
            to_code = self._get_code(self._to_var.get() or self._to_menu.get())
            self._result_var.set(format_amount(result, to_code))
        self._on_amount_change(
            self._get_code(self._from_menu.get()),
            self._get_code(self._to_menu.get()),
            amount,
        )

    def _on_from_changed(self, label: str) -> None:
        code = self._get_code(label)
        self._from_var.set(code)
        self._on_pair_change(code, self._get_code(self._to_menu.get()))

    def _on_to_changed(self, label: str) -> None:
        code = self._get_code(label)
        self._to_var.set(code)
        self._on_pair_change(self._get_code(self._from_menu.get()), code)

    def _swap_currencies(self) -> None:
        """Swap From ↔ To with a visual flash on the swap button."""
        from_code = self._get_code(self._from_menu.get())
        to_code   = self._get_code(self._to_menu.get())

        self._from_menu.set(short_label(to_code))
        self._to_menu.set(short_label(from_code))

        # Brief colour flash to give swap feedback
        self._swap_btn.configure(fg_color="#22cc88")
        self._swap_btn.after(250, lambda: self._swap_btn.configure(fg_color=("#1a6aff", "#2d7dff")))

        self._on_pair_change(to_code, from_code)

    # ── Public API (called by main controller) ─────────────────────

    def update_rate(
        self,
        rate: float,
        prev_rate: Optional[float],
        history_values: Optional[list[float]] = None,
    ) -> None:
        """Receive new rate data and refresh all display elements."""
        self._last_rate = rate
        self._prev_rate = prev_rate

        from_code = self._get_code(self._from_menu.get())
        to_code   = self._get_code(self._to_menu.get())

        # Rate label
        self._rate_var.set(
            f"1 {from_code} = {format_rate(rate)} {to_code}"
        )

        # Percentage change
        if prev_rate:
            pct = rate_change_pct(rate, prev_rate)
            label = pct_label(pct)
            if pct is not None and pct > 0:
                colour = "#22cc66"   # green
                label = f"▲ {label}"
            elif pct is not None and pct < 0:
                colour = "#ff4455"   # red
                label = f"▼ {label}"
            else:
                colour = ("gray50", "gray60")
            self._pct_label.configure(text=label, text_color=colour)
            self._pct_var.set("")     # we set directly, not via var
            self._pct_label.configure(text=label)
        else:
            self._pct_label.configure(text="")

        # Trend-colour on result
        direction = trend_direction(history_values) if history_values else "flat"
        colour_map = {"up": "#22cc66", "down": "#ff4455", "flat": ("gray20", "gray90")}
        self._result_label.configure(text_color=colour_map[direction])

        # Trigger result recalculation
        self._on_amount_typed()

    def set_offline(self, offline: bool) -> None:
        if offline:
            self._offline_badge.pack(side="right")
        else:
            self._offline_badge.pack_forget()

    def get_pair(self) -> tuple[str, str]:
        return (
            self._get_code(self._from_menu.get()),
            self._get_code(self._to_menu.get()),
        )

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _get_code(label: str) -> str:
        """Extract ISO code from a label like '🇺🇸 USD'."""
        parts = label.strip().split()
        for p in parts:
            if len(p) == 3 and p.isalpha() and p.isupper():
                return p
        return label[-3:].upper()   # last resort
