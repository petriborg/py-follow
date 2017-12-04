"""
follow test module run by pytest or by python -m test
"""

import sys
import logging
from os.path import abspath, join

try:
    import test
except ImportError:
    src_dir = abspath(join(__file__, '..', '..'))
    sys.path.append(src_dir)
    import test


def setup_logging(is_debug):
    """
    Configure logging based on --debug in sys.argv
    :param is_debug:
    """
    root = logging.getLogger()
    [root.removeHandler(h) for h in root.handlers[:]]
    [root.removeFilter(f) for f in root.filters[:]]
    logging.basicConfig(
        format='[%(threadName)s][%(levelname)s] %(module)s:%(funcName)s:%('
               'lineno)s %(message)s',
        level=logging.DEBUG if is_debug else logging.INFO,
        stream=sys.stderr,
        )
setup_logging('--debug' in sys.argv)


def main():
    this_module = sys.modules[__name__]
    for name in dir(this_module):
        if name.startswith('test_'):
            getattr(this_module, name)()
    print('All tests completed successfully')


if __name__ == '__main__':
    # main() will discover/run all the test_* methods
    from test.test_config import *
    from test.test_colorize import *
    from test.test_follow import *

    main()
