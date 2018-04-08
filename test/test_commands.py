"""

"""

import pytest
from follow.commands import _parse_path, _build_tail_cmd, \
    ShellCommand, Tail, Open, Path


@pytest.mark.parametrize('path,expected', [
    ('foo@bar:baz', ('foo', 'bar', 'baz')),
    ('bar:baz',     (None,  'bar', 'baz')),
    ('baz',         (None,  None,  'baz')),
])
def test_parse_path(path, expected):
    assert _parse_path(path) == expected


@pytest.mark.parametrize('path,follow,expected', [
    ('foo@bar:baz', True, 'ssh -l bar foo "$(command -v gtail || command -v '
                          'tail) -F -n 10 baz 2>&1"'),
    ('baz', True, '$(command -v gtail || command -v tail) -F -n 10 baz 2>&1'),
])
def test_build_shell_cmd(path, follow, expected):
    assert _build_tail_cmd(*_parse_path(path), 10, follow) == expected


def test_path_class():
    p1 = Path('user@host:/path')
    assert p1.user == 'user'
    assert p1.host == 'host'
    assert p1.path == '/path'

    p2 = Path('path')
    assert p2.userhost == ()
    assert p2.path == 'path'


def test_shell_cmd():
    p1 = Path('user@host:/path')
    t1 = Tail(p1, 1, False)
    assert t1.shell == 'ssh -l user host "tail -n 1  /path"'

    p2 = Path('/path')
    t2 = Tail(p2)
    assert t2.shell == 'tail -n 10 -F /path'
