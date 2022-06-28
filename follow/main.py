import asyncio
import logging
import sys

from asyncio import (
    AbstractEventLoop,
)
from asyncio.unix_events import (
    DefaultEventLoopPolicy,
)


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


class LoopPolicy(DefaultEventLoopPolicy):
    def __init__(self):
        super().__init__()

    def new_event_loop(self) -> AbstractEventLoop:
        loop = super().new_event_loop()  # type: AbstractEventLoop
        loop.set_exception_handler(handler=exception_handler)
        return loop

    def get_event_loop(self) -> AbstractEventLoop:
        loop = super().get_event_loop()
        loop.set_exception_handler(handler=exception_handler)
        return loop


def exception_handler(loop, ctx):
    """
    context is a dict object containing the following keys (new keys may be
            introduced in future Python versions):
    'message': Error message;
    'exception' (optional): Exception object;
    'future'    (optional): asyncio.Future instance;
    'task'      (optional): asyncio.Task instance;
    'handle'    (optional): asyncio.Handle instance;
    'protocol'  (optional): Protocol instance;
    'transport' (optional): Transport instance;
    'socket'    (optional): socket.socket instance;
    'asyncgen'  (optional): Asynchronous generator that caused the exception.
    """
    log.error('Unhandled exception: ' + ctx['message'])


async def async_main(options):
    """
    async main creates a global context for execution
    """
    from .cli import Terminal, SearchCli
    from .engine import AsyncSearchService

    loop = asyncio.get_event_loop()
    try:
        term = Terminal()
        service = AsyncSearchService(loop=loop)
        cmdline = SearchCli(search_service=service, terminal=term, loop=loop)

        # run main application loop
        cli_future = loop.run_in_executor(None, cmdline.loop)
        await asyncio.gather(cli_future, service.loop(term))

    finally:
        log.debug('close async loop')


def main():
    setup_logging('--debug' in sys.argv)

    policy = LoopPolicy()
    asyncio.set_event_loop_policy(policy=policy)
    loop = policy.get_event_loop()

    from .config import argv_parse
    options = argv_parse()
    setup_logging(options.debug)
    try:
        loop.run_until_complete(async_main(options))
    except KeyboardInterrupt:
        pass
