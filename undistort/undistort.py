#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Removes "fisheye" distortion from a camera image.
See ../README.md for details.

(C) Max Gaukler 2025
"""


import requests
import numpy as np
import cv2
import sys
import logging
import glob
import os
import re
from lib.camera_calibration import CameraCalibration
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
import argparse
import datetime


SCRIPT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))

## CONFIGURATION:
# Note: Can be overwritten by commandline arguments!
CONFIG = {
    # Input image - File or HTTP(S) URL. Data must be in JPG format.
    # SECURITY: Note that the URL can be shown in the web interface and on the console.
    "image-url": SCRIPT_DIRECTORY + "/testdata/img1.jpg",
    # "https://raw.githubusercontent.com/opencv/opencv/refs/heads/4.x/modules/core/misc/objc/test/resources/chessboard.jpg",
    # "http://lasercam.lab.fablab.uni-erlangen.de:8080/?action=snapshot",
    # "/undistort/data/test-input/2025-09-16-144244_1.jpg"
    # "/undistort/data/dummy-hires.jpg"
    # "https://raw.githubusercontent.com/opencv/opencv/refs/heads/4.x/modules/core/misc/objc/test/resources/chessboard.jpg"
    #
    # Folder to store the images taken during calibration
    "calibration-dir": SCRIPT_DIRECTORY + "/data/calibration/",
    #
    # 
    "output-image": SCRIPT_DIRECTORY + "/data/output/output.png",
    "port": 8080
    }

def calibration_file_path():
    # File where calibration matrix is saved
    return CONFIG["calibration-dir"] + "/calib.npz"


def get_image(url_or_path: str = None):
    """
    Fetch image as OpenCV object.
    
    Parameter can be URL (starting with http[s]://) or file path (e.g. /tmp/foo)
    """
    if url_or_path is None:
        url_or_path = CONFIG["image-url"]
    logging.info(f"Getting image from {url_or_path}")
    if re.match("^https?://", url_or_path):
        # URL
        try:
            r = requests.get(url_or_path)
        except Exception as e:
            raise Exception("undistort.py: failed to download image from URL " + CONFIG["image-url"])
        data = np.asarray(bytearray(r.content), dtype="uint8")
    else:
        # local file
        with open(url_or_path, "rb") as f:
            data = np.frombuffer(f.read(), dtype="uint8")
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

def main_process_image():
    """
    Load calibration, fetch image, undistort, save to output file
    """
    if not os.path.isfile(calibration_file_path()):
        raise Exception("Calibration file not found, please calibrate first")
    calibration = CameraCalibration()
    calibration.load_calibration(calibration_file_path())
    distorted = get_image()
    logging.info("Processing image")
    undistorted = calibration.undistort_image(distorted, crop=False)
    logging.info("Saving output")
    os.makedirs(os.path.dirname(CONFIG["output-image"]), exist_ok=True)
    cv2.imwrite(CONFIG["output-image"], undistorted)
    assert os.path.isfile(CONFIG["output-image"])
    logging.info("Done processing")

def take_calib_image():
    """
    Take calibration photo and save to folder
    """
    dest = f"{CONFIG["calibration-dir"]}/undistort-calib-{num_calib_images() + 1}.jpg"
    cv2.imwrite(dest, get_image())
    
def calib_images():
    """
    Get all calibration photo paths
    """
    return glob.glob(CONFIG["calibration-dir"] + "/undistort-calib-*.jpg")

def num_calib_images():
    """
    Get number of available calibration photos
    """
    return len(calib_images())

def clear_calib_data():
    """
    Remove calibration images and data
    """
    for f in calib_images():
        os.unlink(f)
    if os.path.isfile(calibration_file_path()):
        # Move old calib data to backup file
        os.rename(calibration_file_path(), calibration_file_path() + ".backup." + datetime.datetime.now().isoformat())

def calibrate_from_files():
    """
    Non-Interactively perform calibration and save to calibration file
    
    Input is read from CONFIG["calibration-dir"] / undistort-calib-*.jpg
    """
    logging.info("Loading calibration images from " + CONFIG["calibration-dir"])
    files = calib_images()
    images = [get_image(f) for f in files]
    if not images:
        raise Exception("No images found for calibration")
    logging.info("Computing calibration... This can take a few minutes.")
    calibration = CameraCalibration()
    calibration.calibrate_camera(images)
    calibration.save_calibration(calibration_file_path())
    logging.info("Done. Calibration saved.")

class UndistortHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    Web request handler
    """
    def do_GET(self):
        logging.info("Received HTTP request")
        try:
            [outputdata, contenttype] = self.process_request()
            if isinstance(outputdata, str):
                outputdata = outputdata.encode("utf8")
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            error = str(e) + "\n\n"
            error += "undistort.py failed:\n"
            error += "\n".join(traceback.format_exception(e))
            self.wfile.write(bytes(error, "utf8"))
            logging.exception(e)
            logging.info("Sent error response")
            return
        self.send_response(200)
        self.send_header("Cache-control", "no-store")
        self.send_header("Content-type", contenttype)
        self.end_headers()
        self.wfile.write(outputdata)
        logging.info("Successfully answered HTTP request")

    def process_request(self):
        outputdata = ""
        contenttype = "text/plain"
        ######
        # Raw image
        if self.path =="/raw":
            contenttype = "image/png"
            img = get_image()
            img_enc = cv2.imencode('.png', img)[1]
            outputdata = np.array(img_enc).tobytes()
        ######
        # Processed image
        elif self.path == "/image":
            main_process_image()
            contenttype = "image/png"
            with open(CONFIG["output-image"], 'rb') as f:
                outputdata = f.read()
        ######
        # Main page
        elif self.path == "/":
            outputdata = """

Undistort.py removes "fisheye" distortion from a webcam image.<p>

<a href="https://github.com/fau-fablab/undistort-webcam">Source on GitHub</a><p>

<ul>
<li><a href="/image">Get processed output image</a></li>
<li><a href="/raw">Get raw input image</a></li>
<li><a href="/calib-pattern">Calibration Step 0: Calibration pattern for printing. Print out this pattern in any size and glue it to a rigid and level surface (e.g. wood or thick cardboard).</a></li>
<li><a href="/calib-clear-images">Calibration: Step 1. Clear old calibration data and images (CAUTION: Old calibration data is deleted. Can not be undone.)</a></li>
<li>Calibration: Step 2. Take 10-20 images with the calibration pattern. <a href="/calib-take-image">Take calibration image.</a> Hold the calibration pattern in front of the camera in different positions to cover most parts of the camera. Keep it roughly perpendicular to the camera (+- 30 degrees), and do not exceed the camera boundaries). </li>
<li><a href="/calib-finish">Calibration: Step 3. Process calibration images (will take a few minutes)</a></li>
</ul>
            """
            contenttype = "text/html"
            
       
        ######
        # Calibration pattern (checkerboard)
        elif self.path == "/calib-pattern":
            with open(SCRIPT_DIRECTORY + "/chessboard.jpg", 'rb') as f:
                outputdata = f.read()
            contenttype = "image/jpeg"
        
        ######
        # Start calibration 
        elif self.path == "/calib-clear-images":
            clear_calib_data()
            outputdata = 'Removed old calibration data and images. <a href="/">Go back to main</a>'
            contenttype = "text/html"
        
        
        ######
        # Take calibration photo
        elif self.path == "/calib-take-image":
            take_calib_image()
            outputdata = f'Image was taken. Now {num_calib_images()} calibration images are saved. <a href="/calib-take-image">Take another image</a> or <a href="/calib-finish">Finish the calibration (will take a few minutes)</a> if you have enough images or <a href="/">Back to main</a>'
            contenttype = "text/html"
            
        
        ######
        # End calibration
        elif self.path == "/calib-finish":
            calibrate_from_files()
            outputdata = 'Successfully calibrated. <a href="/">Back to main</a>'
            contenttype = "text/html"
        
        
        ######
        # Fallback
        else:
            raise Exception("unknown request path")
        
        ######
        # Add HTML head/foot if necessary
        if contenttype == "text/html" and not outputdata.startswith("<html>"):
            outputdata = """
<html>
<body>
<h1>undistort.py</h1>
""" \
     + outputdata + \
    """
</body>
</html>
"""
        return [outputdata, contenttype]
    
def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s')
    parser = argparse.ArgumentParser(
                    prog='undistort.py',
                    description='Undistort webcam. See READE.md.',
                    epilog='(C) Max Gaukler 2025')
    parser.add_argument('--image-url', help="HTTP(s) URL from which the image is received. Local file paths also work (/some/directory/image.jpg). SECURITY: Note that the URL can be shown in the web interface and on the console.")
    parser.add_argument('--calibration-dir', help="Directory to store calibration data (default: temporary directory -- only useful for testing)")
    parser.add_argument('--output-image', help="Temporary PNG file to store output image (default: temporary file).")
    parser.add_argument("--port", type=int, help="Port for webserver")
    args = parser.parse_args()
    for k in CONFIG.keys():
        k_key_name = k.replace("-", "_")
        assert k_key_name in args, f"CONFIG key {k} does not have a corresponding commandline argument"
        if getattr(args, k_key_name):
            CONFIG[k] = getattr(args, k_key_name)
    
    server_address = ('', CONFIG["port"])
    httpd = HTTPServer(server_address, UndistortHTTPRequestHandler)
    logging.info(f"Webserver listening on http://localhost:{CONFIG["port"]}/")
    httpd.serve_forever()

if __name__ == "__main__":
    main()
        
