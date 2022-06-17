#!/usr/bin/env python3
import argparse
import logging
import os.path as path
import re
from typing import Optional, Dict
from tqdm import tqdm
import pandas as pd
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from flight_index import load_index


logger = logging.getLogger('print_index')




class VerbosityParsor(argparse.Action):
    """ accept debug, info, ... or theirs corresponding integer value formatted as string."""

    def __call__(self, parser, namespace, values, option_string=None):
        try:  # in case it represent an int, directly get it
            values = int(values)
        except ValueError:  # else ask logging to sort it out
            assert isinstance(values, str)
            values = logging.getLevelName(values.upper())
        setattr(namespace, self.dest, values)


def main():
    try:
        parser = argparse.ArgumentParser(description='.')
        parser_verbosity = parser.add_mutually_exclusive_group()
        parser_verbosity.add_argument(
            '-v', '--verbose', nargs='?', default=logging.WARNING, const=logging.INFO, action=VerbosityParsor,
            help='verbosity level (debug, info, warning, critical, ... or int value) [warning]')
        parser_verbosity.add_argument(
            '-q', '--silent', '--quiet', action='store_const', dest='verbose', const=logging.CRITICAL)
        parser.add_argument('-i', '--input', required=True,
                            help='path to index file.')

        args = parser.parse_args()

        logger.setLevel(args.verbose)
        logger.debug('config:\n' + '\n'.join(f'\t\t{k}={v}' for k, v in vars(args).items()))

        # load existing
        df = load_index(args.input)
        wings = set(df['wing_name'])
        makers = set(wing.split('-')[0].strip() for wing in wings)
        # print(sorted(makers))
        count = df['wing_name'].value_counts()
        print(count)
        # durations = df['distance'].to_numpy()
        # plt.hist(durations, bins=range(0, 300))
        # plt.show()

    except Exception as e:
        logger.critical(e)
        if args.verbose <= logging.DEBUG:
            raise


if __name__ == '__main__':
    main()
