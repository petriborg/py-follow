"""
Configuration file processing, sys.argv processing, and runtime configuration
"""

import argparse
import logging
import os
import re
from io import StringIO
from itertools import chain

from .commands import Color, Highlight, Match, NegativeMatch, \
    File, Follow, ShellCommand
from .colorize import Plain, Negative, default_colors
from .util import expand_path, build_repr, Singleton

log = logging.getLogger()
default_config_file = '~/.py-follow'


class ConfigGroup:
    """represents current set of patterns"""

    def __init__(self, name, *args):
        self.name = name
        self.colors = {}
        self.patterns = []
        self.requires_match = False  # True if Match object in patterns
        self.add(*args)

    def color(self, token):
        reset = self.colors.get('reset')
        if isinstance(token, str):
            return self.colors.get(token, reset)
        else:
            return self.colors.get(token.long, reset)

    def escape(self, token):
        return self.color(token).escape

    def add(self, *args):
        """add object to session"""
        for obj in args:
            if isinstance(obj, Color):
                self.colors[obj.long] = obj
            elif isinstance(obj, Match):
                if isinstance(obj.color, str):
                    obj.color = self.colors[obj.color]
                self.patterns.append(obj)
                self.requires_match = True
            elif isinstance(obj, Highlight):
                if isinstance(obj.color, str):
                    obj.color = self.colors[obj.color]
                self.patterns.append(obj)
            else:
                raise ValueError('Unknown obj type %r' % type(obj).__name__)

    __repr__ = build_repr('Group', 'name')


class Runtime(ConfigGroup, metaclass=Singleton):
    """Runtime configuration"""

    def __init__(self, *args):
        super().__init__('runtime', *args)
        self.files = []

    def add(self, *args):
        remain = []
        for obj in args:
            if isinstance(obj, ShellCommand):
                log.debug('add file %r', obj)
                self.files.append(obj)
            else:
                remain.append(obj)
        super().add(*remain)

    __repr__ = build_repr('Runtime')


def parse_config_file(config_file, group_names):
    """
    Reads config_file and adds groups to section
    :param config_file:
    :param group_names:
    """
    config_file = expand_path(config_file)
    if os.path.isfile(config_file):
        log.debug('parsing config %r, %r', config_file, group_names)
        try:
            with open(config_file) as fh:
                content = fh.read()
                buf_fh = StringIO(content)
                # repr content must be a dictionary, search for { ignoring
                # any comments coming before it
                stripped = ''.join(ln.split('#', 1)[0].strip() for ln in
                                   content.splitlines(True))
                if re.match(r'\A{', stripped, re.MULTILINE):
                    groups = parse_repr_config(buf_fh)
                else:
                    groups = parse_yaml_config(buf_fh)
                return chain(*[groups[z] for z in group_names])
        except ImportError:
            log.error('Config file requires yaml module')
        except:
            log.critical('Parse yaml config', exc_info=True)
    return []


def parse_repr_config(stream):
    """
    read config_file, returns a dict of lists containing namespace objects.
    Example -
    {
    'syslog': [
      Follow('/var/log/messages'),
      Highlight('regex', 'red'),
      ]
    }
    """
    if hasattr(stream, 'read'):
        content = stream.read()
    else:
        log.debug('stream %r', stream)
        content = stream
    with_globals = [File, Follow, Highlight, Match, NegativeMatch, Color]
    return eval(content, {c.__name__: c for c in with_globals})


def parse_yaml_config(stream):
    """
    read config_file, add dict of lists containing namespace objects.
    expected format -
    section-name:
      - !ctor [args...]
    Example -
    syslog:
      - !follow [/var/log/messages]
      - !highlight ['regex', 'red']
    """
    import yaml

    def build_ctor(class_object):
        def ctor(loader, node):
            log.debug('ctor(loader, node=%r)', node)
            args = loader.construct_sequence(node)
            return class_object(*args)

        return ctor

    with_globals = [File, Follow, Highlight, Match, NegativeMatch, Color]
    for cls in with_globals:
        yaml.add_constructor('!' + cls.__name__.lower(),
                             build_ctor(cls))
    yaml.add_constructor('!nmatch', build_ctor(NegativeMatch))
    yaml.add_constructor('!negative-match', build_ctor(NegativeMatch))

    data = yaml.load(stream)
    log.debug('parse_config(stream) => %r', data)
    return data


