# AGENTS.md – Quick reference for OpenCode agents

## Core workflow
- **Setup** – Install dependencies via `uv sync --all-extras` (requires asyncssh).
- **Test suite** – Run `uv run pytest`.
- **CLI entry point** – `py-follow` defined in `pyproject.toml` → `follow.main:main`.
- **Static analysis** – `uv run mypy` and `uv run ruff check --fix`.

## Modules Overview
- `main.py`: Sets up logging, event loop, parses CLI options, runs async main loop.
- `util.py`: Helper utilities (path parsing, logging, string conversion, singleton, etc.).
- `ssh.py`: AsyncSSH connection pool management (`get_client`, `close_all`).
- `commands.py`: Core command objects (`ShellCommand`, `Path`, `Tail`, `Open`, `Highlight`, `Match`, `NegativeMatch`) and match handling.
- `cli.py`: Interactive CLI built with prompt‑toolkit, command dispatch, help.
- `engine.py`: Search engine (`AsyncSearchService`) handling file processing, queuing output.
- `colorize.py`: Color definitions, building ANSI codes, applying highlights to lines.
- `config.py`: Configuration parsing (config files, command‑line args), runtime singleton.
- `__init__.py`: Package metadata (`__version__`, `__application__`).
- `__main__.py`: Script entry point for `python -m follow`.

## Command‑line syntax
- **File argument format** – `[[USER@]HOST:]FILE`.  Parsed by `ShellCommand._parse_path`.
- **Remote‑command alias handling** – On remote hosts `ShellCommand.local` prepends `$(command -v gtail || command -v tail)` before the actual command.
- **Debug mode** – `--debug` enables DEBUG‑level logging (useful for SSH troubleshooting).
- **Color shortcuts** – Generated from `colorize.default_colors`:
  - `-r` → red, `-g` → green, `-b` → blue, `-y` → yellow, `-e` → plain, `-v` → negative.

## Configuration
- **Default config file** – `~/.py-follow`.  Can be YAML *or* a Python literal dict (detected by a leading `{`).
- **Loading groups** – `-z GROUP` (repeatable) loads a named group from the config file; unknown groups trigger a warning.
- **Runtime singleton** – `Runtime` (in `config.py`) holds `files`, `patterns`, and `colors`.  CLI `-e` / `-v` add `Match` / `NegativeMatch` objects; `-f` wraps files as `Follow` (follow mode), otherwise as `File`.

## Remote execution (asyncssh)
- **Connection pool** – `follow.ssh.get_client(user, host)` caches `asyncssh.SSHClient` objects.
- **Shutdown cleanup** – `AsyncSearchService.close()` schedules `ssh.close_all()` to close all cached connections.
- **Process creation** – `ShellCommand.run`:
  - Remote → `await ssh.get_client(...).create_process(self.local)`.
  - Local  → `await asyncio.create_subprocess_exec(self.exec, *self.args, stdout=PIPE, stderr=PIPE)`.

## Search engine
- **Startup** – `AsyncSearchService` auto‑schedules a search for every file already in `Runtime.files`.
- **Search loop** – Reads each line from a subprocess via `await process.stdout.readline()`, applies `gather` → `colorize` → `tokens_to_str`, then pushes the formatted line onto an internal priority queue for display.

## Helpful utilities
- **HostHelpFormatter** – Overrides `argparse` usage strings to show the `[[USER@]HOST:]FILE` placeholder correctly.
- **Color definitions** – `colorize.build_colors()` creates ANSI codes and the short option mapping (`e` → plain, `v` → negative).  Aliases (`fuscia → fuchsia`, `darkyellow → brown`, etc.) are defined in this module.

---

*All of the above items are the “must‑know” facts that an OpenCode agent would otherwise miss.  Anything not listed here is either obvious from the codebase or covered by standard Python/CLI conventions.*
