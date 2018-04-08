import pytest

from textwrap import dedent

from follow.util import column_formatter, term_help


def test_column_formatter():
    widths = [17, 41]
    form = '{col[0]:<{width[0]}} {col[1]:<{width[1]}}'

    titles = ['Foobar-Title', '0123', 'hi there', 'something']
    blobs = ['Blob',
             'This is some long text which would wrap past the 80 column mark '
             'and go onto the next line number of times blah blah blah.',
             'dito',
             'more text here. more text here. more text here.']

    text = column_formatter(form, widths, titles, blobs)
    expected = """\
Foobar-Title      Blob
0123              This is some long text which would wrap
                  past the 80 column mark and go onto the
                  next line number of times blah blah blah.
hi there          dito
something         more text here. more text here. more text
"""

    for idx, (l1, l2) in enumerate(zip(text.splitlines(),
                                       expected.splitlines())):
        assert l1 == l2, 'line %d: %r != %r' % (idx, l1, l2)


def test_term_help():
    titles = ['Foobar-Title', '0123', 'hi there', 'something']
    blobs = ['Blob',
             'This is some long text which would wrap past the 80 column mark '
             'and go onto the next line number of times blah blah blah.',
             'dito',
             'more text here. more text here. more text here.']
    text = term_help(titles, blobs)
    print(text)
    expected = """\
  Foobar-Title  Blob
  0123          This is some long text which would wrap past the 80 column mark
                and go onto the next line number of times blah blah blah.
  hi there      dito
  something     more text here. more text here. more text here.
    """
    for idx, (l1, l2) in enumerate(zip(text.splitlines(),
                                       expected.splitlines())):
        assert l1 == l2, 'line %d: %r != %r' % (idx, l1, l2)

