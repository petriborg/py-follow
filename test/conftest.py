"""

"""

import sys

from os.path import abspath, join, realpath


def pytest_configure(config):
    root = abspath(realpath(join(__file__, '../..')))
    sys.path.append(root)
