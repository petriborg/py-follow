#!/usr/bin/env python3.5 -u
"""
Tail (or search) local (or remote) file(s) and colorize the result.
"""
# NOTES
# http://tldp.org/HOWTO/Bash-Prompt-HOWTO/x361.html
# http://www.termsys.demon.co.uk/vtansi.htm
# https://pewpewthespells.com/blog/osx_readline.html
# https://stackoverflow.com/a/1512051
# https://stackoverflow.com/a/37501797
# https://stackoverflow.com/a/437088

import asyncio
import logging
import sys

from .cli import Terminal, SearchCli
from .commands import Highlight, Match, NegativeMatch, Color, File, Follow
from .config import argv_parse, Runtime
from .engine import AsyncSearchService

__version__ = '0.4.0'
default_config_file = '~/.py-follow'


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


log = logging.getLogger()
setup_logging('--debug' in sys.argv)


def async_main(options):
    """
    async main creates a global context for execution
    """
    loop = asyncio.get_event_loop()
    try:
        term = Terminal()
        service = AsyncSearchService(loop=loop)
        cmdline = SearchCli(search_service=service, terminal=term)

        # run main application loop
        cli_future = loop.run_in_executor(None, cmdline.loop)
        service_future = asyncio.Task(service.loop(term))
        loop.run_until_complete(asyncio.gather(
            cli_future, service_future))

        # wait for search processes to exit
        pending = asyncio.Task.all_tasks(loop=loop)
        log.debug('shutting down %d pending', len(pending))
        loop.run_until_complete(asyncio.gather(*pending))

    except asyncio.CancelledError as e:
        log.error('main caught %r', e)
    finally:
        log.debug('close async loop')
        loop.close()


def main():
    options = argv_parse()
    setup_logging(options.debug)

    async_main(options)


if __name__ == '__main__':
    main()
