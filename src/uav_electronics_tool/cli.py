import typer
from rich import print

app = typer.Typer(help="UAV Electronics Component Selection Tool", no_args_is_help=True)

@app.callback()
def main() -> None:
    """
    UAV Electronics Component Selection Tool.
    """
    pass

def hello() -> None:
    print("[bold green]Tool is running![/bold green] [OK]")

# Explicit registration (no decorator magic)
app.command("hello")(hello)