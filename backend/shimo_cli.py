#!/usr/bin/env python3
"""Shimo CLI - Interactive Cloud Cost Analysis Agent."""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from datetime import datetime

app = typer.Typer(help="Shimo - Cloud Cost Analysis Agent")
console = Console()


@app.command()
def chat(
    session_id: Optional[str] = typer.Option(
        None, "--session", help="Resume session by ID"
    ),
):
    """Start interactive chat session."""
    from backend.agents.shimo_agent import create_shimo_agent
    from backend.database import init_db

    init_db()

    if session_id:
        try:
            agent = create_shimo_agent(session_id)
            console.print(
                f"[bold green]✓[/bold green] Resumed session: {agent.session.name}"
            )
            console.print(f"[dim]{agent.get_context()}[/dim]")
        except ValueError as e:
            console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")
            return
    else:
        console.print("[bold cyan]Shimo Cloud Cost Agent[/bold cyan]")
        name = typer.prompt("Session name")

        console.print("\n[bold]Select cloud providers:[/bold]")
        cloud_providers = {}
        for provider in ["aws", "azure", "gcp", "digitalocean"]:
            if typer.confirm(
                f"Enable {provider.upper()}?",
                default=True if provider == "aws" else False,
            ):
                cloud_providers[provider] = True

        if not cloud_providers:
            console.print("[bold red]No cloud providers selected[/bold red]")
            return

        agent = create_shimo_agent()
        agent.create_session(name, cloud_providers)
        console.print(f"[bold green]✓[/bold green] Created session: {agent.session.id}")

    agent.initialize_agent()

    # Interactive loop
    console.print(
        "\n[bold cyan]Type your questions (or /help for commands):[/bold cyan]\n"
    )

    while True:
        try:
            query = typer.prompt("[cyan]Shimo[/cyan]")

            if query.startswith("/"):
                handle_command(agent, query)
            else:
                console.print("[dim]Analyzing...[/dim]", end=" ")
                result = agent.analyze(query)
                console.print("\r" + " " * 50 + "\r", end="")  # Clear

                if isinstance(result, dict):
                    if "error" in result:
                        console.print(f"[bold red]Error:[/bold red] {result['error']}")
                    else:
                        print_analysis(result)
                else:
                    console.print(result)

        except KeyboardInterrupt:
            console.print("\n[dim]Saving session...[/dim]")
            agent.db.commit()
            console.print("[green]Goodbye![/green]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")


@app.command()
def new():
    """Create new session."""
    from backend.agents.shimo_agent import create_shimo_agent
    from backend.database import init_db

    init_db()

    console.print("[bold cyan]Create New Session[/bold cyan]")
    name = typer.prompt(
        "Session name", default=f"Session-{datetime.now().strftime('%Y%m%d-%H%M')}"
    )

    console.print("\n[bold]Select cloud providers:[/bold]")
    cloud_providers = {}
    for provider in ["aws", "azure", "gcp", "digitalocean"]:
        if typer.confirm(
            f"Enable {provider.upper()}?", default=True if provider == "aws" else False
        ):
            cloud_providers[provider] = True

    if not cloud_providers:
        console.print("[bold red]No cloud providers selected[/bold red]")
        return

    agent = create_shimo_agent()
    session = agent.create_session(name, cloud_providers)

    console.print("\n[bold green]✓ Session created[/bold green]")
    console.print(f"  ID: [cyan]{session.id}[/cyan]")
    console.print(f"  Name: {session.name}")
    console.print(f"  Providers: {', '.join(cloud_providers.keys())}")


@app.command()
def sessions(
    limit: int = typer.Option(10, "--limit", help="Number of sessions to show"),
):
    """List active sessions."""
    from backend.agents.shimo_agent import create_shimo_agent
    from backend.database import init_db

    init_db()

    agent = create_shimo_agent()
    sessions_list = agent.list_sessions(limit)

    if not sessions_list:
        console.print("[dim]No active sessions[/dim]")
        return

    table = Table(title="Active Sessions")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Providers", style="yellow")
    table.add_column("Messages")
    table.add_column("Created")

    for s in sessions_list:
        providers = ", ".join([p.upper() for p in s["cloud_providers"].keys()])
        created = datetime.fromisoformat(s["created_at"]).strftime("%Y-%m-%d %H:%M")
        table.add_row(
            s["id"][:8], s["name"], providers, str(s["message_count"]), created
        )

    console.print(table)


