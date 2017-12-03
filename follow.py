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

import os
import re
import sys
import atexit
import shutil
import logging
import argparse
import threading

from queue import PriorityQueue, Empty
from datetime import datetime
from itertools import chain
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor

__version__ = '0.2.0'
log = logging.getLogger()
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
setup_logging('--debug' in sys.argv)

try:
    import gnureadline as rl
except ImportError:
    try:
        import readline as rl
        if 'libedit' in rl.__doc__:
            log.warn('MacOS X libedit readline in use, broken')
    except ImportError:
        rl = None
        log.critical('Cannot import readline')
        sys.exit(1)

if rl:
    # Release references early at shutdown (the readline module's
    # contents are quasi-immortal, and the completer function holds a
    # reference to globals).
    atexit.register(lambda: rl.set_completer(None))


def expand_path(path):
    """expand environment variables and tilda in path"""
    if '$' in path:
        path = os.path.expandvars(path)
    if '~' in path:
        path = os.path.expanduser(path)
    return path


def _str(data):
    """coerce data to str type"""
    if not isinstance(data, str) and hasattr(data, 'decode'):
        data = data.decode('utf-8')
    return data


def _bytes(data):
    """coerce data to bytes type"""
    if not isinstance(data, bytes) and hasattr(data, 'encode'):
        data = data.encode('utf-8')
    return data


def build_repr(clz, *attributes):
    """generate __repr__ method for builder classes"""
    def method(self):
        init = ', '.join('%s=%r' % (a, getattr(self, a)) for a in attributes)
        return '%s(%s)' % (clz, init)
    return method


class File:
    """file"""
    def __init__(self, path):
        self.path = path
        m = re.match(r'([^@]*@)?([^:]*:)?([^:]*)', path)
        if not m:
            raise ValueError('Invalid path %r' % path)
        self._user, self._host, self._path = m.groups()
        if self._user:
            self._user = self._user.rstrip('@')
        if self._host:
            self._host = self._host.rstrip(':')
        self._type = self.__class__.__name__
        self._follow = False
        self._process = None
        self._fh = None
        self.number = None

    def open(self):
        if self._host or self._follow:
            return self._follow_file()
        else:
            return self._open_local_file()

    def _open_local_file(self):
        log.debug('open(%r)', self.path)
        self._fh = open(self._path, 'r')
        return self._fh

    def _follow_file(self):
        # TODO handle sudo
        from subprocess import Popen, PIPE

        follow_opt = '-F' if self._follow else ''
        follow_cmd = '{follow} {follow_opt} -n {number} {path} 2>&1'.format(
            follow='$(command -v gtail || command -v tail)',
            follow_opt=follow_opt,
            number=self.number,
            path=self._path,
        )
        if self._host:
            ssh_opt = '-l '+self._user if self._user else ''
            ssh_cmd = '{ssh} {ssh_opt} {host} "{tail}"'.format(
                ssh='ssh',
                ssh_opt=ssh_opt,
                host=self._host,
                tail=follow_cmd,
            )
            cmd = ssh_cmd
        else:
            cmd = follow_cmd
        log.debug('Popen(%r, ...)', cmd)

        self._process = Popen(
            cmd,
            stdout=PIPE,
            shell=True,
        )
        return self._process.stdout

    @property
    def is_open(self):
        return self._fh is not None or self._process is not None

    def close(self):
        if self._process:
            try:
                if self._process and self._process.returncode is None:
                    self._process.terminate()
                    self._process = None
                    self._fh = None
            except ProcessLookupError:
                pass
        elif self._fh:
            self._fh.close()
            self._fh = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *args):
        self.close()

    __repr__ = build_repr('File', 'path')
Open = File


class Follow(File):
    """follow/tail a file"""
    def __init__(self, path, number=10):
        super().__init__(path)
        self.number = number
        self._follow = True

    __repr__ = build_repr('Follow', 'path', 'number')
Tail = Follow


class MatchResult:
    """pattern match result for colorized lines"""
    def __init__(self, match, color):
        self.start = match.start()
        self.end = match.end()
        self.text = match.group()
        self.color = color

    __repr__ = build_repr('MatchResult', 'start', 'end', 'text')


