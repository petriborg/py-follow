"""
Matching, colors, terminal string building
"""

import logging
from typing import List, Tuple

from .commands import Match, NegativeMatch, Color, MatchResult, AltReMatch
from .util import (
    coerce_str as _str,
)

log = logging.getLogger()


def build_colors():
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

    for x, (d, l) in enumerate(zip(dark_colors, light_colors), 30):
        codes[d] = esc + '%im' % x
        codes[l] = esc + '%i;01m' % x

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
default_colors = [Plain, Negative] + list(color_lookup.values())


def colorize(matches, line):
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
    colorized = []  # type: List[Tuple[Color, str]]

    def color_first():
        current = matches.pop(0)

        def color_text(start, end):
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
    # log.debug('gather(%d, %s, %s) => %d, %s',
    #           len(patterns), trim_repr(line), requires_match,
    #           len(matches), matched)
    return matches, matched


def tokens_to_str(session, color_line):
    """turn color_line into a color string"""
    reset = session.escape('reset')

    def text(tk):
        color = session.escape(tk[0])
        return _str(color + tk[1] + reset)

    return ''.join(text(c) for c in color_line)
