"""
Shimo CLI v2 - Memory-Aware Interactive Agent
==============================================
Updated CLI with:
- Cloud platform selection on startup
- Account number input
- Credential management
- Memory-aware session management
- Long-running session support

Uses:
- Typer: CLI framework
- Rich: Beautiful TUI output
- Memory Manager: 4-layer memory system
- Agent Harness: Memory-aware query processing
"""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from typing import List
from datetime import datetime

from backend.agents.agent_harness import AgentHarness
from backend.memory import CloudProvider

# Rich console for beautiful output
console = Console()
app = typer.Typer(help="Shimo Cloud Analytics Agent")


# ========== UTILITY FUNCTIONS ==========


def print_banner():
    """Print Shimo banner"""
    banner = """
    ╔═══════════════════════════════════════╗
    ║  🚀 SHIMO Cloud Analytics Agent v2.0  ║
    ║  Shimo Memory System Enabled          ║
    ╚═══════════════════════════════════════╝
    """
    console.print(banner, style="cyan bold")


def print_section(title: str):
    """Print a section header"""
    console.print(f"\n[bold cyan]▶ {title}[/bold cyan]")


# ========== CLOUD PROVIDER SELECTION ==========


def select_cloud_providers() -> List[CloudProvider]:
    """
    Interactive cloud provider selection.

    Returns:
        List of selected providers
    """
    print_section("Step 1: Select Cloud Providers")

    providers = {
        "1": CloudProvider.AWS,
        "2": CloudProvider.AZURE,
        "3": CloudProvider.GCP,
        "4": CloudProvider.DIGITALOCEAN,
    }

    console.print("Available providers:")
    console.print("  [bold]1[/bold] - AWS")
    console.print("  [bold]2[/bold] - Azure")
    console.print("  [bold]3[/bold] - GCP (Google Cloud)")
    console.print("  [bold]4[/bold] - DigitalOcean")
    console.print("  [bold]5[/bold] - Multi-cloud (select multiple)")

    choice = Prompt.ask("Select provider (1-5)", default="1")

    if choice == "5":
        # Multi-cloud selection
        selected = []
        console.print("\n[bold]Multi-cloud mode[/bold] - Select providers:")

        while True:
            for key, provider in providers.items():
                status = "✓" if provider in selected else " "
                console.print(f"  [{status}] {key} - {provider.value.upper()}")

            choice = Prompt.ask("Add provider (1-4) or 'done'", default="done")

            if choice == "done":
                break
            elif choice in providers:
                if providers[choice] not in selected:
                    selected.append(providers[choice])
                    console.print(
                        f"  ✓ Added {providers[choice].value.upper()}", style="green"
                    )
                else:
                    console.print("  Already selected", style="yellow")
            else:
                console.print("  Invalid choice", style="red")

        return selected if selected else [CloudProvider.AWS]
    else:
        provider = providers.get(choice, CloudProvider.AWS)
        return [provider]


# ========== ACCOUNT & CREDENTIAL INPUT ==========


def input_credentials(provider: CloudProvider) -> dict:
    """
    Interactive credential input for a provider.

    Args:
        provider: Cloud provider

    Returns:
        Credentials dictionary
    """
    console.print(f"\n[bold yellow]Setting up {provider.value.upper()}[/bold yellow]")

    credentials = {}

    if provider == CloudProvider.AWS:
        credentials["account_id"] = Prompt.ask("AWS Account ID (12 digits)")
        credentials["region"] = Prompt.ask("AWS Region", default="us-east-1")
        console.print(
            "[dim]Using AWS credentials from environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)[/dim]"
        )

    elif provider == CloudProvider.AZURE:
        credentials["subscription_id"] = Prompt.ask("Azure Subscription ID")
        console.print(
            "[dim]Using Azure credentials from environment (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET)[/dim]"
        )

    elif provider == CloudProvider.GCP:
        credentials["project_id"] = Prompt.ask("GCP Project ID")
        console.print(
            "[dim]Using GCP service account from GCP_SERVICE_ACCOUNT_JSON environment[/dim]"
        )

    elif provider == CloudProvider.DIGITALOCEAN:
        credentials["api_token"] = Prompt.ask("DigitalOcean API Token", password=True)

    return credentials


def setup_providers(providers: List[CloudProvider]) -> tuple:
    """
    Setup credentials for all selected providers.

    Returns:
        (provider_credentials_dict, provider_list)
    """
    print_section("Step 2: Provider Configuration")

    all_credentials = {}

    for provider in providers:
        creds = input_credentials(provider)
        all_credentials[provider.value] = creds
        console.print(f"  ✓ {provider.value.upper()} configured", style="green")

    return all_credentials, providers


# ========== LLM PROVIDER SELECTION ==========


