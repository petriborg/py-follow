"""
Test colorize
"""

import logging

from follow.colorize import gather, colorize, \
    Plain, Red, Blue, Green
from follow.commands import Highlight

log = logging.getLogger()


def test_1():
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
    ]


def test_2():
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
    ]


def test_3():
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
    ]


def test_5():
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
    ]


def test_6():
    patterns = [
        Highlight(color=Red,  regex='1'),
    ]
    line = 'A11AA11'
    matches, print_line = gather(patterns, line, False)
    colorized = colorize(matches, line)
    assert colorized == [
        (Plain, 'A'),
        (Red, '1'),
        (Red, '1'),
        (Plain, 'AA'),
        (Red, '1'),
        (Red, '1'),
    ]


def test_8():
    patterns = [
        Highlight(color=Red, regex='[1]'),
        Highlight(color=Blue, regex='1000100010'),
        Highlight(color=Green, regex='A1000100010B'),
    ]
    line = 'A1000100010B'
    matches, print_line = gather(patterns, line, False)
    colorized = colorize(matches, line)
    assert colorized == [
        (Green, 'A'),
        (Red, '1'), (Blue, '000'), (Red, '1'),
        (Blue, '000'), (Red, '1'), (Blue, '0'),
        (Green, 'B'),
    ]
