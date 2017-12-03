#!/usr/bin/env python -u
"""
Generates a pseudo log for testing
"""

import time
import random


def get_words():
    word_file = "/usr/share/dict/words"
    try:
        with open(word_file) as fh:
            return fh.read().splitlines()
    except IOError:
        pass

    word_site = "http://svnweb.freebsd.org/csrg/share/dict/words?view=co&content-type=text/plain"
    try:
        from urllib.request import urlopen
    except ImportError:
        from urllib2 import urlopen  # pylint:
    response = urlopen(word_site)
    txt = response.read()
    return txt.splitlines()


def main():
    dictionary = get_words()
    while True:
        time.sleep(2)
        print(' '.join([random.choice(dictionary) for _ in range(5)]))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