class Highlight:
    """Highlight matching text only"""
    def __init__(self, regex, color):
        if color:
            assert isinstance(color, (Color, str))

        self._type = self.__class__.__name__
        self.color = color
        self.regex = re.compile(regex)

    def finditer(self, line):
        for m in self.regex.finditer(line):
            yield MatchResult(m, self.color)

    __repr__ = build_repr('Highlight', 'color', 'regex')


class Match(Highlight):
    """Match object with color"""
    def __init__(self, regex, color):
        super().__init__(regex=regex, color=color)
        self._type = self.__class__.__name__

    __repr__ = build_repr('Match', 'color', 'regex')


class NegativeMatch(Highlight):
    """Inverse match object"""
    def __init__(self, regex):
        super().__init__(regex=regex, color=None)
        self._type = self.__class__.__name__

    __repr__ = build_repr('NegativeMatch', 'regex')


def build_colors():
    """generate list of Color objects for terminal"""
    cli = {  # shortcuts for program arguments
        'green': 'g',
        'red': 'r',
        'blue': 'b',
        'yellow': 'y',
    }
    dark_colors = ["black", "darkred", "darkgreen", "brown", "darkblue",
                   "purple", "teal", "lightgray"]
    light_colors = ["darkgray", "red", "green", "yellow", "blue",
                    "fuchsia", "turquoise", "white"]

    esc = "\x1b["

    codes = {
        "reset": esc + "39;49;00m",

        "bold": esc + "01m",
        "faint": esc + "02m",
        "standout": esc + "03m",
        "underline": esc + "04m",
        "blink": esc + "05m",
        "overline": esc + "06m",
    }

    for x, (d, l) in enumerate(zip(dark_colors, light_colors), 30):
        codes[d] = esc + "%im" % x
        codes[l] = esc + "%i;01m" % x

    # aliases
    codes["darkteal"] = codes["turquoise"]
    codes["darkyellow"] = codes["brown"]
    codes["fuscia"] = codes["fuchsia"]
    codes["white"] = codes["bold"]

    # build color objects
    return {name: Color(name, code, cli.get(name))
            for name, code in codes.items()}

Color = namedtuple('Color', ['long', 'escape', 'short'])
color_lookup = build_colors()
Plain = Color('plain', '', 'e')
Negative = Color('negative', '', 'v')  # negative match
Red = color_lookup['red']
Blue = color_lookup['blue']
Yellow = color_lookup['yellow']
Green = color_lookup['green']
default_colors = [Plain, Negative] + list(color_lookup.values())


def colorize(matches, line):
    """
    Colorize lines based on matches
    :param matches: MatchResult iter
    :param line: text
    :return: color line
    """
    matches = sorted(matches, key=lambda m: (m.start, -m.end))
    colorized = []
    log.debug('matches %r', matches)

    def inner():
        match = matches.pop(0)
        idx = match.start
        log.debug('match %r', match)

        if matches and matches[0].start <= match.end:
            while matches:
                if idx < matches[0].start:
                    colorized.append(
                        (match.color, line[idx:matches[0].start]))
                idx = inner()
                log.debug('inner() => %d', idx)
                if not matches and idx < match.end:
                    colorized.append(
                        (match.color, line[idx:match.end]))
                    idx = match.end
            return idx

        else:
            colorized.append(
                (match.color, line[match.start:match.end]))
            return match.end

    last_end = 0
    while matches:
        if matches[0].start > 0:
            colorized.append(
                (Plain, line[last_end:matches[0].start]))
        last_end = inner()
    colorized.append(
        (Plain, line[last_end:]))

    log.debug('colorize() => %r', colorized)
    return colorized


def gather(patterns, line, requires_match):
    """search line for matches"""
    matched = not requires_match
    matches = []
    for pattern in patterns:
        for match in pattern.finditer(line):
            if isinstance(pattern, NegativeMatch):
                matched = False
                break
            elif isinstance(pattern, Match):
                matched = True
            matches.append(match)
    repr_line = repr(line)
    trim_line = repr_line[:4] + '...' + repr_line[-4:]
    log.debug('gather(%d, %s, %s) => %d, %s',
              len(patterns), trim_line, requires_match, len(matches), matched)
    return matches, matched


