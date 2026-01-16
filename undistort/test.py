#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Test for undistort.py

(C) Max Gaukler 2025
"""


import shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
import numpy as np
import requests
import tempfile
import os
import threading
import subprocess
import sys
import cv2
import time
import pytest

##################################
# Generic Test Helpers (Logging, Comparison)

def info(text):
    print("TEST: " + text)

def decode_image(img):
    """
    Given an image in almost any datatype, decode to RGB numpy.ndarray.

    Supported types:
        HTTP Response (requests.response) --> decoded as PNG or JPEG
        Numpy array of already decoded image --> pass-through
        Local file path --> decoded as PNG or JPEG
    """
    if isinstance(img, np.ndarray):
        return img
    elif isinstance(img, str):
        with open(img, "rb") as f:
            data = np.frombuffer(f.read(), dtype="uint8")
    elif isinstance(img, requests.Response):
        assert img.headers["Content-Type"] in ["image/jpeg", "image/png"]
        data = np.asarray(bytearray(img.content), dtype="uint8")
    else:
        raise TypeError(f"Unsupported argument type {type(img)}, must be numpy array or path as string or HTTP response as requests.Response")
    assert len(data) > 5
    result = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return result

def assert_equal_to_image(actual, expected):
    assert_approximately_equal_to_image(actual, expected, 0)

def assert_approximately_equal_to_image(actual, expected, threshold) -> None:
    actual = decode_image(actual)
    expected = decode_image(expected)
    # Normalized difference
    diff_relative = np.average(np.abs(actual - expected)) / 255
    image_dir = os.path.dirname(__file__) + "/test-output/"
    if not os.path.isdir(image_dir):
        os.mkdir(image_dir)
    cv2.imwrite(image_dir + "/actual.png", actual)
    cv2.imwrite(image_dir + "/expected.png", expected)
    info(f"Actual and expected image stored to {image_dir}")
    info(f"Normalized difference (0...1) of actual to expected image is {diff_relative}, threshold {threshold}")
    assert diff_relative <= threshold, f"Images are not equal enough, difference {diff_relative}, please check visually in {image_dir}"

def assert_response_is_text(response) -> None:
    assert response.headers["Content-Type"].startswith("text")
    assert len(response.text.strip()) > 0

##################################
# Dummy data

def example_image_path(number):
    return os.path.dirname(__file__) + f"/testdata/img{number}.jpg"

def example_image(number):
    return decode_image(example_image_path(number))


def example_image_undistorted(number):
    return decode_image(example_image_path(number) + ".output.png")

##################################
# Dummy webserver and glue logic

def serve_example_image(number):
    """
    Serve an example image with a certain ID (1...10)
    """
    global fake_camera_local_path
    shutil.copyfile(example_image_path(number), fake_camera_local_path)

def request_undistort_url(url: str, ignore_error = False) -> requests.Response:
    assert url == "" or url.startswith("/")
    global undistort_url
    response = requests.get(f"{undistort_url}{url}")
    if not ignore_error:
        response.raise_for_status()
    return response

class HTTPFileServer:
    def __init__(self, directory, port=8000):
        def run_server(directory, port):
            os.chdir(directory)
            server_address = ('localhost', port)
            httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
            httpd.serve_forever()
        self.thread = threading.Thread(target = run_server, args=(directory, port), daemon=True)
        self.thread.start()

##################################
# Running undistort.py

class UndistortPyRunner:
    def __init__(self, port, camera_url):
        args = [os.path.dirname(__file__) + "/undistort.py", f"--port={port}", f"--image-url={camera_url}"]
        self.undistort_process = subprocess.Popen(args)
        info(f"Starting undistort.py: {" ".join(args)}")

    def __del__(self):
        info("Killing undistort.py")
        if hasattr(self, "undistort_process"):
            self.undistort_process.kill()

#################################
# Test procedure

def test_roundtrip_image():
    # Selftest of test infrastructure: Roundtrip encode/decode is correct
    url = "https://raw.githubusercontent.com/opencv/opencv/refs/heads/4.x/modules/core/misc/objc/test/resources/chessboard.jpg"
    img = decode_image(requests.get(url))
    img_enc = cv2.imencode('.png', img)[1]
    data = np.array(img_enc).tobytes()
    img_enc_dec = cv2.imdecode(img_enc, cv2.IMREAD_COLOR)
    np.testing.assert_equal(img, img_enc_dec)

def test_main():
    info("=== Initial setup ===")

    info("Setting up temp data directory for camera image")
    info("Start HTTP Server (fake camera) in background: ")
    fake_camera_url = f"http://localhost:8901/image.jpg"
    fake_camera_dir_temp_obj = tempfile.TemporaryDirectory()
    fake_camera_dir = fake_camera_dir_temp_obj.name
    global fake_camera_local_path
    fake_camera_local_path = f"{fake_camera_dir}/image.jpg"

    serve_example_image(1)
    http_server = HTTPFileServer(directory=fake_camera_dir, port=8901)

    info("Set up temp dir for undistort.py")
    temp_undistort_dir_temp_obj = tempfile.TemporaryDirectory()
    temp_undistort_dir = str(temp_undistort_dir_temp_obj)

    info("Start undistort.py webserver")
    undistort_py = UndistortPyRunner(port=8000, camera_url=fake_camera_url)
    global undistort_url
    undistort_url = "http://localhost:8000"
    info("Waiting for server to start up")
    time.sleep(5)

    info("=== Selftest of test infrastructure ===")
    info("Given we set the fake camera server to serve a certain example image")
    serve_example_image(3)
    info("When the fake camera image is requested")
    response = requests.get(fake_camera_url)
    info("Then the correct example image is returned")
    response.raise_for_status()
    assert_equal_to_image(response, example_image(3))

    info("=== Test ===")

    info("When a non existing URL is requested")
    response = request_undistort_url("/non-existing-url", ignore_error=True)
    info("then an error is returned (currentl 500, ideally should be 404")
    assert response.status_code == 500

    info("When / is requested")
    respose = request_undistort_url("/")
    info("then some text is returned")
    assert_response_is_text(response)

    for i in [1, 2]:
        serve_example_image(i)
        info("When /raw is requested")
        response = request_undistort_url("/raw")
        info("then it returns the example image unchanged")
        assert_equal_to_image(response, example_image(i))
    
    info("When we clear the calibration data")
    response = request_undistort_url("/calib-clear-images")
    info("then some success text is returned")
    assert_response_is_text(response)
    
    for i in [1, 2]:
        serve_example_image(i)
        info("Given we are not yet calibrated")
        info("When /image is requested")
        response = request_undistort_url("/image", ignore_error=True)
        info("then an error is returned")
        assert response.status_code == 500

    for i in range(17):
        serve_example_image(i)
        info("When we take calibration photos 1...10")
        response = request_undistort_url("/calib-take-image")
        info("Then this returns OK")
        response.raise_for_status()

    info("When we then run the calibration")
    response = request_undistort_url("/calib-finish")
    info("Then this returns OK")
    response.raise_for_status()
    
    for i in [1, 2]:
        serve_example_image(i)
        info("When we request /image")
        response = request_undistort_url("/image")
        info("then it returns the undistorted image")
        assert_approximately_equal_to_image(response, example_image_undistorted(i), 0.01)

if __name__ == "__main__":
    sys.exit(pytest.main(sys.argv))
