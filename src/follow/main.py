import argparse
import asyncio
import os
import sys
import time
import yaml
import logging
import logging.config

from textwrap import dedent
from asyncio import AbstractEventLoop, DefaultEventLoopPolicy
from .util import log

log_filename_default = 'debug.log'
log_format_default = "[%(threadName)s][%(levelname)s] %(module)s:%(funcName)s:%(lineno)s %(message)s"
log_config_yaml_default = dedent("""
    ---
    version: 1
    formatters:
      standard:
        format: '{log_format}'
    handlers:
      console:
        class: logging.StreamHandler
        formatter: standard
        level: {log_level}
      applog:
        class: logging.FileHandler
        formatter: standard
        filename: {log_filename}
        level: {log_level}
    root:
      handlers: [console, applog]
      level: {log_level}
    """)



def setup_logging(
    is_debug: bool,
    is_boot: bool = False,
    log_filename: str = log_filename_default,
    log_format: str = log_format_default,
    log_config: str = log_config_yaml_default,
) -> None:
    """setup application logging"""
    if os.path.exists(log_filename):
        os.replace(log_filename, log_filename+'.1')
    if is_boot:
        logging.basicConfig(
            format=log_format,
            level=logging.DEBUG if is_debug else logging.DEBUG,
            stream=sys.stdout,
        )
        return

    log_config = log_config.format(
        log_format=log_format,
        log_filename=log_filename,
        log_level='DEBUG' if is_debug else 'INFO',
    )
    data = yaml.load(log_config, yaml.SafeLoader)
    logging.config.dictConfig(data)
    root = logging.getLogger()
    root.info('logging configured')


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


async def heartbeat() -> None:
    """Ticks every second; logs how late the tick was.
    Near-zero lag = loop is healthy. Growing lag = something is
    blocking the event loop synchronously."""
    last = time.monotonic()
    while True:
        await asyncio.sleep(1)
        now = time.monotonic()
        lag = now - last - 1
        log.info('heartbeat tick, loop lag=%.3fs', lag)
        last = now


async def async_main(options: argparse.Namespace) -> None:
    from .cli import SearchCli
    from .engine import AsyncSearchService

    loop = asyncio.get_running_loop()
    service = AsyncSearchService(loop=loop)
    cmdline = SearchCli(search_service=service, loop=loop)
    hb_task = asyncio.ensure_future(heartbeat())

    await asyncio.gather(cmdline.loop(), service.loop(cmdline))

    hb_task.cancel()

    # Cancel any remaining background tasks (search, close_all, etc.)
    me = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not me]
    for t in pending:
        t.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def main() -> None:
    setup_logging('--debug' in sys.argv)

    policy = LoopPolicy()
    asyncio.set_event_loop_policy(policy=policy)
    loop = policy.new_event_loop()

    from .config import argv_parse
    options = argv_parse()
    loop.set_debug(options.debug)      # <-- new: turn on asyncio debug mode
    loop.slow_callback_duration = 0.05 # <-- new: flag callbacks slower than 50ms
    try:
        loop.run_until_complete(async_main(options))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