def tokens_to_str(session, color_line):
    """turn color_line into a color string"""
    reset = session.escape('reset')

    def text(tk):
        color = session.escape(tk[0])
        return _str(color+tk[1]+reset)

    return ''.join(text(c) for c in color_line)


def search(session, queue, file):
    """search file for matches"""
    threading.current_thread().setName('thread-%r' % file)
    fh = file.open()
    try:
        year = datetime.now().year
        while file.is_open:
            line = _str(fh.readline()).rstrip()
            if not line:
                break

            matches, print_line = \
                gather(session.patterns, line, session.requires_match)
            if print_line:
                try:
                    # example: Dec  2 20:16:21
                    dt = datetime.strptime(line[:14], '%b %d %H:%M:%S')
                    dt = dt.replace(year=year)
                except ValueError:
                    dt = datetime.now()
                tokens = colorize(matches, line)
                color_line = tokens_to_str(session, tokens)
                queue.put_nowait((dt, color_line))
    except:
        log.critical('search failed!', exc_info=True)
    finally:
        log.debug('exiting %r loop', file)
        file.close()


class Completer(ThreadPoolExecutor):
    """Readline tab completion and user prompt"""

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

    def __init__(self, session, prompt=b'>>> '):
        super().__init__()

        namespace = (File, Open, Follow, Tail,
                     Highlight, Match, NegativeMatch)
        self.prompt = _bytes(prompt)
        self.namespace = {c.__name__.lower(): c for c in namespace}
        self.session = session
        self._commands = [c[8:] for c in dir(self)
                          if c.startswith('command_')]
        self._stdout_queue = PriorityQueue()
        self._prefix = None
        self._possible = []
        self._futures = []
        self._files = []

        rl.parse_and_bind("tab: complete")
        rl.set_completer(self.complete)

    @property
    def is_shutdown(self):
        with self._shutdown_lock:
            return self._shutdown

    @staticmethod
    def emit(*args):
        """Write bytes to stdout"""
        stdout_write_bytes = sys.stdout.buffer.write
        stdout_write_bytes(b''.join(args))

    def complete(self, prefix, index):
        """readline complete method"""
        if prefix != self._prefix:
            # build list of possible matches to text
            self._prefix = prefix
            self._possible = \
                [n for n in chain(self.namespace, self._commands)
                 if n.startswith(prefix)]
        try:
            result = self._possible[index]
        except IndexError:
            result = None
        finally:
            log.debug('complete(%r,%r) => %r', prefix, index, result)
            return result

    def search(self, file):
        """start search file task"""
        f = self.submit(search, self.session, self._stdout_queue, file)
        self._files.append(file)
        self._futures.append(f)

    def command_help(self):
        print('Commands:')
        for c in chain(self._commands, self.namespace):
            print(c)

    def command_files(self):
        print('Files:')
        for f in self._files:
            print(repr(f))

    def command_threads(self):
        if not self.is_shutdown:
            print('Threads:')
            for t in threading.enumerate():
                print(repr(t))

    def command_quit(self):
        log.debug('quit command')
        if not self.is_shutdown:
            self.shutdown(False)

    def eval(self, command):
        """eval command and push to executor"""
        if command in self._commands:
            try:
                getattr(self, 'command_'+command, None)()
            except:
                log.critical('command failed!', exc_info=True)
            return
        elif any(command.startswith(ns) for ns in self.namespace):
            try:
                obj = eval(command, self.namespace, self.namespace)
            except SyntaxError:
                log.error('Command error: %r', command)
            else:
                if isinstance(obj, File):
                    self.search(obj)
                else:
                    self.session.add(obj)
                log.debug('eval(%r) -> %r', command, obj)
        else:
            log.error('Unknown command: %r', command)
            return

    def shutdown(self, wait=True):
        if self.is_shutdown:
            return
        self.emit(self.set_scroll(0), self.goto_input, b'exiting...\n')
        # close open files / processes
        for file in self._files:
            file.close()
        for future in self._futures:
            future.cancel()
        for t in threading.enumerate():
            log.debug('pre-thread %r', t)
        super().shutdown(wait)

    def cli(self):
        """prompt - main thread loop"""
        try:
            threading.current_thread().setName('thread-prompt')
            while not self.is_shutdown:
                self.emit(self.save_cursor, self.goto_input, self.clear_line)
                try:
                    cmd = input(_str(self.prompt))
                except ValueError:
                    continue
                except EOFError:
                    # TODO why not exiting cleanly?
                    log.debug('input raised EOFError')
                    if not self.is_shutdown:
                        self.shutdown(False)
                    return
                else:
                    self.eval(cmd)
                    self.emit(self.set_scroll(0), self.goto_input,
                              self.clear_line)
                finally:
                    self.emit(self.unsave_cursor)
        except KeyboardInterrupt:
            log.debug('raised KeyboardInterrupt')
            if not self.is_shutdown:
                self.shutdown(False)
        finally:
            log.debug('exiting cli loop')

    def readline_stdout(self):
        """output"""
        try:
            threading.current_thread().setName('thread-stdout')
            while not self.is_shutdown:
                try:
                    dt, line = self._stdout_queue.get(True, 0.1)
                except Empty:
                    line = None
                if line:
                    # NOTE MacOS X libedit uses some circular buffer? Need hack
                    buf = rl.get_line_buffer()

                    self.emit(self.clear_line, b'\r', _bytes(line), b'\n')
                    self.emit(self.prompt, _bytes(buf))
        except Exception as ex:
            log.exception(ex)
        finally:
            log.debug('exiting prompt loop')


