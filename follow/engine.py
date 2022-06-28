"""
Main search engine.
"""

import abc
import asyncio
import logging
from asyncio import AbstractEventLoop, PriorityQueue

from .commands import ShellCommand
from .util import Closable, syslog_date, coerce_str as _str
from .colorize import colorize, gather, tokens_to_str

log = logging.getLogger()


class SearchService(Closable):
    def __init__(self):
        super().__init__()
        from .config import Runtime
        self.runtime = Runtime()

    @abc.abstractmethod
    def loop(self, term):
        pass

    @abc.abstractmethod
    def add(self, obj):
        pass

    @abc.abstractmethod
    def open_file(self, file):
        pass

    @abc.abstractmethod
    def search(self, file):
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
        self._loop = loop or asyncio.get_event_loop()
        self._queue = queue or asyncio.PriorityQueue()
        super().__init__()

        # start files already part of the runtime
        for file in self.runtime.files:
            asyncio.ensure_future(self.search(file), loop=self._loop)

    def add(self, obj):
        self.runtime.add(obj)
        if isinstance(obj, ShellCommand):
            asyncio.ensure_future(self.search(obj), loop=self._loop)

    async def loop(self, terminal):
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

    async def open_file(self, file):
        """
        Open file for search
        :param file:
        :return: subprocess
        """
        p = await asyncio.create_subprocess_shell(
            file.shell,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            #loop=self._loop,
        )
        log.debug('open_file(%s) => %r', file.shell, p)
        return p

    async def search(self, file):
        """
        Search 'file' for 'section.patterns', queueing colorized output
        for display.
        """
        process = await self.open_file(file)
        log.debug('search %r', process)

        def close():
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
                    line = await asyncio.wait_for(
                        process.stdout.readline(), 0.1)
                    line = _str(line).rstrip()
                except asyncio.TimeoutError:
                    continue

                matches, print_line = gather(
                    self.runtime.patterns, line, self.runtime.requires_match)
                if print_line:
                    dt = syslog_date(line)
                    tokens = colorize(matches, line)
                    color_line = tokens_to_str(self.runtime, tokens)
                    self._queue.put_nowait((dt, color_line))
        except:
            log.exception('line search error')
            self.close()
            close()
        finally:
            log.debug('finished grep %r -> closed: %s',
                      file, self.is_closed)
