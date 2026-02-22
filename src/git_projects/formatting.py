from __future__ import annotations

from datetime import datetime, timezone

import typer

from git_projects.foundry import RemoteRepo


def relative_time(iso_timestamp: str) -> str:
    """Return a human-relative string for an ISO 8601 UTC timestamp."""
    dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minutes ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hours ago"
    days = hours // 24
    if days < 30:
        return f"{days} days ago"
    months = days // 30
    if months < 12:
        return f"{months} months ago"
    years = days // 365
    return f"{years} years ago"


def format_header(name: str, count: int, width: int = 60) -> str:
    """Return a section header for a foundry."""
    label = typer.style(f"{name.upper()}  {count} repos", bold=True)
    return f"\n{label}\n{'─' * width}"


def format_repo(repo: RemoteRepo, width: int = 60, max_desc: int = 60) -> str:
    """Return an indented multi-line block describing one remote repo."""
    date = relative_time(repo.pushed_at)
    vis_label = f"[{repo.visibility}]"
    vis_color = typer.colors.RED if repo.visibility == "public" else typer.colors.GREEN

    # Compute plain-text width for correct padding
    plain_left = repo.name + " " + vis_label
    padding = max(1, width - len(plain_left) - len(date))

    name_styled = typer.style(repo.name, bold=True)
    vis_styled = typer.style(vis_label, fg=vis_color)
    date_styled = typer.style(date, dim=True)
    url_styled = typer.style(repo.clone_url, dim=True)

    name_line = name_styled + " " + vis_styled + " " * padding + date_styled
    lines = [name_line, f"  {url_styled}"]
    if repo.description:
        desc = repo.description
        if len(desc) > max_desc:
            desc = desc[: max_desc - 1] + "…"
        lines.append(f"  {desc}")
    return "\n".join(lines) + "\n"
