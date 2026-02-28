from pathlib import Path
import typer
from rich import print
import pandas as pd

from .recommend import Mission, load_motors_csv, recommend_motors, save_recommendations

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
    motors_csv: str = typer.Option("data/motors.csv", help="Path to motors database CSV"),
    out_csv: str = typer.Option("outputs/recommendations_motors.csv", help="Output CSV path"),
    top: int = typer.Option(5, help="How many top results to print"),
) -> None:
    mission = Mission(
        n_motors=n_motors,
        mass_kg=mass_kg,
        thrust_to_weight=tw,
        battery_cells_s=cells,
        voltage_nom_v=v_nom,
    )

    motors = load_motors_csv(Path(motors_csv))
    recs = recommend_motors(motors, mission)

    if recs.empty:
        print("[red]No motors matched constraints.[/red] Try lowering mass/tw or using a different cell count.")
        raise typer.Exit(1)

    save_recommendations(recs, Path(out_csv))

    print(f"[bold green]Saved:[/bold green] {Path(out_csv).resolve()}")
    print(f"[bold]Top {min(top, len(recs))} motors:[/bold]")
    show = recs.head(top)[["manufacturer", "model", "kv", "mass_g", "price_usd", "power_margin", "current_margin", "score"]]
    print(show.to_string(index=False))


app.command("recommend")(recommend)

import sys
from uav_electronics_tool.db import validate_db

@app.command("validate-db")
def validate() -> None:
    print("[bold green]Validating database...[/bold green]")
    sys.exit(validate_db()) 