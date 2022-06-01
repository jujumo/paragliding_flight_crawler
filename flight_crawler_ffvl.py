#!/usr/bin/env python3
import argparse
import logging
import os
import os.path as path
import re
from typing import Optional
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

logger = logging.getLogger('flight_crawler_ffvl')

FFVL_ROOT_URL = 'https://parapente.ffvl.fr'
DEBUG_MODE = True


def download_flight_info(flight_id: int):
    # flight_id examples: 20000001 - 20010600 - 20201435 - 20319660

    if DEBUG_MODE:
        sample_file_path = path.join(path.dirname(path.abspath(__file__)), 'samples', 'Le vol de JACQUES FOURNIER du 28_04_2022 Parapente.htm')
        with open(sample_file_path, encoding='utf-8') as f:
            content = f.read()
    else:  # not DEBUG
        url = f'{FFVL_ROOT_URL}/cfd/liste/vol/{flight_id}'
        logger.debug(f'parsing page {url}')
        r = requests.get(url)
        content = r.text

    page_bf = BeautifulSoup(content, 'html.parser')

    pilots = [
        a.text.strip()
        for a in page_bf.find_all('a')
        if a.get('href') and a.get('href').startswith(f'{FFVL_ROOT_URL}/pilote/')
    ]
    pilot = next(iter(pilots), None)
    if not pilot:
        logger.debug(f'no data for flight {flight_id}')
        return

    dates = [
        a.text.strip()
        for a in page_bf.find_all('a')
        if a.get('href') and a.get('href').startswith(f'{FFVL_ROOT_URL}/cfd/liste/saison/')
    ]
    date = next(iter(dates), None)

    parenthesis = re.compile(r'\(.*?\)')
    wings = [
        parenthesis.sub('', a.text).strip()
        for a in page_bf.find_all('a')
        if a.get('href') and a.get('href').startswith(f'{FFVL_ROOT_URL}/cfd/liste/aile/')
    ]
    wing = next(iter(wings), None)

    igc_urls = [
        f'{FFVL_ROOT_URL}{a.get("href")}'
        for a in page_bf.find_all('a')
        if a.get('href') and a.get('href').endswith('.igc')
    ]
    igc_url = next(iter(igc_urls), None)

    if False:  # grab more details
        main_section = page_bf.find("section", {"id": "block-system-main"})
        table = main_section.find('ul')
        lines = ([e.strip()
                  for e in line.text.split(':')]
                 for line in table.find_all('li'))
        infos = {e[0]: e[1:] for e in lines}

    flight = {
        'id': 'ffvl/' + str(flight_id),
        'pilot': pilot,
        'date': date,
        'wing': wing,
        'igc': igc_url
    }

    return flight


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


def main():
    try:
        parser = argparse.ArgumentParser(description='Crawl FFVL website to collect flight info.')
        parser_verbosity = parser.add_mutually_exclusive_group()
        parser_verbosity.add_argument(
            '-v', '--verbose', nargs='?', default=logging.WARNING, const=logging.INFO, action=VerbosityParsor,
            help='verbosity level (debug, info, warning, critical, ... or int value) [warning]')
        parser_verbosity.add_argument(
            '-q', '--silent', '--quiet', action='store_const', dest='verbose', const=logging.CRITICAL)
        parser.add_argument('-i', '--flight_id', type=int, required=True,
                            help='flight id (eg. 20321973)')
        parser.add_argument('-o', '--output',
                            help='output path')

        args = parser.parse_args()
        args.output = path.abspath(args.output)

        logger.setLevel(args.verbose)
        create_logger_output(level=args.verbose)

        logger.debug('config:\n' + '\n'.join(f'\t\t{k}={v}' for k, v in vars(args).items()))

        flights = {}
        for flight_id in tqdm(range(20000001, 20000011)):
            flight = download_flight_info(flight_id=flight_id)
            if flight:
                flights[flight_id] = flight
        print(flights)
        # logger.info(flight)

    except Exception as e:
        logger.critical(e)
        if args.verbose <= logging.DEBUG:
            raise


if __name__ == '__main__':
    main()
