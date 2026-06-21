"""
Command line interface (prompt-toolkit version)
"""
import asyncio
import os
import sys
from typing import Any, Callable
from asyncio import AbstractEventLoop
from itertools import chain

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter, Completer, Completion  # noqa: F401
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout

from .commands import shell_commands, match_commands
from .engine import SearchService
from .util import Closable, term_help, log


class SearchCli(Closable):
    """Search command line interface using prompt-toolkit."""

    # default prompt string (can be overridden later)
    prompt: str = '>>> '

    def __init__(self, search_service: SearchService, loop: AbstractEventLoop = None) -> None:
        super().__init__()
        self.service = search_service  # search engine
        self._loop = loop or asyncio.get_running_loop()

        # command mapping
        self._commands: dict[str, Callable] = {
            'quit': self.do_quit,
            'help': self.do_help,
            'list': self.do_list,
            **shell_commands,
            **match_commands,
        }

        # History file for command recall
        history_path = os.path.expanduser('~/.py-follow-history')
        # Simple word completer for command names (Phase 2 will replace this)
        self._session = PromptSession(
            history=FileHistory(history_path),
            completer=WordCompleter(list(self._commands)),
            complete_while_typing=False,
        )

    # ---------------------------------------------------------------------
    # Utility output methods (replace the old Terminal.emit helpers)
    # ---------------------------------------------------------------------
    def emit(self, *strings: str, sep: str = ' ', end: str = '\n', flush: bool = True) -> None:
        """Write to stdout (captured by prompt-toolkit's patch_stdout)."""
        print(sep.join(strings), end=end, flush=flush, file=sys.stdout)

    def emit_line(self, line: str) -> None:
        """Print a line of output with ANSI colors using prompt-toolkit."""
        from prompt_toolkit import print_formatted_text, ANSI
        print_formatted_text(ANSI(line))

    # ---------------------------------------------------------------------
    # Command implementations
    # ---------------------------------------------------------------------
    def do_list(self, *args: Any) -> None:
        """List current set of files, colors, and/or matches."""
        if not args:
            args = ('files', 'patterns')
        objects = [getattr(self.service.runtime, n, []) for n in args]
        lines = ['Available:'] + [str(o) for o in chain(*objects)]
        self.emit('\n'.join(lines))

    def do_quit(self, *_: Any) -> None:
        """Exit application."""
        self.close()
        self.service.close()

    def do_help(self, *_: Any) -> None:
        """Shows this help message."""
        cmd_name: list[str] = ['Commands:'] + list(self._commands)
        cmd_docs: list[str] = ['']
        for m in self._commands.values():
            if m is not None and m.__doc__:
                cmd_docs.append(m.__doc__)
            else:
                cmd_docs.append('')
        text: str = term_help(cmd_name, cmd_docs)
        self.emit(text)

    # ---------------------------------------------------------------------
    # Core CLI loop (async)
    # ---------------------------------------------------------------------
    async def loop(self) -> None:
        """Async input loop using prompt-toolkit."""
        with patch_stdout():
            while not self.is_closed:
                try:
                    line = await self._session.prompt_async(self.prompt)
                except (EOFError, KeyboardInterrupt):
                    self.close()
                    self.service.close()
                else:
                    self.onecmd(line.strip())
        # ensure service is shut down when CLI ends
        self.service.close()

    # ---------------------------------------------------------------------
    # Command parsing and dispatch
    # ---------------------------------------------------------------------
    @staticmethod
    def parse(line: str) -> tuple[str | None, list[str], str]:
        line = line.strip()
        if not line:
            return None, [], line
        if line[0] == '?':
            line = 'help ' + line[1:]
        args = line.split()
        return args[0], args[1:], line

    def onecmd(self, line: str) -> None:
        cmd_name, args, _ = self.parse(line)
        if not cmd_name:
            return
        method = self._commands.get(cmd_name)
        if method is not None:
            obj = method(*args)
            if obj:
                self.service.add(obj)
        else:
            self.emit('Unknown command:', line)

    # ---------------------------------------------------------------------
    # Phase‑2 placeholder for richer completions (will replace WordCompleter)
    # ---------------------------------------------------------------------
    # def complete(self, document, complete_event):
    #     ...  # Future custom completer implementation

