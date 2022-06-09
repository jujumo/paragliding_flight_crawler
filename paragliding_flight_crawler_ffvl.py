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
from typing import Dict
import pandas as pd
from multiprocessing import Pool

logger = logging.getLogger('flight_crawler_ffvl')

FFVL_ROOT_URL = 'https://parapente.ffvl.fr'
DEBUG_MODE = False


def ffvl_to_flight_id(ffvl_flight_id: int) -> str:
    return f'ffvl/{ffvl_flight_id}'


def download_flight_info(ffvl_flight_id: int):
    # flight_id examples: 20000001 - 20010600 - 20201435 - 20319660

    if DEBUG_MODE:
        sample_file_path = path.join(path.dirname(path.abspath(__file__)), 'samples', '20320226.htm')
        with open(sample_file_path, encoding='utf-8') as f:
            content = f.read()
    else:  # not DEBUG
        url = f'{FFVL_ROOT_URL}/cfd/liste/vol/{ffvl_flight_id}'
        # logger.debug(f'parsing page {url}')
        r = requests.get(url)
        content = r.text

    page_bf = BeautifulSoup(content, 'html.parser')

    ffvl_flight_id_link_re = re.compile(re.escape(f'{FFVL_ROOT_URL}/cfd/liste/vol/') + r'(?P<ffvl_flight_id>\d+)')
    ffvl_flight_ids = {
        ffvl_flight_id_link_re.search(a.get('href')).groupdict()['ffvl_flight_id']
        for a in page_bf.find_all('a')
        if a.get('href') and ffvl_flight_id_link_re.search(a.get('href'))
    }
    ffvl_flight_id_actual = next(iter(ffvl_flight_ids), None)

    pilots = [
        a.text.strip()
        for a in page_bf.find_all('a')
        if a.get('href') and a.get('href').startswith(f'{FFVL_ROOT_URL}/pilote/')
    ]
    pilot = next(iter(pilots), None)
    if not pilot:
        logger.debug(f'no data for flight {ffvl_flight_id}')
        return

    dates = [
        a.text.strip()
        for a in page_bf.find_all('a')
        if a.get('href') and a.get('href').startswith(f'{FFVL_ROOT_URL}/cfd/liste/saison/')
    ]
    date = next(iter(dates), None)

    parenthesis = re.compile(r'\(.*?\)')
    wing_names = [
        parenthesis.sub('', a.text).strip()
        for a in page_bf.find_all('a')
        if a.get('href') and a.get('href').startswith(f'{FFVL_ROOT_URL}/cfd/liste/aile/')
    ]
    wing_name = next(iter(wing_names), None)

    wing_ids = [
        int(a.get('href').split('/')[-1])
        for a in page_bf.find_all('a')
        if a.get('href') and a.get('href').startswith(f'{FFVL_ROOT_URL}/cfd/liste/aile/')
    ]
    wing_id = next(iter(wing_ids), None)

    igc_urls = [
        f'{a.get("href")}'
        for a in page_bf.find_all('a')
        if a.get('href') and a.get('href').endswith('.igc')
    ]
    igc_url = next(iter(igc_urls), None)

    main_section = page_bf.find("section", {"id": "block-system-main"})
    table = main_section.find('ul')
    lines = ([e.strip()
              for e in line.text.split(':')]
             for line in table.find_all('li'))
    infos = {e[0]: e[1:] for e in lines}

    flight_type = infos.get('type de vol', [None])[0]
    flight_takeoff = infos.get('décollage', [None])[0]
    flight_landing = infos.get('atterrissage', [None])[0]
    flight_distance = infos.get('distance totale', [None])[0]
    if flight_distance:  # looks like  ['168.89 km b1-b2', '82.48 km\nb2-b3', '59.94 km\nb3-b1', '26.36 km']
        flight_distance = float(flight_distance.split()[0])

    flight_puntos = infos.get('points', [None])[0]
    if flight_puntos:
        flight_puntos = float(flight_puntos.split()[0])

    flight_duration_re = re.compile(r'(?P<hours>\d+)h(?P<minutes>\d+)mn')
    flight_duration = infos.get('durée (du parcours)', [None])[0]
    if flight_duration:
        if not flight_duration_re.match(flight_duration):
            logger.warning(f'inconsistent flight duration for {ffvl_flight_id} ({flight_duration})')
        else:
            flight_duration = flight_duration_re.match(flight_duration).groupdict()
            flight_duration = int(flight_duration['hours']) * 24 + int(flight_duration['minutes'])

    flight = {
        'flight_id': ffvl_to_flight_id(ffvl_flight_id_actual),
        'pilot': pilot,
        'date': date,
        'wing_name': wing_name,
        'igc': igc_url,
        'fai_type': flight_type,
        'takeoff': flight_takeoff,
        'landing': flight_landing,
        'distance': flight_distance,
        'duration': flight_duration,
        'points': flight_puntos,
    }

    return flight


