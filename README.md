# git-proj

Discover, track, and sync Git repos across GitHub, GitLab, and Gitea from one CLI.

Local-first. Config-driven. No daemon.

## Why

If you juggle between different projects and work across multiple Git foundries — GitHub, a company GitLab, a self-hosted Gitea — you may lose track of what lives where and what you've been working on recently.

`git-proj` gives you one place to discover repos via APIs, pick which ones to track, and keep them synced locally.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git-proj
```

Or from source:

```bash
git clone https://github.com/sjev/git-projects.git
cd git-projects
uv sync --frozen
```

The CLI command is `gpr`.

## Quick start

```bash
# Create config with default foundries
gpr config init

# Edit ~/.local/share/git-projects/config.yaml to add your API tokens

# Fetch all repos from configured foundries
gpr remote fetch

# Browse what's available
gpr remote list
gpr remote list myproject    # filter by name

# Track a repo by name (resolved from index) or URL
gpr track my-repo
gpr track git@github.com:user/repo.git

# Clone missing repos, pull & push existing ones
gpr sync

# See what you're tracking
gpr list

# Stop tracking
gpr untrack my-repo
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
gpr sync
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
