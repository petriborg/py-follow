#!/usr/bin/env python3
"""
Generates a pseudo log for testing
"""

import time
import random
import logging
import argparse

from datetime import datetime

log = logging.getLogger()


def get_words():
    word_file = "/usr/share/dict/words"
    try:
        with open(word_file) as fh:
            return fh.read().splitlines()
    except IOError:
        pass

    word_site = ("https://svnweb.freebsd.org/csrg/share/dict/words"
                 "?view=co&content-type=text/plain")
    import requests
    try:
        rsp = requests.get(word_site, headers={'user-agent': 'curl/7'})
        if rsp.ok:
            return rsp.content.decode().splitlines()
        else:
            log.error('HTTP request failed: %s', rsp.reason)
    except Exception as e:
        log.error('HTTP request error: %s', e)

    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dt', '--datetime', default=False, action='store_true'
    )
    options = parser.parse_args()
    use_dt = options.dt

    dictionary = get_words()
    while True:
        time.sleep(.3)
        line = (' '.join([random.choice(dictionary) for _ in range(5)]))
        if use_dt:
            dt = datetime.now().strftime('%b %d %H:%M:%S')
            line = dt + ' ' + line
        print(line, flush=True)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
