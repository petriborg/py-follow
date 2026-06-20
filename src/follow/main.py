import asyncio
import logging
import os
import sys
import argparse

from asyncio import (
    AbstractEventLoop,
)
from asyncio import DefaultEventLoopPolicy


log = logging.getLogger()


def setup_logging(is_debug: bool) -> None:
    """
    Configure logging based on --debug in sys.argv
    :param is_debug:
    """
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    for f in root.filters[:]:
        root.removeFilter(f) 
    logging.basicConfig(
        format='[%(threadName)s][%(levelname)s] %(module)s:%(funcName)s:%('
               'lineno)s %(message)s',
        level=logging.DEBUG if is_debug else logging.INFO,
        stream=sys.stderr,
    )
    fmt = logging.Formatter(
        '[%(threadName)s][%(levelname)s] %(module)s:%(funcName)s:%('
        'lineno)s %(message)s'
    )
    if os.path.exists('error.log'):
        os.replace('error.log', 'error.log.1')
    err_handler = logging.FileHandler('error.log')
    err_handler.setLevel(logging.WARNING)
    err_handler.setFormatter(fmt)
    root.addHandler(err_handler)


class LoopPolicy(DefaultEventLoopPolicy):
    def __init__(self) -> None:
        super().__init__()

    def new_event_loop(self) -> AbstractEventLoop:
        loop = super().new_event_loop()  # type: AbstractEventLoop
        loop.set_exception_handler(handler=exception_handler)
        return loop

    def get_event_loop(self) -> AbstractEventLoop:
        loop = super().get_event_loop()
        loop.set_exception_handler(handler=exception_handler)
        return loop


def exception_handler(loop: asyncio.AbstractEventLoop, ctx: dict) -> None:
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
    exc = ctx.get('exception')
    log.error('Unhandled exception: %s', ctx['message'], exc_info=exc)


async def async_main(options: argparse.Namespace) -> None:
    """
    async main creates a global context for execution
    """
    from .cli import SearchCli
    from .engine import AsyncSearchService

    loop = asyncio.get_running_loop()
    try:
        service = AsyncSearchService(loop=loop)
        cmdline = SearchCli(search_service=service, loop=loop)

        # run main application loop
        await asyncio.gather(cmdline.loop(), service.loop(cmdline))
    finally:
        log.debug('close async loop')


def main() -> None:
    setup_logging('--debug' in sys.argv)

    policy = LoopPolicy()
    asyncio.set_event_loop_policy(policy=policy)
    loop = policy.new_event_loop()

    from .config import argv_parse
    options = argv_parse()
    setup_logging(options.debug)
    try:
        loop.run_until_complete(async_main(options))
    except KeyboardInterrupt:
        pass
