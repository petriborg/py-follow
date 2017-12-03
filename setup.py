import os
import sys
import platform
from setuptools import setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to pytest")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def run_tests(self):
        import shlex
        # import here, cause outside the eggs aren't loaded
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
    version = '0.0.0'
    description = 'Tail (or search) local (or remote) file(s) and colorize ' \
                  'the result.'

osx_requires = [
    'gnureadline'
    ]
requires = []
if platform.platform().startswith('Darwin'):
    requires.extend(osx_requires)

setup(
    name='py-follow',
    author='Peter Cooner',
    author_email='petercooner@gmail.com',
    description=description,
    version=version,
    license='GPL 3.0',
    platforms='any',
    #packges=[
    #    ],
    py_modules=[
        'follow'
        ],
    entry_points={
        'console_scripts': [
            'py-follow = follow:main',
            ]
        },
    cmdclass={
        'test': PyTest,
        },
    install_requires=requires,
    setup_requires=[],
    tests_require=[
        'pytest'
        ],
    )


