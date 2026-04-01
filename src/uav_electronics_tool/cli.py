from pathlib import Path
import typer
from rich import print
import pandas as pd

from .recommend import Mission, recommend_system, save_system_recommendations
from .db import load_database, validate_db

app = typer.Typer(help="UAV Electronics Component Selection Tool", no_args_is_help=True)

@app.callback()
def main() -> None:
    """
    UAV Electronics Component Selection Tool.
    """
    pass

def hello() -> None:
    print("[bold green]Tool is running![/bold green] [OK]")

app.command("hello")(hello)

def recommend(
    n_motors: int = typer.Option(4, help="Number of motors (4 for quad, 6 for hex, etc.)"),
    mass_kg: float = typer.Option(2.0, help="All-up mass (kg)"),
    tw: float = typer.Option(2.0, help="Target thrust-to-weight ratio (e.g., 2.0)"),
    cells: int = typer.Option(6, help="Battery cell count (S), e.g., 4, 6"),
    v_nom: float = typer.Option(None, help="Nominal voltage override (V). If omitted, uses 3.7V*S"),
    data_dir: str = typer.Option("data", help="Path to data directory containing all component CSVs"),
    out_dir: str = typer.Option("outputs", help="Output directory path"),
    top: int = typer.Option(5, help="How many top results to print per component"),
) -> None:
    mission = Mission(
        n_motors=n_motors,
        mass_kg=mass_kg,
        thrust_to_weight=tw,
        battery_cells_s=cells,
        voltage_nom_v=v_nom,
    )

    print(f"[bold blue]Loading database from {data_dir}...[/bold blue]")
    db = load_database(Path(data_dir))
    
    if all(v.empty for v in db.values()):
        print("[red]Database is completely empty. Did you provide the right data_dir?[/red]")
        raise typer.Exit(1)
        
    print("[bold blue]Generating system recommendations...[/bold blue]")
    sys_recs = recommend_system(db, mission)

    if sys_recs.is_empty:
        print("[red]No components matched constraints.[/red] Try relaxing mission requirements.")
        raise typer.Exit(1)

    save_system_recommendations(sys_recs, Path(out_dir))

    print(f"[bold green]Saved recommendations to:[/bold green] {Path(out_dir).resolve()}")
    
    def print_top(df: pd.DataFrame, title: str, cols: list[str]):
        if df.empty:
            print(f"[yellow]No suitable {title} found.[/yellow]")
            return
        print(f"\n[bold underline]Top {min(top, len(df))} {title}[/bold underline]:")
        cols = [c for c in cols if c in df.columns]
        print(df.head(top)[cols].to_string(index=False))

    print_top(sys_recs.motors, "Motors", ["manufacturer", "model", "kv", "mass_g", "price_usd", "score"])
    print_top(sys_recs.escs, "ESCs", ["manufacturer", "model", "max_current_a", "voltage_max_v", "mass_g", "score"])
    print_top(sys_recs.batteries, "Batteries", ["manufacturer", "model", "cells_s", "capacity_mah", "c_rating", "mass_g", "score"])
    print_top(sys_recs.propellers, "Propellers", ["manufacturer", "model", "diameter_in", "pitch_in", "mass_g", "score"])

app.command("recommend")(recommend)

import sys

@app.command("validate-db")
def validate() -> None:
    print("[bold green]Validating database...[/bold green]")
    sys.exit(validate_db()) 