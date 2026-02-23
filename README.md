# git-projects

Discover, track, and sync Git repos across GitHub, GitLab, and Gitea from one CLI.

Local-first. Config-driven. No daemon.

## Why

If you work across multiple Git foundries — GitHub, a company GitLab, a self-hosted Gitea — you lose track of what lives where.
`git-projects` gives you one place to discover repos via APIs, pick which ones to track, and keep them synced locally.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git-projects
```

Or from source:

```bash
git clone https://github.com/sjev/git-projects.git
cd git-projects
uv sync --frozen
```

## Quick start

```bash
# Create config with default foundries
git-projects config init

# Edit ~/.local/share/git-projects/config.yaml to add your API tokens

# Fetch all repos from configured foundries
git-projects remote fetch

# Browse what's available
git-projects remote list
git-projects remote list myproject    # filter by name

# Track a repo by name (resolved from index) or URL
git-projects track my-repo
git-projects track git@github.com:user/repo.git

# Clone missing repos, pull & push existing ones
git-projects sync

# See what you're tracking
git-projects list

# Stop tracking
git-projects untrack my-repo
```

## Commands

| Command | Description |
|---|---|
| `config init` | Create default config file |
| `config show` | Show config path and contents |
| `remote fetch [foundry]` | Fetch repos from foundry APIs, save to local index |
| `remote list [query] [--all]` | Browse repos from local index (no network) |
| `track <name\|url> [--path]` | Add a project to tracking |
| `untrack <name>` | Remove a project from tracking |
| `list` | Show tracked projects |
| `sync` | Clone missing, pull & push existing tracked repos |
| `info` | Show version, paths, and counts |

## Configuration

Config lives at `$XDG_DATA_HOME/git-projects/` (typically `~/.local/share/git-projects/`):

```
config.yaml      # foundries, clone_root, credentials — never share this
projects.json    # tracked projects (portable, no secrets)
index.json       # cached repo metadata from last fetch
```

Example `config.yaml`:

```yaml
clone_root: ~/projects
clone_url_format: ssh    # or "https"
foundries:
  - name: github
    type: github
    token: ghp_...
  - name: my-gitea
    type: gitea
    url: https://gitea.example.com
    token: ""
```

### Multi-machine setup

`projects.json` is portable (relative paths, no secrets). Copy it between machines:

```bash
scp ~/.local/share/git-projects/projects.json other-machine:~/.local/share/git-projects/
git-projects sync
```

## Development

```bash
uv sync --group dev
uv run invoke lint      # ruff check + ruff format --check + mypy
uv run invoke test      # pytest with coverage
uv run invoke format    # ruff format
```

## License

MIT
