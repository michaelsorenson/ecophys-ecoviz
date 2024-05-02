import os
import sys
import pytz
import numpy as np
import mne
import datetime
import pandas as pd
from argparse import ArgumentParser
import time
import warnings
warnings.simplefilter('ignore')

# custom functions
import feature_generation_utils as seal_fe # seal feature extraction

# generate EEG features
def generate_eeg_extended_features(eeg_data, recording_start_datetime, sfreq, output_dir, file_name, epoch_sizes, welch_sizes):
    ref_time = time.time()
    eeg_output_dir = output_dir + '/EEG'
    os.makedirs(eeg_output_dir, exist_ok=True)
    eeg_features_all = []
    print('Generating EEG features')
    counter = 0
    num_iterations = len(epoch_sizes) * len(welch_sizes)
    print('Expecting to take ~', num_iterations * 3, ' minutes', sep='')
    for epoch_size in epoch_sizes:
        for welch_size in welch_sizes:
            ref_time = time.time()
            step_size = epoch_size // 8 if epoch_size >= 8 else 1
            eeg_features = seal_fe.generate_features_sequential(eeg_data, recording_start_datetime, data_type='EEG', sfreq=sfreq, window_length_sec=3600, buffer_length_sec=300,
                                                                epoch_size_sec=epoch_size, welch_window_sec=welch_size, step_size=step_size, config={})
            eeg_features = eeg_features.rename(lambda x: f'EPOCH_{epoch_size}_WELCH_{welch_size}_EEG_{x}', axis=1)
            eeg_features_all.append(eeg_features)
            counter += 1
            print('Time Taken:', time.time() - ref_time)
            ref_time = time.time()
            print('EEG Progress: ', round(((counter / num_iterations) * 100), 2), '%\n', sep='')
    eeg_features_df = pd.concat(eeg_features_all, axis=1)
    print('Writing EEG features to file...')
    eeg_features_df.to_csv(f'{eeg_output_dir}/{file_name}_EEG.csv')
    print()

# generate ECG features
def generate_ecg_extended_features(ecg_data, recording_start_datetime, sfreq, output_dir, file_name, epoch_sizes, welch_sizes, search_radius=200, filter_threshold=200):
    hr_output_dir = output_dir + '/ECG'
    os.makedirs(hr_output_dir, exist_ok=True)
    hr_features_all = []
    print('Calculating Heart Rate from ECG')
    heart_rate = seal_fe.get_heart_rate(ecg_data, fs=500, search_radius=search_radius, filter_threshold=filter_threshold)
    print('Generating Heart Rate features')
    counter = 0
    num_iterations = len(epoch_sizes) * len(welch_sizes)
    print('Expecting to take ~', num_iterations * 1.5, ' minutes', sep='')
    for epoch_size in epoch_sizes:
        for welch_size in welch_sizes:
            ref_time = time.time()
            step_size = epoch_size // 8 if epoch_size >= 8 else 1
            hr_features = seal_fe.generate_features_sequential(heart_rate.values, recording_start_datetime, data_type='HR', sfreq=sfreq, window_length_sec=3600, buffer_length_sec=300,
                                                               epoch_size_sec=epoch_size, welch_window_sec=welch_size, step_size=step_size, config={})
            hr_features = hr_features.rename(lambda x: f'EPOCH_{epoch_size}_WELCH_{welch_size}_HR_{x}', axis=1)
            hr_features_all.append(hr_features)
            counter += 1
            print('Time Taken:', time.time() - ref_time)
            ref_time = time.time()
            print('Heart Rate Progress: ', round(((counter / num_iterations) * 100), 2), '%\n', sep='')
    hr_features_df = pd.concat(hr_features_all, axis=1)
    print('Writing EEG features to file...')
    hr_features_df.to_csv(f'{hr_output_dir}/{file_name}_ECG.csv')
    print()

if __name__ == '__main__':
    start_time = time.time()
    WED_INPUT_FILE = 'data/raw/01_edf_data/test12_Wednesday_05_ALL_PROCESSED.edf'
    WED_OUTPUT_FOLDER = 'data/interim/feature_discovery/'
    WED_OUTPUT_FILENAME = 'Wednesday_feature_discovery'
    WED_LABELS_FILE = 'data/raw/02_hypnogram_data/test12_Wednesday_06_Hypnogram_JKB_1Hz.csv'
    parser = ArgumentParser()
    parser.add_argument("-i", "--input", dest="input", type=str, help="input .edf filepath",
                        default=WED_INPUT_FILE)
    parser.add_argument("-d", "--output-dir", dest="output_dir", type=str, help="output folder filepath (will create an ECG and EEG subfolder)",
                        default=WED_OUTPUT_FOLDER)
    parser.add_argument("-o", "--output-file-name", dest="file_name", type=str, help="name of output file",
                        default=WED_OUTPUT_FILENAME)
    parser.add_argument("-e", "--eeg", dest="eeg", type=str, help="channel name for eeg",
                        default='EEG_ICA5')
    parser.add_argument("-c", "--ecg", dest="ecg", type=str, help="channel name for ecg",
                        default='ECG_Raw_Ch1')
    parser.add_argument("-l", "--labels", dest="labels", type=str, default=None,
                        help="optional .csv filepath with 1Hz labels")
    
    # Get args from command line
    args = parser.parse_args()

    os.makedirs(WED_OUTPUT_FOLDER, exist_ok=True)
    raw = mne.io.read_raw_edf(args.input, include=[args.eeg, args.ecg], preload=False, verbose=False)
    edf_start_time = raw.info['meas_date']

    # Define the PST timezone
    pst_timezone = pytz.timezone('America/Los_Angeles')
    # Convert to datetime object in PST
    if isinstance(edf_start_time, datetime.datetime):
        # If it's already a datetime object, just replace the timezone
        recording_start_datetime = edf_start_time.replace(tzinfo=None).astimezone(pst_timezone)
        # for some reason using .replace(tzinfo=...) does weird shit - offsets based of LMT instead of UTC and gets confusing
        # recording_start_datetime = edf_start_time.replace(tzinfo=pst_timezone)
    elif isinstance(edf_start_time, (int, float)):
        # Convert timestamp to datetime in PST
        recording_start_datetime = pst_timezone.localize(datetime.datetime.fromtimestamp(edf_start_time))
    
    # Generate EEG features
    eeg_raw = mne.io.read_raw_edf(args.input, include=[args.eeg], preload=False, verbose=False)
    sfreq = eeg_raw.info['sfreq']
    generate_eeg_extended_features(eeg_raw.get_data(args.eeg)[0],
                                   recording_start_datetime,
                                   sfreq,
                                   args.output_dir,
                                   args.file_name,
                                   epoch_sizes=[16, 32, 64, 128, 256],
                                   welch_sizes=[1, 2, 4, 8, 16])
    del(eeg_raw)

    # Generate ECG features (heart rate)
    ecg_raw = mne.io.read_raw_edf(args.input, include=[args.ecg], preload=True, verbose=False)
    sfreq = ecg_raw.info['sfreq']
    generate_ecg_extended_features(ecg_raw.get_data(args.ecg)[0],
                                   recording_start_datetime,
                                   sfreq,
                                   args.output_dir,
                                   args.file_name,
                                   epoch_sizes=[128, 256, 512],
                                   welch_sizes=[64, 128, 256, 512])
    del(ecg_raw)
    end_time = time.time()
    print('Done. Total time elapsed:', (end_time - start_time) / 60, 'minutes')