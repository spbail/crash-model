
# coding: utf-8
# Generate canonical dataset for hackathon
# Developed by: bpben
import json
import pandas as pd
from data.util import read_geojson
import os
import argparse
import warnings
import data.config


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__))))

MAP_FP = os.path.join(BASE_DIR, 'data/processed/maps')
DATA_FP = os.path.join(BASE_DIR, 'data/processed')


def read_records(fp, id_col):
    """
    Read point data, output segments with crash counts
    Args:
        fp - file, probably a crash_joined.json file
        id_col - column that corresponds to segment id, probably near_id
    Returns:
        Pandas dataframe with the segment/crash info
    """

    with open(fp, 'r') as f:
        data = json.load(f)

    df = pd.DataFrame(data)

    print("total number of records in {}:{}".format(fp, len(df)))
    
    df_g = df.groupby([id_col]).size()
    df_g = df_g.to_frame()
    cols = ['crash']
    # Get counts for all the modes
    for mode, mode_df in df.groupby('mode'):

        df_g = pd.concat(
            [df_g, mode_df.groupby('near_id').size().astype(int)],
            axis=1,
        )
        cols.append(mode)

    df_g.columns = cols
    df_g.index = df_g.index.set_names(['near_id'])

    df_g.reset_index(inplace=True)

    df_g[cols] = df_g[cols].fillna(value=0).astype(int)

    return(df_g)


def road_make(feats, fp):
    """ Makes road feature df, intersections + non-intersections
    Args:
        feats - list of features to be included
        fp - geojson file for intersections and non intersections
    Returns:
        dataframe consisting of features given (if they exist)
    """

    # Read in segments data (geojson)
    print("reading ", fp)
    segments = read_geojson(fp)
    df = pd.DataFrame([x.properties for x in segments])

    df.set_index('id', inplace=True)

    # Check for missing features
    missing_feats = [x for x in feats if x not in df.columns]
    feats = [x for x in feats if x in df.columns]
    if missing_feats:
        warnings.warn(
            str(len(missing_feats))
            + " feature(s) missing, skipping (" +
            ', '.join(missing_feats)
            + ")")

    return df[feats]


def aggregate_roads(feats, datadir):

    # read/aggregate crashes
    crash = read_records(os.path.join(datadir, 'crash_joined.json'),
                         'near_id')
    # Make near_id string (for matching to segments)
    crash['near_id'] = crash['near_id'].astype('str')

    # combined road feature dataset parameters
    fp = os.path.join(datadir, 'maps', 'inter_and_non_int.geojson')
    # create combined road feature dataset
    aggregated = road_make(feats, fp)
    print("road features being included: ", ', '.join(feats))

    aggregated = aggregated.fillna(0)

    # All features as int
    aggregated = aggregated.apply(lambda x: x.astype('int'))

    return aggregated, crash


def combine_crash_with_segments(crash, aggregated):

    # join segment features to crash
    crash_roads = pd.merge(
        aggregated, crash,
        left_index=True,
        right_on='near_id', right_index=False,
        how='outer'
    )
    crash_roads = crash_roads.rename(
        columns={'near_id': 'segment_id'})
    return crash_roads


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--datadir", type=str,
                        help="Can give alternate data directory")
    parser.add_argument("-c", "--config", type=str,
                        help="Config file", required=True)

    args = parser.parse_args()

    config = data.config.Configuration(args.config)

    # Can override the hardcoded data directory
    if args.datadir:
        DATA_FP = os.path.join(args.datadir, 'processed')
        MAP_FP = os.path.join(DATA_FP, 'maps')

    feats = config.features
    print("Data directory: " + DATA_FP)

    aggregated, crash = aggregate_roads(
        feats,
        DATA_FP
    )

    crash_roads = combine_crash_with_segments(
        crash, aggregated)

    # output canon dataset
    print("exporting canonical dataset to ", DATA_FP)

    crash_roads.set_index('segment_id').to_csv(
        os.path.join(DATA_FP, 'vz_predict_dataset.csv.gz'),
        compression='gzip')