class Section:
    """represents current set of patterns"""
    def __init__(self, name, *args):
        self.name = name
        self.colors = {}
        self.patterns = []
        self.requires_match = False  # True if Match object in patterns
        self.add(*args)

    def color(self, token):
        reset = self.colors.get('reset')
        if isinstance(token, str):
            return self.colors.get(token, reset)
        else:
            return self.colors.get(token.long, reset)

    def escape(self, token):
        return self.color(token).escape

    def add(self, *args):
        """add object to session"""
        for obj in args:
            if isinstance(obj, Color):
                self.colors[obj.long] = obj
            elif isinstance(obj, Match):
                if isinstance(obj.color, str):
                    obj.color = self.colors[obj.color]
                self.patterns.append(obj)
                self.requires_match = True
            elif isinstance(obj, Highlight):
                if isinstance(obj.color, str):
                    obj.color = self.colors[obj.color]
                self.patterns.append(obj)
            else:
                raise ValueError('Unknown obj type %r' % type(obj).__name__)

    __repr__ = build_repr('Section', 'name', 'objects')


def parse_config_file(config_file, group_names):
    """
    Reads config_file and adds groups to section
    :param config_file:
    :param group_names:
    """
    config_file = expand_path(config_file)
    if os.path.isfile(config_file):
        log.debug('parsing config %r, %r', config_file, group_names)
        try:
            with open(config_file) as fh:
                groups = parse_config(fh)
                return chain(*[groups[z] for z in group_names])
        except ImportError:
            log.error('Config file requires yaml module')
    return []


def parse_config(stream):
    """
    read config_file, add patterns, etc to section.
    expected format -
    section-name:
      - !ctor [args...]
    Example -
    syslog:
      - !follow [/var/log/messages]
      - !highlight ['regex', 'red']
    """
    import yaml

    def build_ctor(class_object):
        def ctor(loader, node):
            log.debug('ctor(loader, node=%r)', node)
            args = loader.construct_sequence(node)
            return class_object(*args)
        return ctor

    for cls in [File, Follow, Highlight, Match, NegativeMatch, Color]:
        yaml.add_constructor('!'+cls.__name__.lower(),
                             build_ctor(cls))
    yaml.add_constructor('!nmatch', build_ctor(NegativeMatch))
    yaml.add_constructor('!negative-match', build_ctor(NegativeMatch))

    data = yaml.load(stream)
    log.debug('parse_config(stream) => %r', data)
    return data


