"""
Matching, colors, terminal string building
"""

from typing import Any, Iterable

from .commands import Match, NegativeMatch, Color, MatchResult, AltReMatch
from .util import (
    coerce_str as _str,
    log,
)


def build_colors() -> dict[str, Color]:
    """generate list of Color objects for terminal"""
    cli = {  # shortcuts for program arguments
        'green': 'g',
        'red': 'r',
        'blue': 'b',
        'yellow': 'y',
    }
    dark_colors = ['black', 'darkred', 'darkgreen', 'brown', 'darkblue',
                   'purple', 'teal', 'lightgray']
    light_colors = ['darkgray', 'red', 'green', 'yellow', 'blue',
                    'fuchsia', 'turquoise', 'white']

    esc = '\x1b['

    codes = {
        'reset': esc + '39;49;00m',

        'bold': esc + '01m',
        'faint': esc + '02m',
        'standout': esc + '03m',
        'underline': esc + '04m',
        'blink': esc + '05m',
        'overline': esc + '06m',
    }

    for x, (dark, light) in enumerate(zip(dark_colors, light_colors), 30):
        codes[dark] = esc + '%im' % x
        codes[light] = esc + '%i;01m' % x

    # aliases
    codes['darkteal'] = codes['turquoise']
    codes['darkyellow'] = codes['brown']
    codes['fuscia'] = codes['fuchsia']
    codes['white'] = codes['bold']
    codes['magenta'] = codes['purple']
    codes['cyan'] = codes['teal']

    # build color objects
    return {name: Color(name, code, cli.get(name))
            for name, code in codes.items()}


color_lookup = build_colors()
Plain = Color('plain', '', 'e')
Negative = Color('negative', '', 'v')  # negative match
Red = color_lookup['red']
Blue = color_lookup['blue']
Yellow = color_lookup['yellow']
Green = color_lookup['green']
Reset = color_lookup['reset']
default_colors = [Plain, Negative, Reset] + [c for k,c in color_lookup.items() if k!='reset']


def colorize(matches: Iterable[MatchResult], line: str) -> list[tuple[Color|str|None, str]]:
    """
    Colorize lines based on matches.
    Covers -
    * matches next to each other
    * matches that completely overlap other matches
    * matches that overlap only the tail of the previous match
    :param matches: MatchResult iter
    :param line: text
    :return: color line
    """
    m = AltReMatch(0, len(line), line)
    matches = [MatchResult(m, Plain)] + sorted(matches, key=lambda m: (m.start, -m.end))
    colorized: list[tuple[Color|str|None, str]] = []

    def color_first() -> int:
        current = matches.pop(0)

        def color_text(start: int, end: int) -> None:
            nonlocal current
            if end == start:
                return  # skip over empty str
            colorized.append((current.color, line[start:end]))

        if matches and current.end > matches[0].start:  # next overlaps current
            if matches and current.end < matches[0].end:  # next overlaps tail of current
                color_text(current.start, matches[0].start)
                idx = color_first()
            else:  # next overlap is encompassed by current
                idx = current.start
                while matches and matches[0].start < current.end:  # next still overlaps
                    color_text(idx, matches[0].start)
                    idx = color_first()
                if current.end > idx:  # last overlap remainder
                    color_text(idx, current.end)
                    idx = current.end
            return idx
        else:  # no overlap
            color_text(current.start, current.end)
            return current.end

    # recursively process matches
    color_first()
    return colorized


def gather(patterns: list[Any], line: str, requires_match: bool) -> tuple[list[MatchResult], bool]:
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
    # log.debug('gather(%d, %s, %s) => %d, %s',
    #           len(patterns), trim_repr(line), requires_match,
    #           len(matches), matched)
    return matches, matched


def tokens_to_str(session: Any, color_line: list[tuple[Color|str|None, str]]) -> str:
    """turn color_line into a color string"""
    reset = session.escape('reset')

    def text(tk: tuple[Color|str|None, str]) -> str:
        if tk[0]:
            color = session.escape(tk[0])
            return _str(color + tk[1] + reset)
        else:
            return tk[1]

    return ''.join(text(c) for c in color_line)
