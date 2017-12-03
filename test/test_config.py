import logging

from textwrap import dedent
from follow import parse_config, File, Follow, \
    Match, Highlight, NegativeMatch, Color

log = logging.getLogger()


def test_6():
    log.debug('test_6')
    # test yaml config file

    assert parse_config(dedent("""
    - test
    - basic
    - yaml
    """)) == ['test', 'basic', 'yaml']

    assert repr(parse_config(dedent("""
    - !file [path/to/file]
    - !follow [path/to/file]
    """))) == repr([
        File('path/to/file'),
        Follow('path/to/file'),
    ])

    assert repr(parse_config(dedent("""
    - !color [red, '#00ff00', 'r']
    """))) == repr([
        Color('red', '#00ff00', 'r'),
    ])

    assert repr(parse_config(dedent("""
    - !match [regex, !color [red, '#00ff00', 'r']]
    - !highlight [regex, !color [red, '#00ff00', 'r']]
    """))) == repr([
        Match(color=Color('red', '#00ff00', 'r'), regex='regex'),
        Highlight(color=Color('red', '#00ff00', 'r'), regex='regex'),
    ])

    assert repr(parse_config(dedent("""
    - !match [regex, red]
    - !highlight [regex, red]
    """))) == repr([
        Match(color='red', regex='regex'),
        Highlight(color='red', regex='regex'),
    ])

    assert repr(parse_config(dedent("""
    - !negativematch [regex]
    - !negative-match [regex]
    - !nmatch [regex]
    """))) == repr([
        NegativeMatch('regex'),
        NegativeMatch('regex'),
        NegativeMatch('regex'),
    ])

