import asyncio
import logging
import sys

from .cli import Terminal, SearchCli
from .engine import AsyncSearchService
from .config import argv_parse

log = logging.getLogger()


def setup_logging(is_debug):
    """
    Configure logging based on --debug in sys.argv
    :param is_debug:
    """
    root = logging.getLogger()
    [root.removeHandler(h) for h in root.handlers[:]]
    [root.removeFilter(f) for f in root.filters[:]]
    logging.basicConfig(
        format='[%(threadName)s][%(levelname)s] %(module)s:%(funcName)s:%('
               'lineno)s %(message)s',
        level=logging.DEBUG if is_debug else logging.INFO,
        stream=sys.stderr,
    )


def async_main(options):
    """
    async main creates a global context for execution
    """
    loop = asyncio.get_event_loop()
    try:
        term = Terminal()
        service = AsyncSearchService()
        cmdline = SearchCli(search_service=service, terminal=term)

        # run main application loop
        cli_future = loop.run_in_executor(None, cmdline.loop)
        service_future = asyncio.Task(service.loop(term))
        loop.run_until_complete(asyncio.gather(
            cli_future, service_future))

        # wait for search processes to exit
        pending = asyncio.all_tasks(loop=loop)
        log.debug('shutting down %d pending', len(pending))
        loop.run_until_complete(asyncio.gather(*pending))

    except asyncio.CancelledError as e:
        log.error('main caught %r', e)
    finally:
        log.debug('close async loop')
        if not loop.is_closed():
            loop.close()


def main():
    setup_logging('--debug' in sys.argv)
    options = argv_parse()
    setup_logging(options.debug)
    async_main(options)