def argv_parse():
    def _get_action_name(argument):
        """Work around for http://bugs.python.org/issue11874"""
        from argparse import SUPPRESS
        if argument is None:
            return None
        elif argument.option_strings:
            return '/'.join(argument.option_strings)
        elif argument.metavar not in (None, SUPPRESS):
            return argument.metavar.format(user_host_file='[[USER@]HOST:]FILE')
        elif argument.dest not in (None, SUPPRESS):
            return argument.dest
        else:
            return None

    argparse._get_action_name = _get_action_name

    class ConfigAction(argparse.Action):
        """Expand file path"""

        def __call__(self, p, namespace, values, option_string=None):
            setattr(namespace, self.dest, expand_path(values))

    class HostHelpFormatter(argparse.HelpFormatter):
        """Work around for http://bugs.python.org/issue11874"""

        def _format_usage(self, usage, actions, groups, prefix):
            result = super()._format_usage(usage, actions, groups, prefix)
            return result.format(user_host_file='[[USER@]HOST:]FILE')

        def _format_action_invocation(self, action):
            result = super()._format_action_invocation(action)
            return result.format(user_host_file='[[USER@]HOST:]FILE')

    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument(
        '--config', '-c', default=default_config_file, action=ConfigAction
    )
    config_parser.add_argument(
        '-z', metavar='Z', default=[], dest='group_names', action='append',
    )

    options, ignore = config_parser.parse_known_args()
    log.debug('initial options %r', options)

    cfg_objects = parse_config_file(options.config, options.group_names)
    log.debug('config objects %r', cfg_objects)

    # add files, patterns, colors, etc from the configuration
    session = Runtime(*default_colors)
    session.add(*cfg_objects)

    # import the parent follow package high level description and version
    from . import __doc__ as desc
    from . import __version__ as version

    parser = argparse.ArgumentParser(
        description=desc,
        formatter_class=HostHelpFormatter,
    )
    parser.add_argument(
        '--version', action='version', version='%(prog)s ' + version
    )
    parser.add_argument(
        '--debug', default=False, dest='debug', action='store_true',
        help='enable debug',
    )
    parser.add_argument(
        '--config', '-c',
        metavar='CFG', default=default_config_file, action=ConfigAction,
        help='configuration file, default %(default)s',
    )
    parser.add_argument(
        '-f', default=False, dest='follow', action='store_true',
        help='follow FILE(s)',
    )
    parser.add_argument(
        '-n', metavar='N', default=10, dest='lines', type=int,
        help='output the last N lines, instead of last %(default)s',
    )
    parser.add_argument(
        '-z', metavar='Z', default=[], dest='group_names', action='append',
        help='Load Z group(s) from CFG file'
    )
    parser.add_argument(
        'files',
        metavar='{user_host_file}',
        nargs='*' if session.files else argparse.PARSER,
        help='input files from local or remote hosts',
    )

    def build_action(color):
        """generate action for color"""

        class MatchAction(argparse.Action):
            def __call__(self, parse, namespace, values, option_string=None):
                color_short = option_string[-1]
                if color_short.isupper():
                    matcher = Highlight(color=color, regex=values)
                elif color == Negative:
                    matcher = NegativeMatch(regex=values)
                else:
                    matcher = Match(color=color, regex=values)
                previous = getattr(namespace, self.dest)
                if previous:
                    previous.append(matcher)
                else:
                    setattr(namespace, self.dest, [matcher])

        return MatchAction

    parser.add_argument(
        '-e', metavar='PTRN', dest='patterns',
        action=build_action(Plain),
        default=[], help='match',
    )
    parser.add_argument(
        '-v', metavar='PTRN', dest='patterns',
        action=build_action(Negative),
        default=[], help='invert match',
    )

    # for colors with shortcuts, create arguments
    for section_color in session.colors.values():
        if len(section_color.short or '') == 1 and \
                section_color.long not in (Plain.long, Negative.long):
            log.debug('add color option %r', section_color)
            meta = 'PTRN'
            name = section_color.long
            parser.add_argument(
                '-' + section_color.short.lower(),
                '-' + section_color.short.upper(),
                metavar=meta, dest='patterns',
                action=build_action(section_color),
                default=[], help='match/highlight %s with %s' % (meta, name),
            )

    options = parser.parse_args()
    log.debug('final options %r', options)

    # add patterns from arguments
    session.add(*options.patterns)
    return options
