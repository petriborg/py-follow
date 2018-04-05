"""

"""

import re
import cmd
import sys
import shutil
import logging

from .colorize import Match
from .util import build_repr, coerce_bytes as _bytes, coerce_str as _str

log = logging.getLogger()
_path_re = re.compile(r'([^@]*@)?([^:]*:)?([^:]*)')


def _get_rl():
    """Note this modification fixes Cmd"""
    try:
        import gnureadline as rl
    except ImportError:
        try:
            import readline as rl
            if 'libedit' in rl.__doc__:
                log.warn('MacOS X libedit readline in use, broken')
        except ImportError:
            log.critical('Cannot import readline')
            sys.exit(1)
    return rl


def _parse_path(path):
    log.debug('_parse_path(%r)', path)
    m = _path_re.match(path)
    if not m:
        raise ValueError('Invalid path %r' % path)
    user, host, path = m.groups()
    if user:
        user = user.rstrip('@')
    if host:
        host = host.rstrip(':')
    return user, host, path


def _build_shell_cmd(host, user, path, number=None, follow=True):
    """generate shell command"""

    follow_opt = '-F' if follow else ''
    follow_cmd = '{follow} {follow_opt} -n {number} {path} 2>&1'.format(
        follow='$(command -v gtail || command -v tail)',
        follow_opt=follow_opt,
        number=number,
        path=path,
    )
    if host:
        ssh_opt = '-l ' + user if user else ''
        ssh_cmd = '{ssh} {ssh_opt} {host} "{tail}"'.format(
            ssh='ssh',
            ssh_opt=ssh_opt,
            host=host,
            tail=follow_cmd,
        )
        sh_cmd = ssh_cmd
    else:
        sh_cmd = follow_cmd
    return sh_cmd


class _File:
    def __init__(self, path, number=None, follow=False):
        self.path = path
        self.follow = follow
        self.number = 10 if number is None else int(number)

    def __eq__(self, other):
        return self.path == other.path

    @property
    def shell(self):
        user, host, path = _parse_path(self.path)
        return _build_shell_cmd(user, host, path, self.number, self.follow)


class File(_File):
    def __init__(self, path):
        super().__init__(path, number=None, follow=False)

    __repr__ = build_repr('File', 'path')


class Follow(_File):
    def __init__(self, path, number=10):
        super().__init__(path, number=number, follow=True)

    __repr__ = build_repr('Follow', 'path', 'number')


def _cmd(name, doc=''):
    def command(self, line):
        self._file_cmd(name, *line.split())

    command.__name__ = 'do_' + name
    command.__doc__ = doc
    return command


class Cli(cmd.Cmd):
    # Some ANSI/VT100 Terminal Control Escape Sequences
    esc = b'\x1b['
    clear = esc + b'2J'
    clear_line = esc + b'2K'
    save_cursor = esc + b's'
    unsave_cursor = esc + b'u'

    @property
    def goto_input(self):
        height = shutil.get_terminal_size().lines - 1
        return self.esc + _bytes('%d;0H' % ((height + 1),))

    @classmethod
    def set_scroll(cls, n):
        return cls.esc + _bytes('0;%dr' % n)

    def _emit(self, *objects, sep=' ', end='', flush=True):
        """Write bytes to stdout"""
        self.stdout.write(sep.join(_str(o) for o in objects))
        if end:
            self.stdout.write(end)
        if flush:
            self.stdout.flush()

    def emit_line(self, line):
        if self.stop:
            return False
        rl = _get_rl()
        buf = rl.get_line_buffer()
        self._emit('\r', line, end='\n')
        self._emit(self.prompt, buf)
        return True

    stop = False
    prompt = '>>> '
    do_tail = _cmd('tail', 'tail any local or remote file')
    do_match = _cmd('match', 'search all lines for regex')

    def __init__(self, *args, **kwargs):
        self.runtime_add = kwargs['runtime_add']
        del kwargs['runtime_add']
        super().__init__(*args, **kwargs)

    def _file_cmd(self, name, *args):
        if name == 'tail':
            try:
                self.runtime_add(Follow(*args))
            except ValueError as e:
                log.error('%s error - %s', name, e)
        elif name == 'match':
            self.runtime_add(Match(*args))
        else:
            log.error('unknown error - %s %s', name, args)

    def do_quit(self, _):
        """exit application"""
        return True

    def postcmd(self, stop, line):
        """Hook method executed just after a command dispatch is finished."""
        self.stop = stop or self.stop
        return self.stop

    def cmdloop(self, intro=None):
        """Repeatedly issue a prompt, accept input, parse an initial prefix
        off the received input, and dispatch to action methods, passing them
        the remainder of the line as argument.
        """
        self.preloop()
        if self.use_rawinput and self.completekey:
            try:
                readline = _get_rl()
                self.old_completer = readline.get_completer()
                readline.set_completer(self.complete)
                readline.parse_and_bind(self.completekey+": complete")
            except ImportError:
                pass
        try:
            if intro is not None:
                self.intro = intro
            if self.intro:
                self.stdout.write(str(self.intro)+"\n")
            stop = None
            while not stop:
                if self.cmdqueue:
                    line = self.cmdqueue.pop(0)
                else:
                    if self.use_rawinput:
                        try:
                            line = input(self.prompt)
                        except EOFError:
                            line = 'EOF'
                    else:
                        self.stdout.write(self.prompt)
                        self.stdout.flush()
                        line = self.stdin.readline()
                        if not len(line):
                            line = 'EOF'
                        else:
                            line = line.rstrip('\r\n')
                line = self.precmd(line)
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
            self.postloop()
        finally:
            if self.use_rawinput and self.completekey:
                try:
                    readline = _get_rl()
                    readline.set_completer(self.old_completer)
                except ImportError:
                    pass

    def complete(self, text, state):
        """Return the next possible completion for 'text'.

        If a command has not been entered, then complete against command list.
        Otherwise try to call complete_<command> to get list of completions.
        """
        if state == 0:
            readline = _get_rl()
            orig_line = readline.get_line_buffer()
            line = orig_line.lstrip()
            stripped = len(orig_line) - len(line)
            beg_idx = readline.get_begidx() - stripped
            end_idx = readline.get_endidx() - stripped
            if beg_idx > 0:
                command, args, foo = self.parseline(line)
                if command == '':
                    func = self.completedefault
                else:
                    try:
                        func = getattr(self, 'complete_' + command)
                    except AttributeError:
                        func = self.completedefault
            else:
                func = self.completenames
            self.completion_matches = func(text, line, beg_idx, end_idx)
        try:
            return self.completion_matches[state]
        except IndexError:
            return None
