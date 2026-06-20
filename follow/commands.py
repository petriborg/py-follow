"""
Different command objects which pull data or operate on the data
"""
import re
import typing

from collections import namedtuple
from types import SimpleNamespace
from typing import Any, Union
from itertools import chain

from .util import build_repr, path_re

Color = namedtuple('Color', ['long', 'escape', 'short'])


def _parse_path(path: str) -> tuple[str|None, str|None, str]:
    """parse path input, returning tuple(user, host, path)"""
    m = path_re.match(path)
    if not m:
        raise ValueError('Invalid path %r' % path)
    user, host, path = m.groups()
    if user:
        user = user.rstrip('@')
    if host:
        host = host.rstrip(':')
    return user, host, path


def _build_tail_cmd(user: str | None, host: str | None, path: str, number: int | None = None, follow: bool = True) -> str:
    """generate shell script command"""


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


class ShellCommand(SimpleNamespace):
    """UNIX Shell command that can be piped to search"""

    def __init__(self, exec: str, args: list[str],
                 aliases: list[str] | None = None, remote: tuple[typing.Optional[str], typing.Optional[str]] | tuple[()] = ()) -> None:
        super().__init__(exec=exec, args=args,
                         aliases=aliases or [],
                         remote=remote)

    def __str__(self) -> str:
        return self.shell

    @property
    def ssh(self) -> str:
        user, host = self.remote
        ssh_opt = '-l ' + user if user else ''
        ssh_cmd = '{ssh} {ssh_opt} {host}'.format(
            ssh='ssh',
            ssh_opt=ssh_opt,
            host=host,
        )
        return ssh_cmd

    @property
    def local(self) -> str:
        # TODO handle aliases
        # ex: $(command -v gtail || command -v tail) etc
        return ' '.join(chain([self.exec], self.args))

    @property
    def shell(self) -> str:
        if self.remote:
            return '{ssh} "{local}"'.format(
                ssh=self.ssh,
                local=self.local,
            )
        else:
            return self.local


class Path(SimpleNamespace):
    """Path user@host:/path/to/file"""

    def __init__(self, path: str) -> None:
        user, host, path = _parse_path(path)
        super().__init__(user=user, host=host, path=path)

    @property
    def userhost(self) -> tuple[typing.Optional[str], typing.Optional[str]] | tuple[()]:
        return (self.user, self.host) if self.host else ()


class Tail(ShellCommand):
    """tail [-n int] [-F] <Path>"""

    def __init__(self, path: Union[str, Path], n: int = 10, f: bool = True) -> None:
        if not isinstance(path, Path):
            path = Path(path)
        follow_opt = '-F' if f else ''
        super().__init__('tail', ['-n', str(n), follow_opt, path.path],
                         aliases=['gtail'],
                         remote=path.userhost)


class Open(ShellCommand):
    """cat <Path>"""

    def __init__(self, path: Union[str, Path]):
        if not isinstance(path, Path):
            path = Path(path)
        super().__init__('cat', [path.path],
                         remote=path.userhost)


class File(Open):
    pass


class Follow(Tail):
    pass


class Highlight:
    """Highlight matching text only - highlight <regex> <color>"""

    def __init__(self, regex: str, color: Color|str|None = None):
        if color:
            assert isinstance(color, (Color, str))

        self.color = color
        self.regex = re.compile(regex)

    def finditer(self, line: str) -> typing.Iterator[MatchResult]:
        for m in self.regex.finditer(line):
            yield MatchResult(m, self.color)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Highlight):
            return False
        return self.color == other.color and \
               self.regex == other.regex

    @property
    def type(self) -> str:
        return self.__class__.__name__.lower()

    def __str__(self) -> str:
        if isinstance(self.color, Color):
            color = self.color.long
        elif isinstance(self.color, str):
            color = self.color
        else:
            color = 'None'
        return '%s %s %s' % (
            self.type, self.regex.pattern, color)

    __repr__ = build_repr('Highlight', 'regex', 'color')


class Match(Highlight):
    """Match line and highlight with color - match <regex> [color]"""

    def __init__(self, regex: str, color: str = 'plain') -> None:
        super().__init__(regex=regex, color=color)

    __repr__ = build_repr('Match', 'regex', 'color')


class NegativeMatch(Highlight):
    """Inverse match line - negative <regex> <color>"""

    def __init__(self, regex: str) -> None:
        super().__init__(regex=regex, color=None)

    __repr__ = build_repr('NegativeMatch', 'regex')


shell_commands = dict(
    tail=Tail,
    open=Open,
    file=Open,
    follow=Tail,
)

match_commands = dict(
    match=Match,
    highlight=Highlight,
    negativematch=NegativeMatch,
    negative=NegativeMatch,
)


class AltReMatch:
    """re.Match alternative (hack)"""
    def __init__(self, pos: int, endpos: int, string: str) -> None:
        self.pos = pos
        self.endpos = endpos
        self.string = string

    def start(self) -> int:
        return self.pos

    def end(self) -> int:
        return self.endpos

    def group(self) -> str:
        return self.string


class MatchResult:
    """pattern match result for colorized lines"""

    def __init__(self, match: typing.Union[re.Match[str], AltReMatch], color: typing.Union[Color, str, None]) -> None:
        self.start = match.start()
        self.end = match.end()
        self.text = match.group()
        self.color = color

    __repr__ = build_repr('MatchResult', 'start', 'end', 'text')
