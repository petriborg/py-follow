"""
Matching, colors, terminal string building
"""

import logging

from .commands import Match, NegativeMatch, Color
from .util import coerce_str as _str

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
    Colorize lines based on matches
    :param matches: MatchResult iter
    :param line: text
    :return: color line
    """
    matches = sorted(matches, key=lambda m: (m.start, -m.end))
    colorized = []

    # log.debug('matches %r', matches)

    def inner():
        match = matches.pop(0)
        idx = match.start

        if matches and matches[0].start <= match.end:
            while matches:
                if idx < matches[0].start:
                    colorized.append(
                        (match.color, line[idx:matches[0].start]))
                idx = inner()
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

    # log.debug('colorize() => %r', colorized)
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
