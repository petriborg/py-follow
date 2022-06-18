import os
import sys
from setuptools import setup
from setuptools.command.test import test


class PyTest(test):
    pytest_args = ''
    user_options = [('pytest-args=', 'a', "Arguments to pass to pytest")]

    def initialize_options(self):
        test.initialize_options(self)
        self.pytest_args = ''

    def run_tests(self):
        import shlex
        import pytest
        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


try:
    src_dir = os.path.realpath(os.path.join(__file__, '..'))
    sys.path.append(src_dir)
    import follow

    version = follow.__version__
    description = follow.__doc__
except ImportError:
    follow = None
    version = '0.0.0'
    description = 'Tail (or search) local (or remote) file(s) and colorize ' \
                  'the result.'

test_requires = [
    'pytest > 3.1',
]

setup(
    name='py-follow',
    author='Peter Cooner',
    author_email='petercooner@gmail.com',
    description=description,
    version=version,
    license='GPL 3.0',
    platforms='any',
    packages=[
        'follow',
    ],
    entry_points={
        'console_scripts': [
            'py-follow = follow.main:main',
        ]
    },
    cmdclass={
        'test': PyTest,
    },
    install_requires=[
        'gnureadline;platform_system=="Darwin"',
    ],
    extras_require={
        'test': test_requires
    },
    setup_requires=[],
    tests_require=test_requires,
)
