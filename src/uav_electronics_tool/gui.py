from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from .recommend import Mission, recommend_system, save_system_recommendations
from .db import load_database, validate_db


def _open_folder(path: Path) -> None:
    try:
        os.startfile(str(path))  # Windows
    except Exception:
        messagebox.showinfo("Open folder", f"Saved at:\n{path.resolve()}")


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.master.title("UAV Electronics Tool (Full System)")
        self.master.geometry("980x650")
        self.master.minsize(900, 600)

        # Vars
        self.data_dir = tk.StringVar(value=str(Path("data")))
        self.out_dir = tk.StringVar(value=str(Path("outputs")))

        self.n_motors = tk.IntVar(value=4)
        self.mass_kg = tk.DoubleVar(value=2.0)
        self.tw = tk.DoubleVar(value=2.0)
        self.cells = tk.IntVar(value=6)
        self.v_nom = tk.StringVar(value="")  # optional
        self.top_n = tk.IntVar(value=5)

        self.grid(sticky="nsew")
        self._build_ui()

    def _build_ui(self) -> None:
        # Root grid: left panel + right panel
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        self.columnconfigure(0, weight=0)  # left
        self.columnconfigure(1, weight=1)  # right
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self)
        right = ttk.Frame(self)

        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew")

        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        # ---------- Inputs ----------
        inputs = ttk.LabelFrame(left, text="Mission Inputs", padding=10)
        inputs.grid(row=0, column=0, sticky="ew")
        left.columnconfigure(0, weight=1)

        def add_row(parent: ttk.LabelFrame, r: int, label: str, widget: tk.Widget) -> None:
            ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(0, 10), pady=4)
            widget.grid(row=r, column=1, sticky="ew", pady=4)
            parent.columnconfigure(1, weight=1)

        add_row(inputs, 0, "Motors (count)", ttk.Spinbox(inputs, from_=2, to=16, textvariable=self.n_motors, width=10))
        add_row(inputs, 1, "Mass (kg)", ttk.Entry(inputs, textvariable=self.mass_kg, width=12))
        add_row(inputs, 2, "T/W target", ttk.Entry(inputs, textvariable=self.tw, width=12))
        add_row(inputs, 3, "Battery (S)", ttk.Spinbox(inputs, from_=2, to=14, textvariable=self.cells, width=10))
        add_row(inputs, 4, "V_nom override (V)", ttk.Entry(inputs, textvariable=self.v_nom, width=12))
        add_row(inputs, 5, "Show top N", ttk.Spinbox(inputs, from_=1, to=50, textvariable=self.top_n, width=10))

        tip = ttk.Label(left, text="Tip: Leave V_nom blank to use 3.7V × S", foreground="#666")
        tip.grid(row=1, column=0, sticky="w", pady=(6, 10))

        # ---------- Directories ----------
        files = ttk.LabelFrame(left, text="Directories", padding=10)
        files.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        files.columnconfigure(1, weight=1)

        def browse_dir(var: tk.StringVar, title: str) -> None:
            p = filedialog.askdirectory(title=title)
            if p:
                var.set(p)

        ttk.Label(files, text="Data Folder").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(files, textvariable=self.data_dir).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(files, text="Browse", command=lambda: browse_dir(self.data_dir, "Select data folder")).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(files, text="Output Folder").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(files, textvariable=self.out_dir).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(files, text="Browse", command=lambda: browse_dir(self.out_dir, "Select outputs folder")).grid(row=1, column=2, padx=(8, 0), pady=4)

        # ---------- Actions ----------
        actions = ttk.LabelFrame(left, text="Actions", padding=10)
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)

        ttk.Button(actions, text="Validate DB", command=self.validate_db).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(actions, text="Recommend System", command=self.recommend).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(actions, text="Open Output Folder", command=self.open_output).grid(row=2, column=0, sticky="ew", pady=4)

        # ---------- Results ----------
        results = ttk.LabelFrame(right, text="Results", padding=10)
        results.grid(row=0, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)

        self.text = tk.Text(results, wrap="none", height=25)
        self.text.tag_configure("header", font=("Segoe UI", 10, "bold"), spacing1=10, spacing3=5)
        self.text.grid(row=0, column=0, sticky="nsew")

        y = ttk.Scrollbar(results, orient="vertical", command=self.text.yview)
        x = ttk.Scrollbar(results, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=y.set, xscrollcommand=x.set)

        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")

    def log(self, msg: str, tag=None) -> None:
        if tag:
            self.text.insert(tk.END, msg + "\n", (tag,))
        else:
            self.text.insert(tk.END, msg + "\n")
        self.text.see(tk.END)

    def validate_db(self) -> None:
        data_path = Path(self.data_dir.get())
        if not data_path.exists():
            messagebox.showerror("Validate DB", f"Folder not found: {data_path.resolve()}")
            return

        self.log(f"Scanning folder: {data_path.resolve()}", "header")
        db = load_database(data_path)
        
        any_fail = False
        for k, v in db.items():
            if v.empty:
                self.log(f"Warning: No valid data found for '{k}'")
                any_fail = True
            else:
                self.log(f"OK: {k} -> {len(v)} items loaded")

        if any_fail:
            messagebox.showwarning("Validate DB", "Some datasets are empty or not found. See Results.")
        else:
            messagebox.showinfo("Validate DB", "All datasets loaded successfully ✅")

    def recommend(self) -> None:
        try:
            self.text.delete("1.0", tk.END)
            v_nom_str = self.v_nom.get().strip()
            v_nom_val = float(v_nom_str) if v_nom_str else None

            mission = Mission(
                n_motors=int(self.n_motors.get()),
                mass_kg=float(self.mass_kg.get()),
                thrust_to_weight=float(self.tw.get()),
                battery_cells_s=int(self.cells.get()),
                voltage_nom_v=v_nom_val,
            )

            data_path = Path(self.data_dir.get())
            if not data_path.exists():
                messagebox.showerror("Recommend", f"Data folder not found:\n{data_path.resolve()}")
                return

            self.log("Loading datasets...", "header")
            db = load_database(data_path)
            
            if all(v.empty for v in db.values()):
                messagebox.showerror("Recommend", "Data folder is empty or invalid.")
                return

            self.log("Generating full system recommendations...", "header")
            sys_recs = recommend_system(db, mission)

            if sys_recs.is_empty:
                self.log("No components matched your mission constraints.")
                messagebox.showwarning("Recommend", "No components matched. Try lighter mass or different battery cells.")
                return

            out_path = Path(self.out_dir.get())
            save_system_recommendations(sys_recs, out_path)

            top_n = int(self.top_n.get())

            self.log(f"\nSaved recommendations to: {out_path.resolve()}")
            self.log(f"Inputs: mass={mission.mass_kg}kg, TW={mission.thrust_to_weight}, n_motors={mission.n_motors}, {mission.battery_cells_s}S\n")

            def display_result(df: pd.DataFrame, title: str, cols: list[str]):
                self.log(f"=== Top {min(top_n, len(df))} {title} ===", "header")
                if df.empty:
                    self.log(f"No suitable {title} found.\n")
                    return
                show = df.head(top_n)[[c for c in cols if c in df.columns]]
                self.log(show.to_string(index=False) + "\n")

            display_result(sys_recs.motors, "Motors", ["manufacturer", "model", "kv", "mass_g", "price_usd", "score"])
            display_result(sys_recs.escs, "ESCs", ["manufacturer", "model", "max_current_a", "voltage_max_v", "mass_g", "score"])
            display_result(sys_recs.batteries, "Batteries", ["manufacturer", "model", "cells_s", "capacity_mah", "c_rating", "mass_g", "score"])
            display_result(sys_recs.propellers, "Propellers", ["manufacturer", "model", "diameter_in", "pitch_in", "mass_g", "score"])

            messagebox.showinfo("Recommend", f"Saved component recommendations to:\n{out_path.resolve()}")

        except Exception as e:
            self.log(f"ERROR: {type(e).__name__}: {e}")
            messagebox.showerror("Recommend Error", f"{type(e).__name__}: {e}")

    def open_output(self) -> None:
        p = Path(self.out_dir.get())
        if not p.exists():
            messagebox.showwarning("Open Output", f"Folder not found:\n{p.resolve()}")
            return
        _open_folder(p)


def main() -> None:
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("vista")
    except Exception:
        pass
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()