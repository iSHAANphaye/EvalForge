"""Rich terminal output formatters and scorecards for EvalForge CLI."""

from __future__ import annotations

import json
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def get_console() -> Console:
    """Return a Rich Console instance."""
    return Console()


def render_scorecard(
    task_id: str,
    model_name: str,
    language: str,
    difficulty: str,
    ast_audit: dict[str, Any],
    execution: dict[str, Any],
    rubric: dict[str, Any],
    console: Console | None = None,
) -> None:
    """Render a high-contrast terminal evaluation scorecard matching INTERFACE_SPEC.md §1.2."""
    c = console or get_console()

    title = f"EvalForge — Task Evaluation: [bold cyan]{task_id}[/bold cyan]"
    subtitle = (
        f"Model: [bold yellow]{model_name}[/bold yellow] | "
        f"Language: [bold green]{language.capitalize()}[/bold green] | "
        f"Difficulty: [bold]{difficulty.capitalize()}[/bold]"
    )

    c.print()
    c.print(Panel(subtitle, title=title, border_style="blue", box=box.HEAVY))

    # [1/4] AST Anti-Cheat Audit
    ast_passed = not ast_audit.get("cheat_detected", False) and ast_audit.get("syntax_valid", True)
    ast_status = "[bold green][ PASSED ][/bold green]" if ast_passed else "[bold red][ CHEAT / ERROR ][/bold red]"
    ast_score = rubric.get("ast_score", rubric.get("anti_cheat_score", 0.0))
    c.print(f"  [bold][1/4] Static AST Anti-Cheat Audit[/bold] ........................... {ast_status} ({ast_score:.1f}/20)")

    violations = ast_audit.get("violations", [])
    if violations:
        for v in violations[:3]:
            c.print(f"        [red]⚠ {v}[/red]")
    else:
        complexity = ast_audit.get("cyclomatic_complexity", 1)
        c.print("        - Clean imports: no banned modules detected")
        c.print(f"        - Cyclomatic Complexity: {complexity} (Clean)")

    # [2/4] Container Checkout
    c.print("  [bold][2/4] Pre-Warmed Container Checkout[/bold] ......................... [bold green][ OK ][/bold green] (sub-100ms)")

    # [3/4] Isolated Execution
    duration_ms = execution.get("execution_time_ms", execution.get("duration_ms", 0.0))
    memory_kb = execution.get("memory_used_kb", execution.get("memory_peak_kb", 0))
    exit_code = execution.get("exit_code", 0)
    exec_status = "[bold green][ DONE ][/bold green]" if exit_code == 0 else "[bold red][ FAILED ][/bold red]"
    c.print(
        f"  [bold][3/4] Isolated Execution (RAM: 256MB, CPU: 1.0)[/bold] .............. {exec_status} "
        f"({duration_ms:.1f}ms, {memory_kb // 1024}MB peak)"
    )

    # [4/4] Rubric Scoring Breakdown Table
    c.print("  [bold][4/4] Rubric Scoring Breakdown:[/bold]")
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold blue")
    table.add_column("Rubric Axis", style="white", min_width=32)
    table.add_column("Weight", justify="right", style="cyan")
    table.add_column("Score", justify="right", style="bold")

    func_score = rubric.get("functional_score", 0.0)
    edge_score = rubric.get("edge_score", rubric.get("edge_scale_score", 0.0))
    anti_score = rubric.get("ast_score", rubric.get("anti_cheat_score", 0.0))
    hyg_score = rubric.get("hygiene_score", rubric.get("code_hygiene_score", 0.0))
    composite = rubric.get("composite_score", 0.0)

    table.add_row("Axis 1: Functional Correctness", "40.0%", f"{func_score:.1f} / 40")
    table.add_row("Axis 2: Edge-Case & Scale", "30.0%", f"{edge_score:.1f} / 30")
    table.add_row("Axis 3: Anti-Reward-Hacking", "20.0%", f"{anti_score:.1f} / 20")
    table.add_row("Axis 4: Code Hygiene & Style", "10.0%", f"{hyg_score:.1f} / 10")
    table.add_section()
    comp_color = "green" if composite >= 75.0 else "red"
    table.add_row("[bold]Composite Score[/bold]", "100.0%", f"[{comp_color}]{composite:.1f} / 100[/{comp_color}]")

    c.print(table)

    is_passed = rubric.get("is_passed", False)
    if is_passed:
        c.print(f"  [bold green]Final Outcome: PASSED[/bold green] (Total Latency: {duration_ms:.1f}ms)\n")
    else:
        c.print("  [bold red]Final Outcome: FAILED[/bold red] (Composite < 75.0 or Functional < 40)\n")


