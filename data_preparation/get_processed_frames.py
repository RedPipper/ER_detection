"""
Save all frames of the raw lung ultrasound clips (.mp4) as separate images (.png).
Images are processed such that the ultrasound information is centered, padded to the correct aspect ratio,
and resized to the desired shape. Additionally, embedded text on the side is removed.
"""

import os
import sys

from skimage.io import imread

sys.path.append('..')
sys.path.append(os.path.join(__file__, '..', '..'))

import pickle
import pandas as pd
import concurrent.futures
from glob import glob
from tqdm import tqdm
from natsort import natsorted
from skimage.util import img_as_ubyte
from skimage.color import rgb2gray
from imageio import get_reader, imwrite

from utils.config import raw_folder, images_folder, info_folder
from utils.conversion_utils import crop_and_resize
import numpy as np

def process_frame(frame, points, output_dir, output_type, output_shape, apply_mask):
    frame_data = imread(frame)
    frame_data = img_as_ubyte(rgb2gray(frame_data))
    processed_frame, processing = crop_and_resize(frame_data, points, output_shape=output_shape, apply_mask=apply_mask)

    imwrite(os.path.join(output_dir, os.path.basename(frame)), processed_frame)

    return processing

def process_clip(
        clip: str,
        points: list,
        output_dir: str,
        output_type: str,
        output_shape: tuple,
        apply_mask: bool = True
) -> tuple:
    """
    Load a clip and save all frames after processing as separate images of datatype out_type in the out_dir directory.

    Args:
        clip:  path to clip.
        points:  annotated corner points in the following order: [top left, bottom left, top right, bottom right]
        output_dir:  path to ouptput directory where all individual frames will be stored.
        output_type:  datatype that is used to store the frames.
        output_shape:  shape of output image.
        apply_mask:  indicates if the boolean mask should be applied to remove all embedded information from the sides.

    Returns:
        processing:  processing information about cropping, padding, and resizing.
    """
    # read the clip
    reader = get_reader(clip)

    # loop over frames
    for i, frame in enumerate(reader):
        # create greyscale frame
        frame = img_as_ubyte(rgb2gray(frame))
        # crop the frame, add padding to get the desired aspect ratio, then resize the image
        processed_frame, processing = crop_and_resize(frame, points, output_shape=output_shape, apply_mask=apply_mask)
        # save the processed image and add the processing settings to the list
        imwrite(os.path.join(output_dir, os.path.basename(clip).replace('.mp4', f'_{str(i).zfill(3)}{output_type}')),
                processed_frame)

    return processing


if __name__ == '__main__':

    # define directories, paths, and filenames
    input_folder = os.path.join(raw_folder)
    output_folder = os.path.join(images_folder, 'processed_frames')
    corner_points_path = os.path.join(info_folder, 'corner_points_dictionary.pkl')
    processing_dict_name = 'processing_dictionary.pkl'

    # define output shape
    output_shape = (287,200)

    # define output data type for images
    output_datatype = '.png'

    # --------------------------------------------------------------------------------

    # create output directory if it does not exist yet
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # read pickle file with corner point dictionary
    points_dict = pd.read_pickle(corner_points_path)

    # get all case names from the input folder
    cases = sorted([item for item in os.listdir(input_folder) if item.lower().startswith('case')])

    # create dictionary to collect processing information of each clip per case
    processing_cases = {}

    for case in tqdm(cases):
        # define output folder for a single case and create it if it does not exist yet
        case_output = os.path.join(output_folder, case)
        if not os.path.exists(case_output):
            os.makedirs(case_output)

        # create dictionary to collect processing information for each clip
        processing_clips = {}

        # define the path to directory with all clips
        frames = os.listdir(os.path.join(input_folder, case))
        # get the corner points coordinates for each clip
        points = [points_dict[case.replace("case_","").replace("-","_")][frame + ".npy"] for frame in frames]

        # set some inputs of the convert_clip function
        process = lambda frame, points: process_frame(os.path.join(input_folder, case, frame), points, case_output, output_datatype, output_shape, apply_mask=False)

        # handle clips using multithreading for speedup
        for i, frame in enumerate(frames):
            result = process(frame, points[i])

        processing_cases[case] = processing_clips

    # save processing information dictionary variable
    file = open(os.path.join(info_folder, processing_dict_name), 'wb')
    pickle.dump(processing_cases, file)
    file.close()