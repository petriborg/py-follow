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


def get_words(words_dict_fn):
    try:
        # read cache file if possible
        with open(words_dict_fn) as fh:
            return fh.read().splitlines()
    except IOError:
        pass

    global_word_file = "/usr/share/dict/words"
    try:
        with open(global_word_file) as fh:
            return fh.read().splitlines()
    except IOError:
        pass

    word_site = ("https://svnweb.freebsd.org/csrg/share/dict/words"
                 "?view=co&content-type=text/plain")
    import requests
    try:
        rsp = requests.get(word_site, headers={'user-agent': 'curl/7'})
        if rsp.ok:
            try:
                with open(words_dict_fn, 'wb') as fh:
                    fh.write(rsp.content)
            except IOError:
                pass   # we don't care if we fail to write cache file
            return rsp.content.decode().splitlines()
        else:
            log.error('HTTP request failed: %s', rsp.reason)
    except Exception as e:
        log.error('HTTP request error: %s', e)

    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', '--dt', '--datetime', default=False, action='store_true'
    )
    parser.add_argument(
        '-s', '--sleep', default=.3, type=float,
    )
    parser.add_argument(
        '--words-file', default='.loggen_words_dict', type=str,
    )
    parser.add_argument(
        '--output-file', default=None, type=str,
    )
    options = parser.parse_args()
    use_dt = options.dt

    dictionary = get_words(options.words_file)
    fh = None
    try:
        if options.output_file:
            fh = open(options.output_file, 'w')
        while True:
            time.sleep(options.sleep)
            line = (' '.join([random.choice(dictionary) for _ in range(5)]))
            if use_dt:
                dt = datetime.now().strftime('%b %d %H:%M:%S')
                line = dt + ' ' + line
            if fh:
                fh.write(line)
                fh.write('\n')
                fh.flush()

            print(line, flush=True)
    except IOError:
        pass
    finally:
        if options.output_file and fh:
            try:
                fh.close()
            except IOError:
                pass  # ignore close errors


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
