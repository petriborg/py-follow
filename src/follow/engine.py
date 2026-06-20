"""
Main search engine.
"""

import abc
import asyncio
import logging
from typing import Any, Awaitable
from asyncio import AbstractEventLoop, PriorityQueue

from .commands import ShellCommand
from .ssh import close_all
from .util import Closable, syslog_date, coerce_str as _str
from .colorize import colorize, gather, tokens_to_str

log = logging.getLogger()


class SearchService(Closable):
    def __init__(self) -> None:
        super().__init__()
        from .config import Runtime
        self.runtime = Runtime()

    @abc.abstractmethod
    def loop(self, term: Any) -> Awaitable[None]:
        pass

    @abc.abstractmethod
    def add(self, obj: Any) -> None:
        pass

    @abc.abstractmethod
    def open_file(self, file: Any) -> Awaitable[Any]:
        pass

    @abc.abstractmethod
    def search(self, file: Any) -> Awaitable[None]:
        pass


class AsyncSearchService(SearchService):
    """
    https://stackoverflow.com/a/37430948
    """

    def __init__(
            self,
            queue: PriorityQueue = None,
            loop: AbstractEventLoop = None
    ):
        self._loop = loop or asyncio.get_running_loop()
        self._queue = queue or asyncio.PriorityQueue()
        super().__init__()

        # start files already part of the runtime
        for file in self.runtime.files:
            asyncio.ensure_future(self.search(file), loop=self._loop)

    def add(self, obj: Any) -> None:
        self.runtime.add(obj)
        if isinstance(obj, ShellCommand):
            asyncio.ensure_future(self.search(obj), loop=self._loop)

    async def loop(self, terminal: Any) -> None:
        """pulls from the print queue and writes to terminal"""
        try:
            log.debug('search loop -> closed: %s', self.is_closed)
            while not self.is_closed:
                try:
                    dt, line = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.1)
                else:
                    terminal.emit_line(line)
        except Exception:
            self.close()
            raise
        finally:
            log.debug('finished search loop -> closed: %s', self.is_closed)

    async def open_file(self, file: Any) -> Any:
        """
        Open file for search using the ShellCommand.run() method.
        Returns a process-like object (local subprocess or SSH process).
        """
        # ``file`` is expected to be a ShellCommand (or subclass) instance.
        # ``run`` handles both local and remote execution.
        proc = await file.run()
        log.debug('open_file(%s) => %r', getattr(file, 'shell', '<no shell>'), proc)
        return proc

    def close(self):
        # Ensure SSH connections are closed on shutdown
        super().close()
        # Schedule async cleanup (non-blocking)
        asyncio.ensure_future(close_all())

    async def search(self, file: Any) -> None:
        """
        Search 'file' for 'section.patterns', queueing colorized output
        for display.
        """
        process = await self.open_file(file)
        log.debug('search %r', process)

        def close() -> None:
            nonlocal process
            log.debug('close subprocess %r', process)
            try:
                if process.returncode is None:
                    log.info('terminate %r', process)
                    process.terminate()
                else:
                    log.info('%r already terminated', process)
            except ProcessLookupError:
                pass  # ignore kill failures

        try:
            # while process is alive, search output for matches
            # queue resulting matches for display
            while process.returncode is None:
                if self.is_closed:
                    close()
                    break

                try:
                    assert process.stdout is not None
                    byte_line = await asyncio.wait_for(
                        process.stdout.readline(), 0.1)
                    line = _str(byte_line).rstrip()
                except asyncio.TimeoutError:
                    continue

                matches, print_line = gather(
                    self.runtime.patterns, line, self.runtime.requires_match)
                if print_line:
                    dt = syslog_date(line)
                    tokens = colorize(matches, line)
                    color_line = tokens_to_str(self.runtime, tokens)
                    self._queue.put_nowait((dt, color_line))
        except Exception:
            log.exception('line search error')
            self.close()
            close()
        finally:
            log.debug('finished grep %r -> closed: %s',
                      file, self.is_closed)
