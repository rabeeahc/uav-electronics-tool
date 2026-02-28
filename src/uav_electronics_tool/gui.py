from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from .recommend import Mission, load_motors_csv, recommend_motors, save_recommendations


def _open_file(path: Path) -> None:
    try:
        os.startfile(str(path))  # Windows
    except Exception:
        messagebox.showinfo("Open file", f"Saved at:\n{path.resolve()}")


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.master.title("UAV Electronics Tool (Multirotor)")
        self.master.geometry("980x600")
        self.master.minsize(900, 560)

        # Vars
        self.motors_csv = tk.StringVar(value=str(Path("data") / "motors.csv"))
        self.out_csv = tk.StringVar(value=str(Path("outputs") / "recommendations_motors.csv"))

        self.n_motors = tk.IntVar(value=4)
        self.mass_kg = tk.DoubleVar(value=2.2)
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
        inputs = ttk.LabelFrame(left, text="Inputs", padding=10)
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

        # ---------- Files ----------
        files = ttk.LabelFrame(left, text="Files", padding=10)
        files.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        files.columnconfigure(1, weight=1)

        def browse_in(var: tk.StringVar) -> None:
            p = filedialog.askopenfilename(title="Select CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
            if p:
                var.set(p)

        def browse_out(var: tk.StringVar) -> None:
            p = filedialog.asksaveasfilename(
                title="Save output CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if p:
                var.set(p)

        ttk.Label(files, text="motors.csv").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(files, textvariable=self.motors_csv).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(files, text="Browse", command=lambda: browse_in(self.motors_csv)).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(files, text="Output CSV").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(files, textvariable=self.out_csv).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(files, text="Browse", command=lambda: browse_out(self.out_csv)).grid(row=1, column=2, padx=(8, 0), pady=4)

        # ---------- Actions ----------
        actions = ttk.LabelFrame(left, text="Actions", padding=10)
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)

        ttk.Button(actions, text="Validate DB (scan data/*.csv)", command=self.validate_db).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(actions, text="Recommend Motors", command=self.recommend).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(actions, text="Open Output CSV", command=self.open_output).grid(row=2, column=0, sticky="ew", pady=4)

        # ---------- Results ----------
        results = ttk.LabelFrame(right, text="Results", padding=10)
        results.grid(row=0, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)

        self.text = tk.Text(results, wrap="none", height=20)
        self.text.grid(row=0, column=0, sticky="nsew")

        y = ttk.Scrollbar(results, orient="vertical", command=self.text.yview)
        x = ttk.Scrollbar(results, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=y.set, xscrollcommand=x.set)

        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")

    def log(self, msg: str) -> None:
        self.text.insert(tk.END, msg + "\n")
        self.text.see(tk.END)

    def validate_db(self) -> None:
        data_path = Path("data")
        if not data_path.exists():
            messagebox.showerror("Validate DB", f"Folder not found: {data_path.resolve()}")
            return

        csv_files = sorted(data_path.glob("*.csv"))
        if not csv_files:
            messagebox.showwarning("Validate DB", f"No CSV files found in: {data_path.resolve()}")
            return

        self.log(f"Scanning: {data_path.resolve()}")
        any_fail = False

        for f in csv_files:
            try:
                df = pd.read_csv(f)
                if df.shape[1] == 0:
                    self.log(f"BAD: {f.name} (no columns)")
                    any_fail = True
                else:
                    self.log(f"OK:  {f.name}  rows={len(df)} cols={df.shape[1]}")
            except Exception as e:
                self.log(f"ERR: {f.name} -> {type(e).__name__}: {e}")
                any_fail = True

        messagebox.showwarning("Validate DB", "Some CSV files have problems. See Results.") if any_fail else messagebox.showinfo("Validate DB", "All CSV files look readable ✅")

    def recommend(self) -> None:
        try:
            v_nom_str = self.v_nom.get().strip()
            v_nom_val = float(v_nom_str) if v_nom_str else None

            mission = Mission(
                n_motors=int(self.n_motors.get()),
                mass_kg=float(self.mass_kg.get()),
                thrust_to_weight=float(self.tw.get()),
                battery_cells_s=int(self.cells.get()),
                voltage_nom_v=v_nom_val,
            )

            motors_path = Path(self.motors_csv.get())
            if not motors_path.exists():
                messagebox.showerror("Recommend", f"motors.csv not found:\n{motors_path.resolve()}")
                return

            motors = load_motors_csv(motors_path)
            recs = recommend_motors(motors, mission)

            if recs.empty:
                self.log("No motors matched constraints. Try lower mass/TW or different cells.")
                messagebox.showwarning("Recommend", "No motors matched. See Results.")
                return

            out_path = Path(self.out_csv.get())
            save_recommendations(recs, out_path)

            top_n = int(self.top_n.get())
            show = recs.head(top_n)[["manufacturer", "model", "kv", "mass_g", "price_usd", "power_margin", "current_margin", "score"]]

            self.log("")
            self.log("=== Recommend Motors ===")
            self.log(f"Saved: {out_path.resolve()}")
            self.log(f"Inputs: motors={mission.n_motors}, mass={mission.mass_kg}kg, TW={mission.thrust_to_weight}, S={mission.battery_cells_s}, Vnom={mission.voltage_nom_v or 'auto'}")
            self.log("")
            self.log(show.to_string(index=False))
            self.log("")

            messagebox.showinfo("Recommend", f"Saved recommendations to:\n{out_path.resolve()}")

        except Exception as e:
            self.log(f"ERROR: {type(e).__name__}: {e}")
            messagebox.showerror("Recommend", f"{type(e).__name__}: {e}")

    def open_output(self) -> None:
        p = Path(self.out_csv.get())
        if not p.exists():
            messagebox.showwarning("Open Output", f"Output not found:\n{p.resolve()}")
            return
        _open_file(p)


def main() -> None:
    root = tk.Tk()
    # Slightly nicer default spacing on Windows
    style = ttk.Style()
    try:
        style.theme_use("vista")
    except Exception:
        pass
    App(root)
    root.mainloop()