def save_flights(
        flights: Dict[str, Dict],
        output_filepath: str):
    # update or create flight file
    df = pd.DataFrame.from_dict(flights, orient='index')
    if path.isfile(output_filepath):
        existing_df = pd.read_csv(output_filepath, index_col='flight_id')
        assert existing_df is not None
        df = pd.concat([existing_df, df])
        df.drop_duplicates(keep='last', inplace=True)
        df.sort_index(inplace=True)

    logger.debug(f'saving {len(df)} flights in total.')
    df.to_csv(output_filepath, index_label='flight_id')


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


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
        parser.add_argument('-i', '--flight_id', nargs='+', type=int, default=[20150701, 20330226],
                            help='flight id (eg. 20321973 or 20000001 20000011)')
        parser.add_argument('-o', '--output', required=True,
                            help='input / output database path')
        parser.add_argument('-f', '--force', action='store_true', default=False,
                            help='force download flight [False]')
        parser.add_argument('-c', '--checkpoint', type=int, default=500,
                            help='save file every X flights [500]')

        args = parser.parse_args()
        args.output = path.abspath(args.output)

        logger.setLevel(args.verbose)
        create_logger_output(level=args.verbose)

        logger.debug('config:\n' + '\n'.join(f'\t\t{k}={v}' for k, v in vars(args).items()))

        if len(args.flight_id) == 1:
            args.flight_id += [args.flight_id[0] + 1]

        if not len(args.flight_id) == 2:
            parser.error('flight_id must have 1 or 2 arguments.')
            exit(-1)

        # load existing
        df = None
        if path.isfile(args.output):
            logger.info(f'loading existing data from {args.output}')
            df = pd.read_csv(args.output, index_col='flight_id')
            logger.debug(f'{len(df)} flights are already registered.')

        logger.info(f'parsing ...')
        if not args.force and df is not None:
            # to not parse again empty flight
            # assume max index correspond to resume
            resume_index = max((int(flight_id.split('/')[1]) for flight_id in df.index))
            args.flight_id[0] = max(args.flight_id[0], resume_index + 1)
            logger.info(f'resume to flight id: {args.flight_id[0]}')

        ffvl_flight_id_list = range(*args.flight_id)
        ffvl_flight_id_batch_list = chunks(ffvl_flight_id_list, args.checkpoint)

        flights = {}
        try:
            pool = Pool(10)
            for flight_id_batch in tqdm(ffvl_flight_id_batch_list):
                # print(flight_id_batch) ; exit()
                flights_batch = pool.map(download_flight_info, flight_id_batch)
                # remove unavailable flights
                flights_batch = filter(lambda flight: flight and flight['igc'], flights_batch)
                # move out flight_id as key
                flights_batch = {
                    flight['flight_id']: {k: v for k, v in flight.items() if k != 'flight_id'}
                    for flight in flights_batch
                }
                flights.update(flights_batch)
                if len(flights) >= args.checkpoint:
                    logger.info(f'saving checkpoint')
                    save_flights(flights_batch, args.output)
                    flights = {}

        except KeyboardInterrupt:
            logger.info(f'user interruption.')

        finally:
            save_flights(flights_batch, args.output)

    except Exception as e:
        logger.critical(e)
        if args.verbose <= logging.DEBUG:
            raise


if __name__ == '__main__':
    main()