@app.command()
def config():
    """Configure Shimo settings."""
    from backend.config import settings

    console.print("[bold cyan]Shimo Configuration[/bold cyan]\n")

    config_data = {
        "LLM Provider": settings.llm_provider,
        "LLM Model": getattr(settings, f"{settings.llm_provider}_model", ""),
        "AWS Region": settings.aws_region,
        "Azure Subscription": settings.azure_subscription_id[:8] + "..."
        if settings.azure_subscription_id
        else "Not configured",
        "GCP Project": settings.gcp_project_id or "Not configured",
        "DigitalOcean": "Configured"
        if settings.digitalocean_api_token
        else "Not configured",
    }

    for key, value in config_data.items():
        console.print(f"  {key}: [yellow]{value}[/yellow]")


@app.command()
def export(session_id: str = typer.Argument(..., help="Session ID to export")):
    """Export session to JSON."""
    from backend.agents.shimo_agent import create_shimo_agent
    from backend.database import init_db

    init_db()

    try:
        agent = create_shimo_agent(session_id)
        data = agent.export_session()

        console.print_json(data=data)

    except ValueError as e:
        console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")


@app.command()
def delete(session_id: str = typer.Argument(..., help="Session ID to delete")):
    """Archive session."""
    from backend.agents.shimo_agent import create_shimo_agent
    from backend.database import init_db

    init_db()

    try:
        if typer.confirm(f"Archive session {session_id}?"):
            agent = create_shimo_agent(session_id)
            agent.delete_session()
            console.print("[bold green]✓ Session archived[/bold green]")
    except ValueError as e:
        console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")


def handle_command(agent, command: str):
    """Handle slash commands."""
    cmd = command.strip("/").split()[0].lower()
    args = command.strip("/").split()[1:] if len(command.split()) > 1 else []

    if cmd == "help":
        console.print(
            Panel.fit(
                "[bold cyan]Available Commands[/bold cyan]\n"
                "/help          - Show this help\n"
                "/sessions      - List active sessions\n"
                "/compress      - Compress context (for long sessions)\n"
                "/export        - Export current session\n"
                "/config        - Show configuration\n"
                "/model [name]  - Switch LLM model\n"
                "/clouds [list] - Show/configure cloud providers\n"
                "/exit          - Exit Shimo"
            )
        )
    elif cmd == "sessions":
        sessions_list = agent.list_sessions(5)
        for s in sessions_list:
            console.print(f"  {s['id'][:8]}: {s['name']}")
    elif cmd == "compress":
        console.print("[dim]Compressing context...[/dim]", end=" ")
        summary = agent.compress_context()
        console.print("\r" + " " * 50 + "\r", end="")
        console.print(f"[green]✓[/green] {summary[:100]}...")
    elif cmd == "export":
        data = agent.export_session()
        console.print_json(data=data)
    elif cmd == "config":
        console.print(f"LLM: {agent.session.llm_provider}")
        console.print(f"Providers: {', '.join(agent.session.cloud_providers.keys())}")
    elif cmd == "model":
        if args:
            console.print("[yellow]Model switching not yet implemented[/yellow]")
        else:
            console.print(f"Current model: {agent.session.llm_provider}")
    elif cmd == "clouds":
        console.print(f"Enabled: {', '.join(agent.session.cloud_providers.keys())}")
    elif cmd == "exit":
        raise KeyboardInterrupt()
    else:
        console.print(f"[dim]Unknown command: {cmd}[/dim]")


def print_analysis(result: dict):
    """Pretty print analysis results."""
    if "services" in result:
        # Cost by service
        console.print("[bold cyan]Cost Breakdown[/bold cyan]")
        table = Table()
        table.add_column("Service", style="cyan")
        table.add_column("Cost", style="green", justify="right")

        for service, cost in sorted(
            result.get("services", {}).items(), key=lambda x: x[1], reverse=True
        )[:10]:
            table.add_row(service, f"${cost:,.2f}")

        table.add_row(
            "[bold]Total[/bold]", f"[bold]${result.get('total_cost', 0):,.2f}[/bold]"
        )
        console.print(table)

    if "daily_costs" in result:
        # Daily trend
        console.print("\n[bold cyan]Daily Trend[/bold cyan]")
        for item in result.get("daily_costs", [])[-7:]:
            cost = item.get("cost", 0)
            bar = "█" * int(cost / 100) if cost > 0 else ""
            console.print(f"  {item.get('date')}: {bar} ${cost:,.2f}")


if __name__ == "__main__":
    app()
