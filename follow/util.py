"""
Common utility methods
"""

import os
import re
import logging

from itertools import zip_longest
from textwrap import wrap
from shutil import get_terminal_size
from datetime import datetime

log = logging.getLogger()
path_re = re.compile(r'([^@]*@)?([^:]*:)?([^:]*)')
_isdigit_re = re.compile(r'[0-9]*')


def isdigit(s):
    return _isdigit_re.match(s)


def ispath(s):
    """matches user@host:/path"""
    return path_re.match(s)


def expand_path(path):
    """expand environment variables and tilda in path"""
    if '$' in path:
        path = os.path.expandvars(path)
    if '~' in path:
        path = os.path.expanduser(path)
    return path


def syslog_date(line, now=None, fmt='%b %d %H:%M:%S'):
    """Parse a log line, returning the datetime at the start of a line"""
    if now is None:
        now = datetime.now()
    try:
        # example: Dec  2 20:16:21
        dt = datetime.strptime(line[:14], fmt)
        dt = dt.replace(year=now.year)
        return dt
    except ValueError:
        return now


def coerce_str(data):
    """coerce data to str type"""
    if not isinstance(data, str) and hasattr(data, 'decode'):
        data = data.decode('utf-8')
    return data


def coerce_bytes(data):
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


def trim_repr(obj, length=4, sep='...'):
    """returns a trimmed repr string of obj"""
    obj_repr = repr(obj)
    return obj_repr[:length] + sep + obj_repr[-length:]


def term_help(left_rows, right_rows,
              indent=2, sep=2):
    """
    returns text blob of two columns with indent and separator.
    """
    # two columns with separator and indent are just 4 columns where column
    # index 0 and 2 are empty space
    form = ''.join('{col[%d]:<{width[%d]}}' % (i, i) for i in range(4))

    page_width = get_terminal_size().columns
    left_width = max(len(r) for r in left_rows)
    right_width = page_width - sum([sep, indent, left_width])
    widths = [indent, left_width, sep, right_width]
    indent_rows = ['' for _ in range(len(left_rows))]
    sep_rows = ['' for _ in range(len(left_rows))]

    return column_formatter(form, widths,
                            indent_rows, left_rows,
                            sep_rows, right_rows)


def column_formatter(format_str, widths, *columns):
    """
    format_str describes the format of the report.
    {col[i]} is replaced by data from the ith element of columns.

    widths is expected to be a list of integers.
    {width[i]} is replaced by the ith element of the list widths.

    All the power of Python's string format spec is available for you to use
    in format_str. You can use it to define fill characters, alignment, width, type, etc.

    formatter takes an arbitrary number of arguments.
    Every argument after format_str and widths should be a list of strings.
    Each list contains the data for one column of the report.

    formatter returns the report as one big string.
    https://stackoverflow.com/q/3096402/2815

    NOTE: each str.format() result needs rstrip() to avoid right-side padding
    """
    log.debug('column_formatter(%r, %r, *%r)', format_str, widths, columns)
    result = []
    for row in zip(*columns):
        lines = [wrap(elt, width=num) for elt, num in zip(row, widths)]
        for line in zip_longest(*lines, fillvalue=''):
            result.append(format_str.format(width=widths, col=line).rstrip())
    return '\n'.join(result)


def first(func, iterable, default=None, index=True):
    """
    Returns the first item of iterable for which function(item) is true.
    If function is None, return the first item that is truthy. If nothing
    evaluates to true the default value is returned.
    If index is True, return the index or None.
    """
    for idx, i in enumerate(iterable):
        if func is None and i or func(i):
            return idx, i if index else i
    return None, default if index else default


class Closable:
    def __init__(self):
        self._closed = False

    @property
    def is_closed(self):
        return self._closed

    def close(self):
        log.debug('Closing %r', self)
        self._closed = True


class Singleton(type):
    """metaclass"""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = \
                super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
