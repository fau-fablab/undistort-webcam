FROM ubuntu:24.04
RUN apt-get -qy update && apt-get -qy install --no-install-recommends python3-opencv python3-requests python3-matplotlib python3-pytest tini
VOLUME /undistort/persistent
ADD . /undistort
EXPOSE 8080
CMD tini -- python3 /undistort/undistort/undistort.py --calibration-dir /undistort/persistent
