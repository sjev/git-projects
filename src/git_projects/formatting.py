from __future__ import annotations

from datetime import datetime, timezone

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
    label = f"{name.upper()}  {count} repos"
    return f"\n{label}\n{'─' * width}"


def format_repo(repo: RemoteRepo, width: int = 60, max_desc: int = 60) -> str:
    """Return an indented multi-line block describing one remote repo."""
    date = relative_time(repo.pushed_at)
    name_line = repo.name.ljust(width - len(date)) + date
    lines = [name_line, f"  {repo.clone_url}"]
    if repo.description:
        desc = repo.description
        if len(desc) > max_desc:
            desc = desc[: max_desc - 1] + "…"
        lines.append(f"  {desc}")
    return "\n".join(lines) + "\n"
