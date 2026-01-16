# Undistort: Camera distortion removal 📸🫠➡️🙂 

Removes "fisheye" distortion from a camera image.

Input image is taken from a JPEG as local file or via HTTP(S).

Output image is served via a simple webserver as PNG.

Calibration can be triggered via the web interface.


# Installation

You need `docker` and `docker-compose`.


# Development Unittests
`./run_tests_in_docker.sh` runs a test suite using `docker-compose`.

# Configuration

Adjust the image URL/path in `undistort/undistort.py` (or on the commandline argument --image-url) according to your needs. Otherwise an example image is used. With the example image you can try the calibration but the result will look a bit odd.

# Running

Using `./run_docker.sh`

# Calibration

Open the web interface and follow the instructions for calibration:

Print out the chessboard calibration pattern [chessboard.jpg](./chessboard.jpg) in any size and glue it to a rigid and plane surface (e.g. wood or thick cardboard). Hold it in front of the camera at different "tilt" angles and positions (but still keep it roughly perpendicular to the camera, +- 30°, and do not exceed the camera boundaries). Follow the web instructions to take 10-20 images, then finish the calibration.

# Normal use after calibration
`./undistort/undistort.py process`

The processed camera image is saved to output.jpg.

# Performance

Runtime for processing an image with six megapixels is about 300 ms.

# Known issues

The webserver is not parallelized. Only one request is processed at a time.
