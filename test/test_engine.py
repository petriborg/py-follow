"""

"""

import pytest
from follow.engine import _parse_path, _build_shell_cmd


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
    assert _build_shell_cmd(*_parse_path(path), 10, follow) == expected
