"""
Main search engine.
"""

import abc
import asyncio
import logging

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

    def __init__(self, queue=None):
        self._queue = queue or asyncio.PriorityQueue()
        super().__init__()

        # start files already part of the runtime
        for file in self.runtime.files:
            asyncio.ensure_future(self.search(file))

    def add(self, obj):
        self.runtime.add(obj)
        if isinstance(obj, ShellCommand):
            asyncio.ensure_future(self.search(obj))

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
        except asyncio.CancelledError:
            log.error('search loop cancelled')
            self.close()
        except:
            log.exception('search loop error')
            self.close()
        finally:
            log.debug('finished search loop -> closed: %s', self.is_closed)

    async def open_file(self, file):
        """
        Open file for search
        :param file:
        :return: subprocess
        """
        log.debug('open %s', file.shell)
        p = await asyncio.create_subprocess_shell(
            file.shell,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return p

    async def search(self, file):
        """
        Search 'file' for 'section.patterns', outputting portions of
        matching 'file'
        :param file: File object
        """
        log.debug('grep %s', file)
        process = await self.open_file(file)

        def close():
            log.debug('close subprocess %r', process)
            try:
                if process.returncode is None:
                    log.debug('terminate %r', process)
                    process.terminate()
            except ProcessLookupError:
                pass

        try:
            while process.returncode is None:
                if self.is_closed:
                    close()
                    break

                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        0.1)
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
        except asyncio.CancelledError:
            self.close()
            close()
        except:
            log.exception('line search error')
            self.close()
            close()
        finally:
            log.debug('finished grep %r -> closed: %s',
                      file, self.is_closed)
