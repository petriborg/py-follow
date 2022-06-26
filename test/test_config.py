import logging

from textwrap import dedent

from follow.colorize import Red
from follow.commands import (
    Highlight, Match, NegativeMatch, Color, File, Follow
)
from follow.config import parse_repr_config, parse_yaml_config

log = logging.getLogger()


def test_8():
    # test to make sure classes equality work right
    assert Follow('foo') == Follow('foo')
    assert Match('rez', 'red') == Match('rez', 'red')
    assert Color(long='red', escape='\x1b[31;01m', short='r') == Red
    assert {'a': Follow('a')} == {'a': Follow('a')}


def test_7():
    # test repr config file
    assert parse_repr_config(dedent("""
    {
    'syslog': [
        Follow('/foo/bar'),
        Match('baz', 'red'),
        ]
    }
    """)) == {
        'syslog': [
            Follow(path='/foo/bar', n=10),
            Match(color='red', regex='baz')
        ]
    }


def test_6():
    # test yaml config file
    assert parse_yaml_config(dedent("""
    - test
    - basic
    - yaml
    """)) == ['test', 'basic', 'yaml']

    assert repr(parse_yaml_config(dedent("""
    - !file [path/to/file]
    - !follow [path/to/file]
    """))) == repr([
        File('path/to/file'),
        Follow('path/to/file'),
    ])

    assert repr(parse_yaml_config(dedent("""
    - !color [red, '#00ff00', 'r']
    """))) == repr([
        Color('red', '#00ff00', 'r'),
    ])

    assert repr(parse_yaml_config(dedent("""
    - !match [regex, !color [red, '#00ff00', 'r']]
    - !highlight [regex, !color [red, '#00ff00', 'r']]
    """))) == repr([
        Match(color=Color('red', '#00ff00', 'r'), regex='regex'),
        Highlight(color=Color('red', '#00ff00', 'r'), regex='regex'),
    ])

    assert repr(parse_yaml_config(dedent("""
    - !match [regex, red]
    - !highlight [regex, red]
    """))) == repr([
        Match(color='red', regex='regex'),
        Highlight(color='red', regex='regex'),
    ])

    assert repr(parse_yaml_config(dedent("""
    - !negativematch [regex]
    - !negative-match [regex]
    - !nmatch [regex]
    """))) == repr([
        NegativeMatch('regex'),
        NegativeMatch('regex'),
        NegativeMatch('regex'),
    ])
