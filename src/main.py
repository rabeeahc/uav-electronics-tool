import typer
from rich import print

app = typer.Typer(help="UAV Electronics Component Selection Tool")

@app.command()
def hello():
    print("[bold green]Tool is running![/bold green] ✅")