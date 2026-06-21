import asyncio
import logging
import os
import sys
import argparse

from asyncio import AbstractEventLoop, DefaultEventLoopPolicy

log = logging.getLogger()


def setup_logging(is_debug: bool) -> None:
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    for f in root.filters[:]:
        root.removeFilter(f)
    logging.basicConfig(
        format='[%(threadName)s][%(levelname)s] %(module)s:%(funcName)s:%(lineno)s %(message)s',
        level=logging.DEBUG if is_debug else logging.INFO,
        stream=sys.stderr,
    )
    fmt = logging.Formatter(
        '[%(threadName)s][%(levelname)s] %(module)s:%(funcName)s:%(lineno)s %(message)s'
    )
    if os.path.exists('error.log'):
        os.replace('error.log', 'error.log.1')
    err_handler = logging.FileHandler('error.log')
    err_handler.setLevel(logging.WARNING)
    err_handler.setFormatter(fmt)
    root.addHandler(err_handler)


class LoopPolicy(DefaultEventLoopPolicy):
    def new_event_loop(self) -> AbstractEventLoop:
        loop = super().new_event_loop()
        loop.set_exception_handler(handler=exception_handler)
        return loop

    def get_event_loop(self) -> AbstractEventLoop:
        loop = super().get_event_loop()
        loop.set_exception_handler(handler=exception_handler)
        return loop


def exception_handler(loop: asyncio.AbstractEventLoop, ctx: dict) -> None:
    exc = ctx.get('exception')
    log.error('Unhandled exception: %s', ctx['message'], exc_info=exc)


async def async_main(options: argparse.Namespace) -> None:
    from .cli import SearchCli
    from .engine import AsyncSearchService

    loop = asyncio.get_running_loop()
    service = AsyncSearchService(loop=loop)
    cmdline = SearchCli(search_service=service, loop=loop)

    await asyncio.gather(cmdline.loop(), service.loop(cmdline))


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
    finally:
        loop.close()
