#!/usr/bin/env python3
import argparse
import logging
import os.path as path
import re
from typing import Optional
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pymap3d as pm
from convert_igc_to_npz import convert_igc_to_array


logger = logging.getLogger('compute_polar')


class VerbosityParsor(argparse.Action):
    """ accept debug, info, ... or theirs corresponding integer value formatted as string."""

    def __call__(self, parser, namespace, values, option_string=None):
        try:  # in case it represent an int, directly get it
            values = int(values)
        except ValueError:  # else ask logging to sort it out
            assert isinstance(values, str)
            values = logging.getLevelName(values.upper())
        setattr(namespace, self.dest, values)


def create_logger_output(level, logfile: Optional[str] = None):
    logger_formatter = logging.Formatter('%(name)s::%(levelname)-8s: %(message)s')
    logger_stream = logging.FileHandler(logfile) if logfile else logging.StreamHandler()
    logger_stream.setFormatter(logger_formatter)
    logger_stream.setLevel(level)
    logger.addHandler(logger_stream)
    return logger_stream


def lla2enu(tlla):
    timestamps = tlla[0:1]
    longitudes, latitudes, altitudes = tlla[1:4]
    enu = pm.geodetic2enu(longitudes, latitudes, altitudes, longitudes[0], latitudes[0], altitudes[0])
    enu = np.array(enu)
    tenu = np.vstack([timestamps, enu])
    return tenu


def tenu2speeds(tenu):
    deltas = tenu[:, 1:] - tenu[:, 0:-1]
    # remove jitter
    speed_h = np.linalg.norm(deltas[1:3], axis=0) / deltas[0]
    speed_v = deltas[3] / deltas[0]
    speeds = np.vstack([speed_h, speed_v])
    return speeds


def cleans(speeds):
    # remove jitter
    # horizontal speed limit: 100 km/h = 30m/s
    valid_h = speeds[0] < 30
    # vertical speed limit: 20m/s
    valid_v = np.abs(speeds[1]) < 20
    valid = np.logical_and(valid_v, valid_h)
    speeds = speeds[:, valid]
    return speeds


def interp(array, frequency):
    # fir
    return array


def smooth(array, k=30):
    array = np.vstack([
        np.convolve(array[i], np.ones(k)/k, mode='valid')
        for i in range(4)
    ])
    return array


def compute_polar(tenu):
    speeds = tenu2speeds(tenu=tenu)
    speeds = cleans(speeds)
    return speeds


def main():
    try:
        parser = argparse.ArgumentParser(description='Compute polar.')
        parser_verbosity = parser.add_mutually_exclusive_group()
        parser_verbosity.add_argument(
            '-v', '--verbose', nargs='?', default=logging.WARNING, const=logging.INFO, action=VerbosityParsor,
            help='verbosity level (debug, info, warning, critical, ... or int value) [warning]')
        parser_verbosity.add_argument(
            '-q', '--silent', '--quiet', action='store_const', dest='verbose', const=logging.CRITICAL)
        parser.add_argument('-i', '--input', required=True,
                            help='input')
        parser.add_argument('-s', '--start', type=int,
                            help='start timestamp')
        parser.add_argument('-e', '--end', type=int,
                            help='stop timestamp')
        parser.add_argument('-d', '--duration', type=int,
                            help='duration in seconds')
        parser.add_argument('-k', '--window', type=int, default=30,
                            help='Convolution window size in seconds [30]')
        # parser.add_argument('-o', '--output', help='output file')

        args = parser.parse_args()
        # normalize input path
        args.input = path.abspath(args.input)
        # logger stdout
        logger.setLevel(args.verbose)
        # config
        logger.debug('config:\n' + '\n'.join(f'\t\t{k}={v}' for k, v in vars(args).items()))
        input_ext = path.splitext(args.input)[1]
        if '.npy' == input_ext:
            logger.debug(f'loading {args.input}')
            tlla = np.load(args.input)
        if '.igc' == input_ext:
            logger.debug(f'converting  {args.input}')
            with open(args.input) as igc:
                tlla = convert_igc_to_array(igc_stream=igc)
        # from now on, each row is a data type
        tlla = tlla.transpose()

        k = args.window
        tenu = lla2enu(tlla)
        tenu = smooth(tenu, k=k)
        if args.end:
            tenu = tenu[:args.end]
        if args.start:
            tenu = tenu[args.start:]

        fig, axs = plt.subplots(2)
        axs[0].scatter(tenu[0], tenu[3], c=tenu[0], marker='.')
        speeds = compute_polar(tenu)
        axs[1].scatter(speeds[0], speeds[1], c=tenu[0, 0:-1], marker='.')
        plt.show()

    except Exception as e:
        logger.critical(e)
        if args.verbose <= logging.DEBUG:
            raise


if __name__ == '__main__':
    main()
