from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

console = Console()


def print_rewritten_query(original: str, rewritten: str, where_filter: dict | None = None, where_document: dict | None = None):
    """Display the rewritten query alongside the original."""
    text = Text()
    text.append("Original:       ", style="dim")
    text.append(original, style="white")
    text.append("\n")
    text.append("Rewritten:      ", style="dim")
    text.append(rewritten, style="bold yellow")
    text.append("\n")
    text.append("Filter:         ", style="dim")
    text.append(str(where_filter) if where_filter else "None (all providers)", style="cyan")
    text.append("\n")
    text.append("Doc filter:     ", style="dim")
    text.append(str(where_document) if where_document else "None", style="cyan")
    console.print(Panel(text, title="Query Rewrite", border_style="yellow", padding=(0, 1)))


def print_context(selected: list[tuple[str, float, dict]]):
    """Display retrieved context chunks in styled panels."""
    console.print(Rule("[bold cyan]Context[/bold cyan]"))
    for i, (doc, sim, meta) in enumerate(selected, 1):
        title = f"Chunk {i} | {meta.get('provider', '')} | similarity: {sim:.3f}"
        header = Text(title, style="dim")
        console.print(Panel(doc.strip(), title=str(header), border_style="blue", padding=(0, 1)))


def print_question(query: str):
    """Display the user's question in a styled panel."""
    console.print(Panel(query, title="Question", border_style="green", padding=(0, 1)))
    console.print(Rule(style="cyan"))


def print_answer(answer: str):
    """Display the LLM's answer in a styled panel."""
    console.print(Panel(answer.strip(), title="Answer", border_style="magenta", padding=(1, 2)))
