# Prompt-Toolkit Integration Plan (3 Phases)

## Overview
Replace the blocking `readline` + `input()` CLI loop with `prompt-toolkit`'s async `PromptSession`, eliminating the thread-based executor and manual ANSI cursor management. `prompt-toolkit` is already a declared dependency in `pyproject.toml` but is not imported anywhere.

## Target Files
| File | Action | Purpose |
|------|--------|---------|
| `src/follow/cli.py` | **Major rewrite** | Replace readline/input with `PromptSession.prompt_async()` + `patch_stdout()`; remove `Terminal` class; add `Completer` (Phase 2) |
| `src/follow/main.py` | **Edit** | Remove `run_in_executor`; remove `Terminal()` instantiation; await the async CLI loop directly |
| `AGENTS.md` | **Edit** | Update mentions of old Terminal/threaded-loop architecture |

---

## Phase 1 — Async PromptSession + patch_stdout

**Remove `Terminal` class entirely.** Inline its responsibilities:
- `prompt` string → `SearchCli.prompt` class attribute
- `stdout` → `sys.stdout` directly
- `emit_line()` → `print(line, file=sys.stdout)` under `patch_stdout`

**Rewrite `SearchCli`:**
- Drop readline imports/fallback and the manual `completer` callback
- Add `PromptSession` with `FileHistory('~/.py-follow-history')` and `WordCompleter`
- `loop()` becomes `async`; body wrapped in `patch_stdout()`
- `onecmd()` and `parse()` stay unchanged

**Update `main.py`:**
- Remove `Terminal()` construction
- Remove `loop.run_in_executor(None, cmdline.loop)`
- `cmdline.loop()` is now directly awaitable alongside `service.loop()`

### Detailed diff sketch — `cli.py`

```python
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout

prompt = '>>> '
history_file = os.path.expanduser('~/.py-follow-history')

class SearchCli(Closable):
    """Search command line interface"""

    def __init__(self, search_service, loop=None):
        super().__init__()
        self.service = search_service
        self._loop = loop or asyncio.get_running_loop()

        self._commands = {
            'quit': self.do_quit,
            'help': self.do_help,
            'list': self.do_list,
            **shell_commands,
            **match_commands,
        }

        self._session = PromptSession(
            history=FileHistory(history_file),
            completer=WordCompleter(list(self._commands)),
        )

    async def loop(self):
        with patch_stdout():
            while not self.is_closed:
                try:
                    line = await self._session.prompt_async(prompt)
                except EOFError:
                    self.close()
                    self.service.close()
                else:
                    self.onecmd(line.strip())
        self.service.close()
```

### Detailed diff sketch — `main.py`

```python
async def async_main(options):
    from .cli import SearchCli
    from .engine import AsyncSearchService

    loop = asyncio.get_running_loop()
    service = AsyncSearchService(loop=loop)
    cmdline = SearchCli(search_service=service, loop=loop)

    try:
        await asyncio.gather(cmdline.loop(), service.loop())
    finally:
        log.debug('close async loop')
```

---

## Phase 2 — Custom Completer with argument support

**Replace `WordCompleter`** with a `Completer` subclass that provides context-aware completions:

- First word → commands
- After `tail`/`open`/`file`/`follow` → file paths (or previously-seen paths)
- After `match`/`highlight` → color names
- After `negative` → (optional) regex suggestions

```python
class CommandCompleter(Completer):
    def __init__(self, commands, colors):
        self.commands = commands
        self.colors = colors
        self._cmd_names = list(commands)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        if ' ' not in text:
            # completing command name
            word = document.get_word_before_cursor()
            for cmd in self._cmd_names:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))
        else:
            # completing argument — inspect the command
            cmd = text.split()[0]
            if cmd in ('match', 'highlight') and text.count(' ') >= 1:
                # might be completing color name
                last_word = text.split()[-1]
                for color in self.colors:
                    if color.startswith(last_word):
                        yield Completion(color, start_position=-len(last_word))
            elif cmd in ('tail', 'open', 'file', 'follow'):
                # file path completion — simple, just echo what they type
                pass
```

**Install in `__init__`:**
```python
self._session = PromptSession(
    ...
    completer=CommandCompleter(self._commands, list(self.service.runtime.colors)),
)
```

---

## Phase 3 — Additional features (post-migration)

Add incrementally, one at a time, after verifying Phase 1+2 stability:

1. **Bottom toolbar** — show active files/patterns
   ```python
   from prompt_toolkit.formatted_text import HTML
   ...
   def _toolbar(self):
       n_files = len(self.service.runtime.files)
       n_patterns = len(self.service.runtime.patterns)
       return HTML(f'<b>{n_files}</b> files  <b>{n_patterns}</b> patterns')
   ```
   Pass as `bottom_toolbar=self._toolbar` to `PromptSession` or per-call.

2. **Syntax highlighting** — colorize commands using a `Lexer`
   ```python
   from prompt_toolkit.lexers import PygmentsLexer
   from pygments.lexers.shell import BashLexer
   # or a custom Lexer subclass
   ```

3. **Vi mode** — `PromptSession(vi_mode=True)`

---

## Implementation Order

### Phase 1 (one shot)
1. Rewrite `cli.py` — remove `Terminal`, drop readline, add `PromptSession` + `patch_stdout`
2. Edit `main.py` — remove `Terminal()`, remove `run_in_executor`
3. Run `uv run pytest` + `uv run mypy` + `uv run ruff check --fix` to verify

### Phase 2
4. Replace `WordCompleter` with `CommandCompleter` in `cli.py`
5. Run tests + mypy + ruff

### Phase 3 (per feature)
6. Bottom toolbar
7. Syntax highlighting
8. Vi mode

---

## What stays unchanged

| Module | Reason |
|--------|--------|
| `engine.py` | Pure async, no UI dependency |
| `commands.py` | Data model / command objects |
| `colorize.py` | Pure functions |
| `config.py` | Argument parsing, no UI |
| `ssh.py` | Connection management |
| `util.py` | Utilities |
| All `test/` files | No semantics changed for non-CLI code |

> **Note:** `prompt-toolkit` is already a hard dependency in `pyproject.toml`. Run `uv sync` before starting if the venv is out of date.