def render_leaderboard(
    entries: list[dict[str, Any]],
    title: str = "EVALFORGE BENCHMARK LEADERBOARD",
    subtitle: str = "Evaluated against 30 Algorithmic Tasks",
    console: Console | None = None,
) -> None:
    """Render aggregate benchmark leaderboard table matching INTERFACE_SPEC.md §4.3."""
    c = console or get_console()
    c.print()

    header_panel = Panel(
        f"[bold]{subtitle}[/bold]",
        title=f"[bold cyan]{title}[/bold cyan]",
        border_style="blue",
        box=box.DOUBLE,
    )
    c.print(header_panel)

    table = Table(box=box.HEAVY_HEAD, show_header=True, header_style="bold blue")
    table.add_column("Rank", justify="center", style="bold white", width=6)
    table.add_column("Model Name", style="bold yellow", min_width=22)
    table.add_column("Tasks", justify="center", style="white", width=9)
    table.add_column("pass@1", justify="right", style="green", width=10)
    table.add_column("pass@5", justify="right", style="cyan", width=10)
    table.add_column("Mean Score", justify="right", style="bold", width=13)
    table.add_column("Cheats Detected", justify="center", style="red", width=17)

    if not entries:
        table.add_row("-", "No evaluations recorded yet", "0 / 30", "0.0%", "0.0%", "0.0 / 100", "0")
    else:
        for entry in entries:
            rank = str(entry.get("rank", "-"))
            model = str(entry.get("model_name", "unknown"))
            total_tasks = str(entry.get("total_tasks", 0))
            p1 = f"{entry.get('pass_at_1', 0.0):.1f}%"
            p5 = f"{entry.get('pass_at_5', entry.get('pass_at_1', 0.0)):.1f}%"
            mean_score = f"{entry.get('mean_composite_score', 0.0):.1f} / 100"
            cheats = entry.get("cheat_attempts_detected", 0)
            cheat_str = f"{cheats} (Disqualified)" if cheats > 0 else "0"

            table.add_row(rank, model, f"{total_tasks} / 30", p1, p5, mean_score, cheat_str)

    c.print(table)
    c.print()


def render_run_report(
    run_data: dict[str, Any],
    output_format: str = "table",
    console: Console | None = None,
) -> str | None:
    """Render or export evaluation run summary in table, json, or markdown format."""
    c = console or get_console()

    if output_format == "json":
        formatted_json = json.dumps(run_data, indent=2, default=str)
        c.print(formatted_json)
        return formatted_json

    if output_format == "markdown":
        md_lines = [
            f"# EvalForge Run Report: {run_data.get('run_id')}",
            f"- **Model**: {run_data.get('model_name')}",
            f"- **Tasks Evaluated**: {run_data.get('tasks_evaluated')}",
            f"- **pass@1**: {run_data.get('pass_at_1', 0.0) * 100:.1f}%",
            f"- **Mean Score**: {run_data.get('mean_score', 0.0):.1f} / 100",
            f"- **Created At**: {run_data.get('created_at')}",
            "",
            "## Task Evaluations",
            "| Task ID | Passed | Composite Score | Cheat Detected | Execution Time (ms) |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ]
        for ev in run_data.get("evaluations", []):
            passed_sym = "✅" if ev.get("passed") else "❌"
            score = ev.get("composite_score", 0.0)
            cheat = "🚨 Yes" if ev.get("cheat_detected") else "No"
            dur = ev.get("duration_ms", 0.0)
            md_lines.append(f"| {ev.get('task_id')} | {passed_sym} | {score:.1f} | {cheat} | {dur:.1f} |")

        md_output = "\n".join(md_lines)
        c.print(md_output)
        return md_output

    # Default: Rich Table
    c.print()
    panel = Panel(
        f"Model: [bold yellow]{run_data.get('model_name')}[/bold yellow] | "
        f"Tasks Evaluated: [bold]{run_data.get('tasks_evaluated')}[/bold] | "
        f"Mean Score: [bold green]{run_data.get('mean_score', 0.0):.1f} / 100[/bold green]",
        title=f"Evaluation Run: [bold cyan]{run_data.get('run_id')}[/bold cyan]",
        border_style="blue",
    )
    c.print(panel)

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold blue")
    table.add_column("Task ID", style="bold white")
    table.add_column("Passed", justify="center")
    table.add_column("Composite", justify="right")
    table.add_column("Functional", justify="right")
    table.add_column("Edge Cases", justify="right")
    table.add_column("Anti-Cheat", justify="right")
    table.add_column("Execution (ms)", justify="right")

    for ev in run_data.get("evaluations", []):
        p_str = "[bold green]PASS[/bold green]" if ev.get("passed") else "[bold red]FAIL[/bold red]"
        comp = f"{ev.get('composite_score', 0.0):.1f}"
        func = f"{ev.get('functional_score', 0.0):.1f}"
        edge = f"{ev.get('edge_scale_score', 0.0):.1f}"
        anti = f"{ev.get('anti_cheat_score', 0.0):.1f}"
        dur = f"{ev.get('duration_ms', 0.0):.1f}"
        table.add_row(ev.get("task_id", "-"), p_str, comp, func, edge, anti, dur)

    c.print(table)
    c.print()
    return None


__all__ = ["get_console", "render_scorecard", "render_leaderboard", "render_run_report"]
