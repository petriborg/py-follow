"""
Main search engine.
"""

import abc
import asyncio
from typing import Any, Awaitable
from asyncio import AbstractEventLoop, PriorityQueue

from .commands import ShellCommand
from .ssh import close_all
from .util import Closable, syslog_date, coerce_str as _str
from .colorize import colorize, gather, tokens_to_str
from .util import log


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
        self._queue = queue or asyncio.PriorityQueue(maxsize=100)
        self._search_tasks: list[asyncio.Task] = []
        super().__init__()

        for file in self.runtime.files:
            task = asyncio.ensure_future(self.search(file), loop=self._loop)
            self._search_tasks.append(task)

    def add(self, obj: Any) -> None:
        self.runtime.add(obj)
        if isinstance(obj, ShellCommand):
            task = asyncio.ensure_future(self.search(obj), loop=self._loop)
            self._search_tasks.append(task)

    async def loop(self, terminal: Any) -> None:
        try:
            log.debug('search loop -> closed: %s', self.is_closed)
            while not self.is_closed:
                dt, line = await self._queue.get()
                terminal.emit_line(line)
                await asyncio.sleep(0)
        except Exception:
            self.close()
            raise
        finally:
            log.debug('finished search loop -> closed: %s', self.is_closed)

    async def open_file(self, file: Any) -> Any:
        proc = await file.run()
        log.debug('open_file(%s) => %r', getattr(file, 'shell', '<no shell>'), proc)
        return proc

    def close(self):
        for task in self._search_tasks:
            task.cancel()
        self._search_tasks.clear()
        super().close()
        asyncio.ensure_future(close_all(), loop=self._loop)

    async def search(self, file: Any) -> None:
        process = None
        try:
            process = await self.open_file(file)
            log.debug('search %r', process)

            while True:
                try:
                    assert process.stdout is not None
                    byte_line = await process.stdout.readline()
                except asyncio.CancelledError:
                    break

                if not byte_line:
                    break

                line = _str(byte_line).rstrip()
                matches, print_line = gather(
                    self.runtime.patterns, line, self.runtime.requires_match)
                if print_line:
                    dt = syslog_date(line)
                    tokens = colorize(matches, line)
                    color_line = tokens_to_str(self.runtime, tokens)
                    await self._queue.put((dt, color_line))
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception('line search error')
            self.close()
        finally:
            log.debug('finished grep %r -> closed: %s',
                      file, self.is_closed)
            if process is not None and process.returncode is None:
                try:
                    process.terminate()
                except (ProcessLookupError, OSError):
                    pass
