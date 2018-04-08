"""
Test colorize
"""

import logging

from follow.colorize import gather, colorize, \
    Plain, Red, Blue, Green
from follow.commands import Highlight

log = logging.getLogger()


def test_1():
    log.debug('test_1')
    # smaller matches within a larger one

    patterns = [
        Highlight(color=Red, regex='[1]'),
        Highlight(color=Blue, regex='1000100010'),
        ]
    line = '1000100010'
    matches, print_line = gather(patterns, line, False)
    colorized = colorize(matches, line)
    assert colorized == [
        (Red, '1'), (Blue, '000'), (Red, '1'),
        (Blue, '000'), (Red, '1'), (Blue, '0'),
        (Plain, ''),
        ]


def test_2():
    log.debug('test_2')
    # match overrides match overrides match

    patterns = [
        Highlight(color=Red, regex='12345'),
        Highlight(color=Blue, regex='34567'),
        Highlight(color=Green, regex='67890'),
        ]
    line = '1234567890'
    matches, print_line = gather(patterns, line, False)
    colorized = colorize(matches, line)
    assert colorized == [
        (Red, '12'), (Blue, '345'), (Green, '67890'),
        (Plain, '')
        ]


def test_3():
    log.debug('test_3')
    # match within match within match

    patterns = [
        Highlight(color=Red, regex='345678'),
        Highlight(color=Blue, regex='4567'),
        Highlight(color=Green, regex='23456789'),
    ]
    line = '1234567890'
    matches, print_line = gather(patterns, line, False)
    colorized = colorize(matches, line)
    assert colorized == [
        (Plain, '1'), (Green, '2'), (Red, '3'),
        (Blue, '4567'), (Red, '8'), (Green, '9'),
        (Plain, '0')
    ]


def test_4():
    log.debug('test_4')
    # last, shortest match wins

    patterns = [
        Highlight(color=Green, regex='.'),
        Highlight(color=Red, regex='[123]'),
        Highlight(color=Blue, regex='[ABC]'),
        ]
    line = '123ABC'
    matches, print_line = gather(patterns, line, False)
    colorized = colorize(matches, line)
    assert colorized == [
        (Red, '1'), (Red, '2'), (Red, '3'),
        (Blue, 'A'), (Blue, 'B'), (Blue, 'C'),
        (Plain, '')
        ]


def test_5():
    log.debug('test_5')
    # last, shortest match wins

    patterns = [
        Highlight(color=Green, regex='.'),
        Highlight(color=Red, regex='123'),
        Highlight(color=Blue, regex='ABC'),
        ]
    line = '123ABC'
    matches, print_line = gather(patterns, line, False)
    colorized = colorize(matches, line)
    assert colorized == [
        (Green, '1'), (Green, '2'), (Green, '3'),
        (Green, 'A'), (Green, 'B'), (Green, 'C'),
        (Plain, '')
        ]


