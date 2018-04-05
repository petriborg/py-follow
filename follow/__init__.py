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

import sys
import logging

from .util import coerce_str as _str, syslog_date
from .config import argv_parse, Runtime
from .engine import Cli, Follow, File
from .colorize import colorize, gather, tokens_to_str

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
    import signal
    import asyncio

    from asyncio.queues import PriorityQueue, QueueEmpty

    section = Runtime()
    queue = PriorityQueue()
    loop = asyncio.get_event_loop()

    def runtime_add(obj):
        log.debug('adding new runtime: %r', obj)
        section.add(obj)
        if isinstance(obj, (File, Follow)):
            asyncio.ensure_future(search(obj), loop=loop)

    async def search(sfile):
        """
        Search 'file' for 'section.patterns', outputting portions of matching 'file'
        :param sfile: File object
        """
        log.debug('grep %r', sfile.path)

        process, close = await open_file(sfile)
        try:
            while process.returncode is None:
                if cli.stop:
                    close()
                    await process.wait()
                    log.debug('wait process %r exit', process)
                    break

                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(), 0.1)
                    line = _str(line).rstrip()
                except asyncio.TimeoutError:
                    continue

                matches, print_line = gather(
                    section.patterns, line, section.requires_match)
                if print_line:
                    dt = syslog_date(line)
                    tokens = colorize(matches, line)
                    color_line = tokens_to_str(section, tokens)
                    queue.put_nowait((dt, color_line))
        except asyncio.CancelledError:
            close()
        finally:
            log.debug('finished grep %r', sfile.path)

    async def open_file(ofile):
        """
        open tail on 'file'
        :param ofile:
        :return: tuple of file handle, and close method
        """
        process = await asyncio.create_subprocess_shell(
            ofile.shell,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # close_fds=True,
            # start_new_session=True,  # alternative to preexec_fn
            # universal_newlines=True,
        )

        def close():
            log.debug('close subprocess %r', process)
            try:
                if process.returncode is None:
                    log.debug('terminate %r', process)
                    process.terminate()
            except ProcessLookupError:
                pass

        return process, close

    cli = Cli(runtime_add=runtime_add)

    def sig_exit():
        cli.stop = True
        for task in asyncio.Task.all_tasks(loop=loop):
            log.debug('pending %r', task)
            task.cancel()
        log.debug('finished signal exit')

    async def print_queue(cli_instance):
        try:
            while not cli_instance.stop:
                try:
                    dt, line = queue.get_nowait()
                except QueueEmpty:
                    await asyncio.sleep(0.1)
                else:
                    cli_instance.emit_line(line)
        except asyncio.CancelledError:
            cli_instance.stop = True
        finally:
            log.debug('finished print queue')

    def cli_loop():
        try:
            cli.cmdloop()
        finally:
            log.debug('finished cli loop')

    try:
        # setup signal handler
        loop.add_signal_handler(signal.SIGINT, sig_exit)

        # create initial application processes
        for fn in options.files:
            if options.follow:
                runtime_add(Follow(fn, options.lines))
            else:
                runtime_add(File(fn))

        # run main application loop
        cli_future = loop.run_in_executor(None, cli_loop)
        print_future = asyncio.ensure_future(print_queue(cli))
        loop.run_until_complete(asyncio.gather(
            cli_future, print_future))

        # wait for search processes to exit
        loop.run_until_complete(asyncio.gather(
            *asyncio.Task.all_tasks(loop=loop)))

    except asyncio.CancelledError as e:
        log.error('main caught %r', e)
    finally:
        log.debug('close loop')
        loop.close()


def main():
    options = argv_parse()
    setup_logging(options.debug)

    async_main(options)


if __name__ == '__main__':
    main()
