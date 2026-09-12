#!/usr/bin/env python3
"""Shimo CLI - interactive, memory-aware multi-cloud cost analysis agent.

Run as ``shimo`` (installed entry point) or ``python backend/shimo_cli.py``.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import typer  # noqa: E402  pylint: disable=wrong-import-position
from rich.console import Console  # noqa: E402  pylint: disable=wrong-import-position
from rich.panel import Panel  # noqa: E402  pylint: disable=wrong-import-position
from rich.prompt import Confirm, Prompt  # noqa: E402  pylint: disable=wrong-import-position
from rich.table import Table  # noqa: E402  pylint: disable=wrong-import-position

from backend.config import SUPPORTED_CLOUD_PROVIDERS, SUPPORTED_LLM_PROVIDERS, settings  # noqa: E402  pylint: disable=wrong-import-position
from backend.database import init_db  # noqa: E402  pylint: disable=wrong-import-position

app = typer.Typer(help="Shimo - the CloudCost Analyzer agent for AWS, Azure, GCP and DigitalOcean", no_args_is_help=True, add_completion=False)
console = Console()

PROVIDER_LABELS = {"aws": "AWS", "azure": "Azure", "gcp": "GCP (Google Cloud)", "digitalocean": "DigitalOcean"}
LLM_LABELS = {
    "bedrock": "AWS Bedrock",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "anthropic": "Anthropic Claude",
    "ollama": "Ollama (local)",
    "unsloth": "Unsloth Studio",
}


# ----- helpers ------------------------------------------------------------------------


def _harness():
    from backend.agents.agent_harness import AgentHarness  # pylint: disable=import-outside-toplevel

    init_db()
    return AgentHarness()


def _parse_providers(value: str | None) -> list[str]:
    if not value:
        return []
    providers = [p.strip().lower() for p in value.split(",") if p.strip()]
    unknown = [p for p in providers if p not in SUPPORTED_CLOUD_PROVIDERS]
    if unknown:
        raise typer.BadParameter(f"Unknown provider(s): {', '.join(unknown)}. Choose from {', '.join(SUPPORTED_CLOUD_PROVIDERS)}")
    return providers


def _validate_llm(value: str | None) -> str | None:
    if value is None:
        return None
    llm = value.strip().lower()
    if llm not in SUPPORTED_LLM_PROVIDERS:
        raise typer.BadParameter(f"Unknown LLM provider {value!r}. Choose from {', '.join(SUPPORTED_LLM_PROVIDERS)}")
    return llm


def _money(value: Any, currency: str = "USD") -> str:
    try:
        return f"{currency} {float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


class ToolProgress:
    """Strands callback handler that surfaces tool calls in the spinner."""

    def __init__(self, status):
        self.status = status
        self.tools: list[str] = []

    def __call__(self, **kwargs: Any) -> None:
        tool_use = kwargs.get("event", {}).get("contentBlockStart", {}).get("start", {}).get("toolUse")
        if tool_use and tool_use.get("name"):
            self.tools.append(tool_use["name"])
            self.status.update(f"[cyan]Calling {tool_use['name']}...[/cyan]")
        elif kwargs.get("data") and self.tools:
            self.status.update("[cyan]Writing analysis...[/cyan]")


# ----- wizard -------------------------------------------------------------------------------


def print_banner() -> None:
    console.print(
        Panel.fit(
            f"[bold cyan]SHIMO[/bold cyan] · {settings.app_name} v{settings.app_version}\n"
            "[dim]AI multi-cloud cost analysis · 4-layer memory · AWS · Azure · GCP · DigitalOcean[/dim]",
            border_style="cyan",
        )
    )


def select_providers(preselected: list[str] | None = None) -> list[str]:
    if preselected:
        return preselected
    console.print("\n[bold]Step 1 · Cloud providers[/bold]  [dim](comma-separated numbers, e.g. 1,3)[/dim]")
    names = list(SUPPORTED_CLOUD_PROVIDERS)
    for index, name in enumerate(names, start=1):
        configured = settings.provider_status()[name]["configured"]
        marker = "[green]configured[/green]" if configured else "[dim]not configured[/dim]"
        console.print(f"  [bold]{index}[/bold] - {PROVIDER_LABELS[name]:<20} {marker}")
    while True:
        raw = Prompt.ask("Select providers", default="1")
        chosen: list[str] = []
        for token in raw.replace(" ", "").split(","):
            if token.isdigit() and 1 <= int(token) <= len(names):
                chosen.append(names[int(token) - 1])
            elif token in names:
                chosen.append(token)
        chosen = list(dict.fromkeys(chosen))
        if chosen:
            return chosen
        console.print("[red]Please choose at least one valid provider.[/red]")


def collect_credentials(providers: list[str]) -> dict[str, dict[str, Any]]:
    """Ask for account identifiers (stored) and, optionally, secrets (process-only)."""
    console.print("\n[bold]Step 2 · Account context[/bold]  [dim](identifiers are saved; secrets are never written to disk)[/dim]")
    credentials: dict[str, dict[str, Any]] = {}
    for provider in providers:
        console.print(f"\n[bold yellow]{PROVIDER_LABELS[provider]}[/bold yellow]")
        creds: dict[str, Any] = {}
        if provider == "aws":
            creds["account_id"] = Prompt.ask("AWS account ID", default=settings.aws_account_id or "")
            creds["region"] = Prompt.ask("Default region", default=settings.aws_region)
            if not settings.aws_access_key_id and Confirm.ask("Enter AWS access keys for this run?", default=False):
                creds["access_key_id"] = Prompt.ask("AWS_ACCESS_KEY_ID")
                creds["secret_access_key"] = Prompt.ask("AWS_SECRET_ACCESS_KEY", password=True)
                token = Prompt.ask("AWS_SESSION_TOKEN (optional)", default="", password=True)
                if token:
                    creds["session_token"] = token
            else:
                console.print("[dim]Using AWS credentials from the environment / profile.[/dim]")
        elif provider == "azure":
            creds["subscription_id"] = Prompt.ask("Azure subscription ID", default=settings.azure_subscription_id or "")
            if not settings.azure_client_secret and Confirm.ask("Enter a service principal for this run?", default=False):
                creds["tenant_id"] = Prompt.ask("AZURE_TENANT_ID")
                creds["client_id"] = Prompt.ask("AZURE_CLIENT_ID")
                creds["client_secret"] = Prompt.ask("AZURE_CLIENT_SECRET", password=True)
            else:
                console.print("[dim]Using Azure credentials from the environment / az login.[/dim]")
        elif provider == "gcp":
            creds["project_id"] = Prompt.ask("GCP project ID", default=settings.gcp_project_id or "")
            if not settings.gcp_service_account_json and Confirm.ask("Provide a service-account key path for this run?", default=False):
                creds["service_account_json"] = Prompt.ask("Path to service-account JSON")
            else:
                console.print("[dim]Using GCP credentials from the environment / ADC.[/dim]")
        elif provider == "digitalocean":
            creds["team"] = Prompt.ask("Team / account label (optional)", default="")
            if not settings.digitalocean_api_token:
                token = Prompt.ask("DigitalOcean API token (blank to skip)", default="", password=True)
                if token:
                    creds["api_token"] = token
            else:
                console.print("[dim]Using DIGITALOCEAN_API_TOKEN from the environment.[/dim]")
        credentials[provider] = {k: v for k, v in creds.items() if v not in ("", None)}
    return credentials


def select_llm(preselected: str | None = None) -> str:
    if preselected:
        return preselected
    console.print("\n[bold]Step 3 · LLM provider[/bold]")
    names = list(SUPPORTED_LLM_PROVIDERS)
    for index, name in enumerate(names, start=1):
        current = " [green](current default)[/green]" if name == settings.llm_provider else ""
        console.print(f"  [bold]{index}[/bold] - {LLM_LABELS[name]}{current}")
    default_index = str(names.index(settings.llm_provider) + 1) if settings.llm_provider in names else "1"
    while True:
        raw = Prompt.ask("Select LLM", default=default_index).strip().lower()
        if raw.isdigit() and 1 <= int(raw) <= len(names):
            return names[int(raw) - 1]
        if raw in names:
            return raw
        console.print("[red]Invalid choice.[/red]")


def start_session(
    name: str | None,
    providers: list[str],
    llm: str | None,
    user: str | None,
    quick: bool,
):
    harness = _harness()
    if not quick:
        print_banner()
    session_name = name or (
        f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        if quick
        else Prompt.ask("Session name", default=f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    )
    chosen = providers or (["aws"] if quick else select_providers())
    credentials = {} if quick else collect_credentials(chosen)
    llm_provider = llm or (settings.llm_provider if quick else select_llm())
    user_id = user if (user is not None or quick) else (Prompt.ask("Your user id (optional, enables cross-session memory)", default="") or None)

    session = harness.create_session(
        session_name=session_name,
        providers=chosen,
        llm_provider=llm_provider,
        user_id=user_id or None,
        credentials=credentials,
    )
    console.print(f"\n[green]✓[/green] Session created: [cyan]{session.id}[/cyan]")
    console.print(f"[green]✓[/green] Providers: {', '.join(PROVIDER_LABELS[p] for p in chosen)}")
    console.print(f"[green]✓[/green] LLM: {LLM_LABELS.get(llm_provider, llm_provider)} ({settings.llm_model_name(llm_provider)})")
    console.print("[green]✓[/green] Memory: 4-layer (hot · cold · procedural" + (" · deep)" if user_id else ")"))
    return harness


# ----- rendering ------------------------------------------------------------------------------


def render_turn(turn) -> None:
    analysis = turn.analysis or {}
    currency = analysis.get("currency", "USD")
    if not turn.success:
        console.print(Panel(f"[red]{turn.error or turn.response}[/red]", title="Shimo · error", border_style="red"))
        return

    console.print(Panel(analysis.get("summary") or turn.response, title="Shimo", border_style="cyan"))

    meta = []
    if analysis.get("total_cost"):
        meta.append(f"Total: [bold]{_money(analysis['total_cost'], currency)}[/bold]")
    if analysis.get("period"):
        meta.append(f"Period: {analysis['period']}")
    meta.append(f"Type: {analysis.get('query_type', 'analysis')}")
    console.print("  " + "   ".join(meta), style="dim")

    breakdown = analysis.get("service_breakdown") or []
    if breakdown:
        table = Table(title="Cost by service", title_justify="left")
        table.add_column("Service", style="cyan")
        table.add_column("Cost", justify="right", style="green")
        table.add_column("Share", justify="right")
        table.add_column("Change", justify="right")
        for item in breakdown[:12]:
            change = item.get("change") or 0
            change_text = f"{change:+.1f}%" if change else "-"
            style = "red" if change > 0 else "green" if change < 0 else "dim"
            table.add_row(
                str(item.get("service")),
                _money(item.get("cost"), currency),
                f"{float(item.get('percentage') or 0):.1f}%",
                f"[{style}]{change_text}[/{style}]",
            )
        console.print(table)

    series = analysis.get("time_series") or []
    if series:
        console.print("[bold]Trend[/bold]")
        peak = max((float(p.get("cost") or 0) for p in series), default=0) or 1
        for point in series[-12:]:
            cost = float(point.get("cost") or 0)
            bar_text = "█" * max(1, int(cost / peak * 30)) if cost > 0 else ""
            console.print(f"  {point.get('date'):<12} {bar_text} {_money(cost, currency)}")

    recommendations = analysis.get("recommendations") or []
    if recommendations:
        console.print("[bold yellow]Recommendations[/bold yellow]")
        for rec in recommendations:
            console.print(f"  • {rec}")

    footer = []
    if turn.tool_calls:
        footer.append("tools: " + ", ".join(f"{c['tool']}×{c['calls']}" for c in turn.tool_calls))
    if turn.usage.get("total_tokens"):
        footer.append(f"tokens: {turn.usage['total_tokens']}")
    footer.append(f"{turn.duration_seconds:.1f}s")
    console.print("  " + " · ".join(footer), style="dim")
    if turn.compression and turn.compression.get("compressed_messages"):
        console.print(f"[yellow]ℹ Context compressed ({turn.compression['compressed_messages']} messages summarised)[/yellow]")


def render_sessions(sessions: list[dict[str, Any]], title: str = "Sessions") -> None:
    if not sessions:
        console.print("[dim]No sessions found. Start one with `shimo chat`.[/dim]")
        return
    table = Table(title=title, title_justify="left")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Providers", style="yellow")
    table.add_column("LLM")
    table.add_column("Msgs", justify="right")
    table.add_column("Updated")
    table.add_column("State")
    for item in sessions:
        providers = ", ".join(p.upper() for p, enabled in (item.get("cloud_providers") or {}).items() if enabled)
        updated = (item.get("updated_at") or "")[:16].replace("T", " ")
        table.add_row(
            item["id"][:8],
            item["name"],
            providers,
            item.get("llm_provider", ""),
            str(item.get("message_count", 0)),
            updated,
            "active" if item.get("is_active") else "archived",
        )
    console.print(table)


# ----- chat loop ------------------------------------------------------------------------------------


HELP_TEXT = """[bold cyan]Commands[/bold cyan]
  /help            Show this help
  /sessions        List recent sessions
  /session         Show current session info
  /memory          Show memory layer status
  /health          Show agent health
  /tools           List tools available to this session
  /compress        Compress context (summarise older turns)
  /export [file]   Export the session as JSON (to a file if given)
  /config          Show configuration
  /clouds          Show connected cloud providers
  /model           Show the LLM in use
  /exit, /quit     End the session (it stays resumable)
