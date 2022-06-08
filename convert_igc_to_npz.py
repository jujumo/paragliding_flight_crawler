#!/usr/bin/env python3
import argparse
import logging
import os.path as path
import re
from typing import Optional
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt


logger = logging.getLogger('snippet')

RECORD_PATTERNS_B = re.compile(
    r'^B'
    r'(?P<hours>\d{2})(?P<minutes>\d{2})(?P<seconds>\d{2})'
    r'(?P<latitude_deg>\d{2})(?P<latitude_min>\d{2})(?P<latitude_dec>\d{3})(?P<NS>[NS])'
    r'(?P<longitude_deg>\d{3})(?P<longitude_min>\d{2})(?P<longitude_dec>\d{3})(?P<EW>[EW])'
    r'(?P<fix>[AV])'
    r'\s*(?P<pressure>\d{5})'
    r'\s*(?P<altitude>\d{5})')


def minutes2degrees(deg, min, dec):
    degrees = float(deg)
    minutes = float(f'{min}.{dec}')
    degrees = degrees + (minutes / 60.)
    # todo: handle N/S E/W
    return degrees


def time2timestamp(hours: str, minutes: str, seconds: str):
    timestamp = (int(hours) * 60 + int(minutes)) * 60 + int(seconds)
    # todo: handle passing 00:00
    return timestamp


def decode_record_b(
        record: str,
        date: datetime):
    record_dict = RECORD_PATTERNS_B.search(record)
    record_dict = record_dict.groupdict()

    time_of_day = timedelta(**{k: int(v) for k, v in record_dict.items() if k in ['hours', 'minutes', 'seconds']})
    timestamp = (date + time_of_day).timestamp()
    latitude = minutes2degrees(record_dict['latitude_deg'], record_dict['latitude_min'], record_dict['latitude_dec'])
    longitude = minutes2degrees(record_dict['longitude_deg'], record_dict['longitude_min'], record_dict['longitude_dec'])
    altitude = float(record_dict['altitude'])
    pressure = float(record_dict['pressure'])
    return [timestamp, longitude,  latitude, altitude, pressure]


def decode_record_h(data: str):
    code = data[1:5]
    if 'FDTE' == code:
        date_str = data[5:]
        date = datetime.strptime(date_str, '%d%m%y')
        return date
    return None


def parse_record_i(data: str):
    nb = int(data[1:3])
    for n in range(nb):
        start = data[3 + n:5 + n]
        print(start)


RECORD_DECODERS = {
    'B': decode_record_b,
    'H': decode_record_h
}


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


def convert_igc_to_array(igc_stream):
    lines = (l.strip() for l in igc_stream)
    records = (l for l in lines if l[0] in RECORD_DECODERS)
    track_list = []
    date = None
    for record in records:
        record_type = record[0]
        if record_type == 'H':
            header = decode_record_h(record)
            if header is not None:
                date = header

        if record_type == 'B':
            assert date is not None
            track_point = decode_record_b(record, date=date)
            track_list.append(track_point)
    track = np.array(track_list)
    return track


def main():
    try:
        parser = argparse.ArgumentParser(description='Description of the program.')
        parser_verbosity = parser.add_mutually_exclusive_group()
        parser_verbosity.add_argument(
            '-v', '--verbose', nargs='?', default=logging.WARNING, const=logging.INFO, action=VerbosityParsor,
            help='verbosity level (debug, info, warning, critical, ... or int value) [warning]')
        parser_verbosity.add_argument(
            '-q', '--silent', '--quiet', action='store_const', dest='verbose', const=logging.CRITICAL)
        parser.add_argument('-i', '--input', type=str, required=True, help='input')
        parser.add_argument('-o', '--output', type=str, help='output file')
        parser.add_argument('-l', '--logfile', type=str, help='log file path. To stdout if None [None]')

        args = parser.parse_args()
        # normalize input path
        args.input = path.abspath(args.input)
        args.output = path.abspath(args.output) if args.output else None
        args.logfile = path.abspath(args.logfile) if args.logfile else None
        if not args.output:
            args.output = path.splitext(args.input)[0] + '.npy'
        # logger stdout
        logger.setLevel(args.verbose)
        create_logger_output(level=args.verbose, logfile=args.logfile)
        # config
        logger.debug('config:\n' + '\n'.join(f'\t\t{k}={v}' for k, v in vars(args).items()))
        with open(args.input) as igc_stream:
            track = convert_igc_to_array(igc_stream)

        with open(args.output, 'wb') as fout:
            np.save(fout, track, allow_pickle=True)

        if args.verbose >= logging.DEBUG:
            print(track)
            plt.scatter(track[:, 0], track[:, 3], marker='x')
            plt.show()

    except Exception as e:
        logger.critical(e)
        if args.verbose <= logging.DEBUG:
            raise


if __name__ == '__main__':
    main()