def select_llm_provider() -> str:
    """
    Interactive LLM provider selection.

    Returns:
        LLM provider name
    """
    print_section("Step 3: Select LLM Provider")

    providers = {
        "1": "bedrock",
        "2": "openai",
        "3": "gemini",
        "4": "anthropic",
        "5": "ollama",
        "6": "unsloth",
    }

    console.print("Available LLM providers:")
    console.print("  [bold]1[/bold] - AWS Bedrock (recommended)")
    console.print("  [bold]2[/bold] - OpenAI GPT-4o")
    console.print("  [bold]3[/bold] - Google Gemini")
    console.print("  [bold]4[/bold] - Anthropic Claude")
    console.print("  [bold]5[/bold] - Ollama (local)")
    console.print("  [bold]6[/bold] - Unsloth Studio")

    choice = Prompt.ask("Select LLM (1-6)", default="1")

    llm = providers.get(choice, "bedrock")
    console.print(f"  ✓ Selected {llm.upper()}", style="green")
    return llm


# ========== SESSION INITIALIZATION ==========


def init_session() -> AgentHarness:
    """
    Initialize a new session with full wizard.

    Returns:
        Initialized AgentHarness
    """
    print_banner()

    # Step 1: Session name
    print_section("Step 0: Session Name")
    session_name = Prompt.ask(
        "Session name",
        default=f"Shimo Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )

    # Step 2: Cloud providers
    providers = select_cloud_providers()

    # Step 3: Credentials
    all_credentials, active_providers = setup_providers(providers)

    # Step 4: LLM
    llm_provider = select_llm_provider()

    # Step 5: Initialize harness
    print_section("Step 4: Initializing Agent")

    harness = AgentHarness(
        user_id=Prompt.ask("Your user ID (optional, press Enter to skip)", default=""),
        enable_deep_memory=True,
    )

    session_id = harness.create_session(
        session_name=session_name,
        providers=active_providers,
        llm_provider=llm_provider,
        credentials=all_credentials,
    )

    console.print(f"  ✓ Session created: {session_id}", style="green")
    console.print(
        f"  ✓ Providers: {', '.join([p.value.upper() for p in active_providers])}",
        style="green",
    )
    console.print(f"  ✓ LLM: {llm_provider.upper()}", style="green")
    console.print("  ✓ Memory system: Active (4-layer)", style="green")

    return harness


# ========== INTERACTIVE CHAT ==========


def chat_loop(harness: AgentHarness):
    """
    Main interactive chat loop.

    Args:
        harness: AgentHarness instance
    """
    print_section("Chat Session Started")
    console.print("Type '/help' for commands | '/exit' to quit\n")

    while True:
        try:
            # Get user query
            query = Prompt.ask("[bold cyan]Shimo[/bold cyan]")

            if not query.strip():
                continue

            # Handle commands
            if query.startswith("/"):
                handle_command(harness, query)
                continue

            # Process query
            console.print("\n[dim]Processing query...[/dim]")

            try:
                response, analysis = harness.analyze(query)

                # Display response
                console.print("\n[bold green]Response:[/bold green]")
                console.print(response)

                # Display analysis data
                if analysis:
                    console.print("\n[bold cyan]Analysis Data:[/bold cyan]")
                    for key, value in analysis.items():
                        console.print(f"  {key}: {value}")

                # Check if compression needed
                if harness.check_compression_needed():
                    console.print(
                        "\n[yellow]ℹ Context compression triggered (auto)[/yellow]",
                        style="dim",
                    )

            except Exception as e:
                console.print(f"[red]Error processing query: {e}[/red]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type '/exit' to quit.[/yellow]")
        except EOFError:
            break


# ========== SLASH COMMANDS ==========


def handle_command(harness: AgentHarness, command: str):
    """Handle slash commands"""
    cmd = command.split()[0].lower()

    if cmd == "/help":
        show_help()

    elif cmd == "/memory":
        show_memory_status(harness)

    elif cmd == "/compress":
        compress_session(harness)

    elif cmd == "/session":
        show_session_info(harness)

    elif cmd == "/export":
        export_session(harness)

    elif cmd == "/health":
        show_health_status(harness)

    elif cmd == "/exit":
        exit_session(harness)

    else:
        console.print("[red]Unknown command. Type '/help' for list.[/red]")


def show_help():
    """Display help information"""
    console.print("\n[bold cyan]Available Commands:[/bold cyan]")

    help_text = """
    [bold]/help[/bold]           - Show this help
    [bold]/memory[/bold]         - Show memory status (all 4 layers)
    [bold]/compress[/bold]       - Force context compression
    [bold]/session[/bold]        - Show session information
    [bold]/export[/bold]         - Export session as JSON
    [bold]/health[/bold]         - Show agent health status
    [bold]/exit[/bold]           - End session and save
    
    [dim]Shortcut: 'quit' or Ctrl+D to exit[/dim]
    """
    console.print(help_text)


def show_memory_status(harness: AgentHarness):
    """Display memory layer status"""
    console.print("\n[bold cyan]Memory System Status[/bold cyan]")

    status = harness.get_memory_status()

    # Create table
    table = Table(title="Memory Layers")
    table.add_column("Layer", style="cyan")
    table.add_column("Content", style="magenta")
    table.add_column("Status", style="green")

    # Hot Memory
    hot = status["hot_memory"]
    table.add_row("HOT (Prompt)", f"{hot['total_messages']} interactions", "✓ Active")

    # Cold Memory
    cold = status["cold_memory"]
    table.add_row("COLD (History)", f"{cold['total_messages']} stored", "✓ Searchable")

    # Procedural Memory
    proc = status["procedural_memory"]
    table.add_row(
        "PROCEDURAL (Skills)",
        f"{proc['total_skills']} total",
        f"Loaded: {proc['loaded_skills']}",
    )

    # Deep Memory
    if status["deep_memory"]:
        deep = status["deep_memory"]
        table.add_row(
            "DEEP (User Model)", f"{deep['total_sessions']} sessions", "✓ Enabled"
        )

    console.print(table)


def show_session_info(harness: AgentHarness):
    """Display session information"""
    console.print("\n[bold cyan]Session Information[/bold cyan]")

    info = harness.get_session_info()

    # Create panel
    content = f"""
[cyan]Session ID:[/cyan] {info["session_id"]}
[cyan]Name:[/cyan] {info["session_name"]}
[cyan]Providers:[/cyan] {", ".join(info["providers"])}
[cyan]LLM:[/cyan] {info["llm_provider"]}
[cyan]Queries:[/cyan] {info["query_count"]}
[cyan]Created:[/cyan] {info["created_at"]}
[cyan]Last Activity:[/cyan] {info["last_activity"]}
    """

    console.print(Panel(content, title="Session", border_style="cyan"))


def show_health_status(harness: AgentHarness):
    """Display agent health"""
    console.print("\n[bold cyan]Agent Health Status[/bold cyan]")

    health = harness.get_health_status()

    # Create table
    table = Table(title="Health Metrics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Session Active", "✓" if health["session_active"] else "✗")

    mem = health["memory_layers"]
    table.add_row("Memory - Hot", str(mem["hot"]))
    table.add_row("Memory - Cold", str(mem["cold"]))
    table.add_row("Memory - Procedural", str(mem["procedural"]))
    table.add_row("Memory - Deep", mem["deep"])

    comp = health["compression_status"]
    table.add_row("Compressions", str(comp["compressions"]))

    console.print(table)


def compress_session(harness: AgentHarness):
    """Manually compress session context"""
    console.print("\n[yellow]Compressing session context...[/yellow]")

    result = harness.compress_context()

    console.print(f"  ✓ Compressed: {result['compressed_messages']} messages")
    console.print(f"  ✓ Pruned: {result['pruned_messages']} messages")
    console.print("  ✓ Summary saved to memory")


def export_session(harness: AgentHarness):
    """Export session data"""
    console.print("\n[yellow]Exporting session...[/yellow]")

    export = harness.export_session()

    filename = f"session_{export['session_id']}.json"

    # Print JSON
    console.print("\n[cyan]Exported session data:[/cyan]")
    console.print_json(data=export)

    console.print(f"\n[green]✓ Exported to: {filename}[/green]")


def exit_session(harness: AgentHarness):
    """End session gracefully"""
    console.print("\n[yellow]Ending session...[/yellow]")

    summary = harness.end_session()

    console.print("\n[bold cyan]Session Summary:[/bold cyan]")
    console.print(f"  Duration: {summary['duration_minutes']:.1f} minutes")
    console.print(f"  Total queries: {summary['query_count']}")
    console.print(f"  Session ID: {summary['session_id']}")

    console.print("\n[green]✓ Session saved and closed[/green]")
    raise typer.Exit()


# ========== MAIN COMMANDS ==========


@app.command()
def chat():
    """
    Start interactive chat session with cloud analytics.

    This launches the main Shimo experience with:
    - Cloud provider selection
    - Account configuration
    - Memory-aware analysis
    - Long-running session support
    """
    try:
        # Initialize session
        harness = init_session()

        # Start chat loop
        chat_loop(harness)

    except KeyboardInterrupt:
        console.print("\n[yellow]Session interrupted[/yellow]")
    except typer.Exit:
        pass
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise


@app.command()
def sessions():
    """List recent sessions (stub - needs DB integration)"""
    console.print(
        "[dim]Recent sessions (coming soon - requires database integration)[/dim]"
    )


@app.command()
def config():
    """Show current configuration"""
    console.print("[cyan]Shimo Configuration[/cyan]")
    console.print("  Memory system: Shimo 4-layer")
    console.print(
        "  LLM providers: Bedrock, OpenAI, Gemini, Anthropic, Ollama, Unsloth"
    )
    console.print("  Cloud providers: AWS, Azure, GCP, DigitalOcean")
    console.print("  Version: 2.0.0")


def main():
    """Entry point"""
    app()


if __name__ == "__main__":
    main()