[dim]Tip: `shimo chat --session <id>` resumes a session later.[/dim]"""


def handle_command(harness, command: str) -> bool:
    """Handle a slash command. Returns False when the loop should end."""
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/exit", "/quit"):
        return False
    if cmd == "/help":
        console.print(Panel(HELP_TEXT, border_style="cyan"))
    elif cmd == "/sessions":
        render_sessions(harness.list_sessions(limit=10), title="Recent sessions")
    elif cmd == "/session":
        console.print_json(data=harness.get_session_info())
    elif cmd == "/memory":
        show_memory(harness)
    elif cmd == "/health":
        console.print_json(data=harness.get_health_status())
    elif cmd == "/tools":
        for name in harness.get_session_info().get("tools", []):
            console.print(f"  • {name}")
    elif cmd == "/compress":
        with console.status("[yellow]Compressing context...[/yellow]"):
            result = harness.compress_context()
        if result.get("compressed_messages"):
            console.print(f"[green]✓[/green] Compressed {result['compressed_messages']} messages into a summary")
            console.print(f"[dim]{result.get('summary', '')[:400]}[/dim]")
        else:
            console.print("[dim]Nothing to compress yet.[/dim]")
    elif cmd == "/export":
        data = harness.export_session()
        if arg:
            Path(arg).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            console.print(f"[green]✓[/green] Exported to {arg}")
        else:
            console.print_json(data=data, default=str)
    elif cmd == "/config":
        show_config()
    elif cmd == "/clouds":
        for provider in harness.providers:
            ctx = harness.connection_context.get(provider) or {}
            details = ", ".join(f"{k}={v}" for k, v in ctx.items()) or "default credentials"
            console.print(f"  • {PROVIDER_LABELS[provider]}: {details}")
    elif cmd == "/model":
        console.print(f"  {LLM_LABELS.get(harness.llm_provider, harness.llm_provider)} · {settings.llm_model_name(harness.llm_provider)}")
    else:
        console.print(f"[dim]Unknown command {cmd}. Type /help for the list.[/dim]")
    return True


def show_memory(harness) -> None:
    status = harness.get_memory_status()
    table = Table(title="Memory layers", title_justify="left")
    table.add_column("Layer", style="cyan")
    table.add_column("Content", style="magenta")
    table.add_column("Status", style="green")
    hot = status["hot_memory"]
    cold = status["cold_memory"]
    proc = status["procedural_memory"]
    metrics = status["metrics"]
    table.add_row("HOT (prompt)", f"{hot['recent_interactions']} recent turns", f"{hot['total_messages']} messages")
    table.add_row(
        "COLD (history)",
        f"{cold['total_messages']} indexed, {cold['summaries']} summaries",
        f"{metrics['messages_since_summary']}/{metrics['compression_threshold']} until compression",
    )
    table.add_row("PROCEDURAL (skills)", f"{proc['total_skills']} skills", "loaded: " + (", ".join(proc["loaded_skills"]) or "-"))
    deep = status.get("deep_memory")
    table.add_row(
        "DEEP (user model)",
        f"{deep['total_sessions']} sessions, {deep['total_queries']} queries" if deep else "-",
        "enabled" if deep else "disabled (no user id)",
    )
    console.print(table)


def show_config() -> None:
    table = Table(title="Shimo configuration", title_justify="left")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")
    table.add_row("LLM provider", f"{settings.llm_provider} ({settings.llm_model_name()})")
    table.add_row("Database", settings.database_url)
    for name, status in settings.provider_status().items():
        details = ", ".join(f"{k}={v}" for k, v in status.items() if k != "configured" and v)
        table.add_row(PROVIDER_LABELS[name], ("configured" if status["configured"] else "not configured") + (f" · {details}" if details else ""))
    table.add_row("Compression threshold", str(settings.memory_compression_threshold))
    table.add_row("Recent window", str(settings.memory_recent_window))
    console.print(table)


def chat_loop(harness) -> None:
    console.print("\n[dim]Ask about your cloud costs. Type /help for commands, /exit to quit.[/dim]\n")
    while True:
        try:
            query = Prompt.ask("[bold cyan]Shimo[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            break
        if not query:
            continue
        if query.lower() in ("exit", "quit"):
            break
        if query.startswith("/"):
            if not handle_command(harness, query):
                break
            continue
        try:
            with console.status("[cyan]Analyzing...[/cyan]") as status:
                harness.callback_handler = ToolProgress(status)
                turn = harness.analyze(query)
        except KeyboardInterrupt:
            console.print("[yellow]Interrupted.[/yellow]")
            continue
        except Exception as exc:  # pylint: disable=broad-exception-caught
            console.print(f"[red]Error: {exc}[/red]")
            continue
        finally:
            harness.callback_handler = None
        render_turn(turn)

    summary = harness.end_session()
    console.print(
        f"[green]✓[/green] Session saved · {summary['query_count']} queries · "
        f"resume with [cyan]shimo chat --session {summary['session_id']}[/cyan]"
    )


# ----- commands ------------------------------------------------------------------------------------------


@app.command()
def chat(
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Resume a session by id (prefix ok)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Name for a new session"),
    providers: Optional[str] = typer.Option(None, "--providers", "-p", help="Comma-separated: aws,azure,gcp,digitalocean"),
    llm: Optional[str] = typer.Option(None, "--llm", "-l", help=f"LLM provider: {', '.join(SUPPORTED_LLM_PROVIDERS)}"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="User id (enables cross-session deep memory)"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Skip the wizard; use flags and defaults"),
):
    """Start (or resume) an interactive chat session."""
    provider_list = _parse_providers(providers)
    llm_provider = _validate_llm(llm)
    if session:
        harness = _harness()
        try:
            loaded = harness.load_session(session)
        except LookupError as exc:
            console.print(f"[red]✗ {exc}[/red]")
            raise typer.Exit(code=1) from exc
        console.print(f"[green]✓[/green] Resumed session [cyan]{loaded.id}[/cyan] · {loaded.name} · {loaded.message_count} messages")
        recent = harness.store.get_messages(loaded.id, limit=4, include_summaries=False)
        for message in recent:
            label = "You" if message.role == "user" else "Shimo"
            console.print(f"[dim]{label}: {message.content[:160]}{'...' if len(message.content) > 160 else ''}[/dim]")
    else:
        harness = start_session(name, provider_list, llm_provider, user, quick)
    try:
        chat_loop(harness)
    finally:
        harness.close()


@app.command()
def ask(
    query: str = typer.Argument(..., help="Question to ask"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Run inside an existing session"),
    providers: Optional[str] = typer.Option(None, "--providers", "-p", help="Comma-separated providers (new session)"),
    llm: Optional[str] = typer.Option(None, "--llm", "-l", help="LLM provider (new session)"),
    json_output: bool = typer.Option(False, "--json", help="Print the full result as JSON"),
):
    """Ask a single question non-interactively (creates a session if none is given)."""
    harness = _harness()
    try:
        if session:
            harness.load_session(session)
        else:
            harness.create_session(
                session_name=f"ask {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                providers=_parse_providers(providers) or ["aws"],
                llm_provider=_validate_llm(llm),
            )
        if json_output:
            turn = harness.analyze(query)
            console.print_json(data={"session_id": harness.session_id, **turn.to_dict()}, default=str)
        else:
            with console.status("[cyan]Analyzing...[/cyan]") as status:
                harness.callback_handler = ToolProgress(status)
                turn = harness.analyze(query)
            render_turn(turn)
            console.print(f"[dim]session: {harness.session_id}[/dim]")
        raise typer.Exit(code=0 if turn.success else 1)
    except LookupError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        harness.close()


@app.command()
def new(
    name: Optional[str] = typer.Option(None, "--name", "-n"),
    providers: Optional[str] = typer.Option(None, "--providers", "-p", help="Comma-separated providers"),
    llm: Optional[str] = typer.Option(None, "--llm", "-l"),
    user: Optional[str] = typer.Option(None, "--user", "-u"),
):
    """Create a new session without starting the chat."""
    harness = _harness()
    try:
        session_name = name or Prompt.ask("Session name", default=f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        chosen = _parse_providers(providers) or select_providers()
        created = harness.create_session(session_name=session_name, providers=chosen, llm_provider=_validate_llm(llm), user_id=user)
        console.print(f"[green]✓ Session created[/green]  id=[cyan]{created.id}[/cyan]  providers={', '.join(chosen)}")
        console.print(f"[dim]Start chatting with: shimo chat --session {created.id}[/dim]")
    finally:
        harness.close()


@app.command("sessions")
def sessions_cmd(
    limit: int = typer.Option(10, "--limit", help="Number of sessions to show"),
    show_all: bool = typer.Option(False, "--all", "-a", help="Include archived sessions"),
):
    """List sessions."""
    harness = _harness()
    try:
        render_sessions(harness.list_sessions(limit=limit, include_archived=show_all))
    finally:
        harness.close()


@app.command()
def resume(session_id: str = typer.Argument(..., help="Session id (prefix ok)")):
    """Resume a session (alias for `chat --session`)."""
    chat(session=session_id, name=None, providers=None, llm=None, user=None, quick=False)


@app.command()
def config():
    """Show the effective configuration."""
    show_config()


@app.command("providers")
def providers_cmd():
    """Show cloud provider configuration and the tools each one exposes."""
    from backend.agents.tools import tool_names  # pylint: disable=import-outside-toplevel

    table = Table(title="Cloud providers", title_justify="left")
    table.add_column("Provider", style="cyan")
    table.add_column("Status")
    table.add_column("Tools", style="dim")
    for name, status in settings.provider_status().items():
        state = "[green]configured[/green]" if status["configured"] else "[yellow]not configured[/yellow]"
        table.add_row(PROVIDER_LABELS[name], state, ", ".join(tool_names([name])))
    console.print(table)


@app.command()
def export(
    session_id: str = typer.Argument(..., help="Session id to export"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write JSON to this file"),
):
    """Export a session (messages, analysis, memory snapshot) as JSON."""
    harness = _harness()
    try:
        harness.load_session(session_id)
        data = harness.export_session()
        if output:
            output.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            console.print(f"[green]✓[/green] Exported to {output}")
        else:
            console.print_json(data=data, default=str)
    except LookupError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        harness.close()


@app.command()
def delete(
    session_id: str = typer.Argument(..., help="Session id to archive/delete"),
    hard: bool = typer.Option(False, "--hard", help="Permanently delete instead of archiving"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask for confirmation"),
):
    """Archive a session (or delete it permanently with --hard)."""
    harness = _harness()
    try:
        target = harness.store.require_session(session_id)
        action = "Permanently delete" if hard else "Archive"
        if not yes and not Confirm.ask(f"{action} session {target.id[:8]} · {target.name}?", default=False):
            raise typer.Exit(code=0)
        harness.delete_session(target.id, hard=hard)
        console.print(f"[green]✓[/green] Session {'deleted' if hard else 'archived'}")
    except LookupError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        harness.close()


def main() -> None:
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
