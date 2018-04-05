"""
Common utility methods
"""

import os
from datetime import datetime


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


class Singleton(type):
    """metaclass"""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = \
                super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
