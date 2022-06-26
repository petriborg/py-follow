"""
Command line interface
"""
import shutil
import sys
import logging

from itertools import chain
from functools import partial

from .commands import shell_commands, match_commands
from .util import (
    Closable, term_help,
    # coerce_bytes as _bytes,
    coerce_str as _str,
)

log = logging.getLogger()

try:
    import gnureadline as readline
except ImportError:
    try:
        import readline

        if 'libedit' in readline.__doc__:
            log.warn('MacOS X libedit readline in use, broken')
    except ImportError:
        readline = None

prompt_default = '>>> '


class Terminal:
    """Virtual terminal"""
    # Some ANSI/VT100 Terminal Control Escape Sequences
    # http://www.termsys.demon.co.uk/vtansi.htm
    esc = '\x1b['
    erase_line = esc + '2K'
    erase_down = esc + 'J'
    erase_up = esc + '1J'
    erase_screen = esc + '2J'
    save_cursor = esc + 's'
    unsave_cursor = esc + 'u'

    def __init__(self, stdout=None, stdin=None,
                 prompt=prompt_default, complete_key='tab'):
        self.prompt = prompt
        self.stdout = stdout or sys.stdout
        self.stdin = stdin or sys.stdin
        self.complete_key = complete_key

    @property
    def goto_input(self):
        height = shutil.get_terminal_size().lines - 1
        return self.esc + '%d;0H' % ((height + 1),)

    def set_scroll(self, n):
        return self.esc + ('0;%dr' % n)

    def emit(self, *strings, sep=' ', end='', flush=True):
        """Write string to stdout"""
        self.stdout.write(_str(sep.join(strings)))
        if end:
            self.stdout.write(_str(end))
        if flush:
            self.stdout.flush()

    def emit_line(self, line):
        """Write string line to output without breaking input"""
        buf = readline.get_line_buffer()
        self.emit('\r', line, end='\n')
        self.emit(self.prompt, buf)


def _build_do_cmd(name, doc=''):
    def do_cmd(self, args):
        self._file_cmd(name, args)

    do_cmd.__name__ = 'do_' + name
    do_cmd.__doc__ = doc
    return do_cmd


class SearchCli(Closable):
    """Search command line terminal"""

    def do_list(self, args):
        """List current set of files, colors, and/or matches."""
        if not args:  # output all case
            args = ['files', 'patterns']

        objects = [getattr(self.service.runtime, n, []) for n in args]
        lines = ['Available:'] + [str(o) for o in chain(*objects)]
        self.term.emit('\n'.join(lines), end='\n')

    @staticmethod
    def do_quit(_):
        """Exit application."""
        raise SystemExit

    def do_help(self, _):
        """Shows this help message."""
        cmd_name = ['Commands:'] + self._do_commands
        cmd_docs = [''] + [getattr(self, 'do_' + cmd).__doc__ or ''
                           for cmd in self._do_commands]
        text = term_help(cmd_name, cmd_docs)
        self.term.emit(text, end='\n')

    def __init__(self, search_service, terminal=None):
        super().__init__()
        self.service = search_service
        self.term = terminal or Terminal()

        # build do_<cmd> list
        for cmd, cls in chain(shell_commands.items(), match_commands.items()):
            do_cmd = partial(self._file_cmd, cmd)
            do_cmd.__doc__ = cls.__doc__
            # log.debug('setattr do_%s = %r', cmd, do_cmd)
            setattr(self, 'do_' + cmd, do_cmd)

        # readline completer
        self._prefix = None
        self._possible = []
        self._do_commands = \
            sorted([c[3:] for c in dir(self) if c.startswith('do_')])

    def _file_cmd(self, name, args):
        try:
            if name in shell_commands:
                command = shell_commands[name]
                self.service.add(command(*args))
            elif name in match_commands:
                match = match_commands[name]
                self.service.add(match(*args))
            else:
                log.error('unknown error - %s %s', name, args)
        except ValueError as e:
            log.exception('%s error - %s', name, e)

    @staticmethod
    def parse(line):
        """split line into cmd, args, original"""
        line = line.strip()
        if not line:
            return None, None, line
        if line[0] == '?':
            line = 'help ' + line[1:]
        args = line.split()
        return args[0], args[1:], line

    def onecmd(self, line):
        """execute one command"""
        cmd, args, line = self.parse(line)
        if not cmd:
            return
        method = getattr(self, 'do_' + cmd, None)
        if method is None:
            self.term.emit('Unknown command: ', line, end='\n')
        else:
            return method(args)

    def loop(self):
        """input loop"""
        log.debug('cli loop')
        completer = readline.get_completer()
        readline.set_completer(self.complete)
        readline.parse_and_bind(self.term.complete_key + ": complete")

        try:
            while not self.is_closed:
                try:
                    line = input(self.term.prompt)
                except EOFError:
                    self.close()
                    self.service.close()
                else:
                    self.onecmd(line)
        except SystemExit:
            self.close()
            self.service.close()
        except Exception:
            log.exception('cli loop error')
        finally:
            readline.set_completer(completer)
            log.debug('finished cli loop -> closed: %s', self.is_closed)

    def complete(self, prefix, index):
        """readline complete method"""
        if prefix != self._prefix:
            # build list of possible matches to text
            self._prefix = prefix
            self._possible = \
                [n for n in self._do_commands if n.startswith(prefix)]
        result = None
        try:
            result = self._possible[index]
        except IndexError:
            pass
        log.debug('complete(%r,%r) => %r', prefix, index, result)
        return result
