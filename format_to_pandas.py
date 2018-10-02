#!/usr/bin/env python
import json
import pandas as pd
import fnmatch
import os
import bz2
import pickle
import argparse
import gc
from pprint import pprint

# read files in list and convert to pandas dataframes
def load_files(files):
    dfs = {}
    for file in files:
        # check file format and read appropriately
        if file.endswith('json'):
            f = open(file, 'rb')
        else:
            f = bz2.BZ2File(file, 'rb')

        jsons = json.load(f)
        f.close()

        # iterate through packets in file
        for pkt in jsons:
            # create a new dataframe with packet timestamp and values
            df = pd.DataFrame.from_dict(pkt["values"])
            df = df.rename( columns={0:"ds", 1:"y"})
            df["ds"] = pd.to_datetime(df["ds"], unit='s')
            df = df.sort_values(by=["ds"])
            df.y = pd.to_numeric(df['y'], errors='coerce')
            df = df.dropna()
            md = str(pkt["metric"])
            # append generated dataframe and metadata to collection
            try:
                dfs[md] = dfs[md].append(df, ignore_index=True)
            except:
                dfs[md] = df
    return dfs

# take a list of dataframes and their metadata and collapse to a
# collection of unique time series (based on unique metadata)
def collapse_to_unique(dfs_master, dfs_new):
    # iterate through metadata
    dfs_remaining = {}
    for md in dfs_new.keys():
        try:
            # find metadata in our master list
            # if this throws an error, simply add it to the list
            dfs_master[md] = dfs_master[md].append(dfs_new[md], ignore_index=True)
        except:
            dfs_remaining[md] = dfs_new[md]
    return dfs_master, dfs_remaining

# create pickle file containing data
def save_checkpoint(pds, file):
    if file[-4:] != ".pkl":
        file = file + ".pkl"
    f = open(file, "wb")
    pickle.dump(pds, f)
    f.close()
    return file

# load pickle file containing data
def load_checkpoint(file):
    f = open(file, "rb")
    pds = pickle.load(f)
    f.close()
    return pds

# load all files and convert to a list of pandas dataframes
def convert_to_pandas(files, batch_size):
    checkpoints = []
    # # separate files into batches
    batches = [files[batch_size*i:batch_size*(i+1)] for i in range(int(len(files)/batch_size) + 1)]
    print("Batches: ", len(batches))
    i = 0
    for batch in batches:
        print("Load batch %i" % i, end="\r")
        i += 1
        # get new portion of dataframes and add to master set
        pds_new = load_files(batch)
        cp = save_checkpoint(pds_new, "raw_" + str(i))
        checkpoints.append(cp)
        gc.collect()
    print("Loaded %i batches" % i)

    pds = []
    # iterate checkpoint by checkpoint and add data to unique collection
    # of time series
    collapsed_fs = []
    i = 0
    for cp in checkpoints:
        i += 1
        print("Processing batch %i" % i, end="\r")
        pds_new = load_checkpoint(cp)
        # load data in batches and combine dataframes
        for f in collapsed_fs:
            pds = load_checkpoint(f)
            pds, pds_new = collapse_to_unique(pds, pds_new)
            save_checkpoint(pds, f)
            gc.collect()
        if len(pds_new) > 0:
            f_new = save_checkpoint(pds_new, "collapsed_" + str(i)) 
            # print("Generated ", f_new)
            collapsed_fs.append(f_new)   
        gc.collect()
    print("Processed %i batches" % i)
    return pds

# get main input arguments and return formatted data
def read_input(data_folder, metric, batch_size):
    # metric-specific data folder
    folder = os.path.join(data_folder, metric)

    # get all files in folder
    files = []
    for root, d_names, f_names in os.walk(folder):
        for f in f_names:
            if f.endswith('bz2') or f.endswith('json'):
                files.append(os.path.join(root, f))
    files.sort()
    print("Processing %s files" % len(files))

    pd_frames = convert_to_pandas(files, batch_size)

    return pd_frames

# remove all temp pickle files generated during this program
# TODO: use tempfiles for temporary files
def combine_checkpoints(master_file):
    df = {}
    files = os.listdir()
    for file in files:
        if fnmatch.fnmatch(file, "collapsed_*.pkl"):
            try:
                f = open(file, "rb")
                dfs = pickle.load(f)
                f.close()
                df.update(dfs)
            except:
                continue
            os.system("rm " + file)
        elif fnmatch.fnmatch(file, "raw_*.pkl"):
            os.system("rm " + file)
    f = open(master_file + ".pkl", "wb")
    pickle.dump(df, f)
    f.close()

def main():
    print("Formatting Data")
    pd_frames = read_input(args.input, args.metric, args.batch_size)
    print("Conversion successful")

    os.makedirs(args.output)
    master_file = os.path.join(args.output, args.metric)

    combine_checkpoints(master_file)

    print("Saved data:", master_file)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="format time series data into an array of pandas dataframes. input folder architecture: input folder must contain a folder with the metric name. Inside the metric folder will be sum/, count/, quant/, or bucket/ according to the metric_type. ex: data/metric_name/files. data/ is input directory")

    parser.add_argument("--metric", type=str, help='metric name', required=True)

    parser.add_argument("-i", "--input", default='', help='input directory')

    parser.add_argument("-o", "--output", default='', help='output directory')

    parser.add_argument("--batch_size", default=1, type=int, help="number of data files to process at once. use this flag if handling big dataset (recommended: 20)")


    args = parser.parse_args()

    main()