def main():
    def _get_action_name(argument):
        """Work around for http://bugs.python.org/issue11874"""
        from argparse import SUPPRESS
        if argument is None:
            return None
        elif argument.option_strings:
            return '/'.join(argument.option_strings)
        elif argument.metavar not in (None, SUPPRESS):
            return argument.metavar.format(user_host_file='[[USER@]HOST:]FILE')
        elif argument.dest not in (None, SUPPRESS):
            return argument.dest
        else:
            return None
    argparse._get_action_name = _get_action_name

    class ConfigAction(argparse.Action):
        """Expand file path"""
        def __call__(self, p, namespace, values, option_string=None):
            setattr(namespace, self.dest, expand_path(values))

    class HostHelpFormatter(argparse.HelpFormatter):
        """Work around for http://bugs.python.org/issue11874"""
        def _format_usage(self, usage, actions, groups, prefix):
            result = super()._format_usage(usage, actions, groups, prefix)
            return result.format(user_host_file='[[USER@]HOST:]FILE')

        def _format_action_invocation(self, action):
            result = super()._format_action_invocation(action)
            return result.format(user_host_file='[[USER@]HOST:]FILE')

    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument(
        '--config', '-c', default=default_config_file, action=ConfigAction
        )
    config_parser.add_argument(
        '-z', metavar='Z', default=[], dest='group_names', action='append',
        )

    options, ignore = config_parser.parse_known_args()
    log.debug('initial options %r', options)

    session = Section('RUNTIME')
    session.add(*default_colors)
    config_files = []
    for cfg in parse_config_file(options.config, options.group_names):
        if isinstance(cfg, File):
            config_files.append(cfg)
        else:
            session.add(cfg)
    log.debug('files from config %r', config_files)

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=HostHelpFormatter,
        )
    parser.add_argument(
        '--version', action='version', version='%(prog)s '+str(__version__)
        )
    parser.add_argument(
        '--debug', default=False, dest='debug', action='store_true',
        help='enable debug',
        )
    parser.add_argument(
        '--config', '-c',
        metavar='CFG', default=default_config_file, action=ConfigAction,
        help='configuration file, default %(default)s',
        )
    parser.add_argument(
        '-f', default=False, dest='follow', action='store_true',
        help='follow FILE(s)',
        )
    parser.add_argument(
        '-n', metavar='N', default=10, dest='lines', type=int,
        help='output the last N lines, instead of last %(default)s',
        )
    parser.add_argument(
        '-z', metavar='Z', default=[], dest='group_names', action='append',
        help='Load Z group(s) from CFG file'
        )
    parser.add_argument(
        'files',
        metavar='{user_host_file}',
        nargs='*' if config_files else argparse.PARSER,
        help='input files from local or remote hosts',
        )

    def build_action(color):
        """generate action for color"""
        class MatchAction(argparse.Action):
            def __call__(self, parse, namespace, values, option_string=None):
                color_short = option_string[-1]
                if color_short.isupper():
                    matcher = Highlight(color=color, regex=values)
                elif color == Negative:
                    matcher = NegativeMatch(regex=values)
                else:
                    matcher = Match(color=color, regex=values)
                previous = getattr(namespace, self.dest)
                if previous:
                    previous.append(matcher)
                else:
                    setattr(namespace, self.dest, [matcher])

        return MatchAction

    parser.add_argument(
        '-e', metavar='PTRN', dest='patterns',
        action=build_action(Plain),
        default=[], help='match',
        )
    parser.add_argument(
        '-v', metavar='PTRN', dest='patterns',
        action=build_action(Negative),
        default=[], help='invert match',
        )

    # for colors with shortcuts, create arguments
    for section_color in session.colors.values():
        if len(section_color.short or '') == 1 and \
           section_color.long not in (Plain.long, Negative.long):
            log.debug('add color option %r', section_color)
            meta = 'PTRN'
            name = section_color.long
            parser.add_argument(
                '-'+section_color.short.lower(),
                '-'+section_color.short.upper(),
                metavar=meta, dest='patterns',
                action=build_action(section_color),
                default=[], help='match/highlight %s with %s' % (meta, name),
                )
    options = parser.parse_args()
    log.debug('final options %r', options)
    setup_logging(options.debug)

    # setup session, matches, highlights, files, etc
    session.add(*options.patterns)

    # start thread pool and setup prompt
    with Completer(session) as executor:
        for file in config_files:
            executor.search(file)

        # command line files
        for file in options.files:
            if options.follow:
                executor.search(Follow(file, options.lines))
            else:
                executor.search(File(file))

        # command line prompt
        executor.submit(executor.readline_stdout)

        # main thread loop
        executor.cli()


if __name__ == '__main__':
    main()

