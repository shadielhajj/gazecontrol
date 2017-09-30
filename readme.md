# Gaze Control

A real-time control application for the [Tobii Pro Glasses 2](https://www.tobiipro.com/product-listing/tobii-pro-glasses-2/).

## Motivation

Helping a disabled sailor control his boat.

This part of the system detects then the sailor is gazing at an [ArUco](https://www.uco.es/investiga/grupos/ava/node/26) fiducial using the Tobbii Pro Glasses and send the fiducial's Id via serial port. This can be used to drive any device, including in our case a servo-controlled sailbot.

## Project status

Functional Beta.

## Usage

```
python gazecontrol [COM_PORT]
```

If COM_PORT is omitted, the fiducial ID is just displayed on the monitor.
The GUI controls allow to add on offset to the detected gaze position and alter the detection threshold.
Press 'c' to calibrate.
Press 'q' to quit.

More configuration parameters can be modified in config.py

## Prerequisites

* [Python 2.7](https://www.python.org/download/releases/2.7/)
* [OpenCV 3](http://opencv.org/) including the [ArUco contrib module](https://github.com/opencv/opencv_contrib/tree/master/modules/aruco)
* [Pyserial](https://pythonhosted.org/pyserial/) (optional)

If Pyserial is not found, serial port output is disabled.

The system has been tested on Ubuntu Linux, Windows 10, Mac OS Sierra.

On Mac OS, it is advised to install a third-party Python distribution, since the Apple supplied one is know to cause problems related to [interference between Python pip and Apple SIP](https://apple.stackexchange.com/questions/209572/how-to-use-pip-after-the-os-x-el-capitan-upgrade)

Windows does not support Python multiprocessing shared memory out of the box, so the system will fall back to Python multi-threading, which is slightly less efficient than Python multiprocessing.

### Installing via pip

```
pip install pyserial
pip install opencv-contrib-python
```

### Compiling OpenCV with support for FFMPEG, Python and ArUco

On some platforms (eg. Ubuntu Linux), opencv-contrib-python is compiled without FFMPEG support, in this case do not install OpenCV contrib via pip. Compile OpenCV from source like so:

```
sudo apt-get install build-essential libgtk2.0-dev libjpeg-dev libtiff5-dev libjasper-dev libopenexr-dev cmake python-dev python-numpy python-tk libtbb-dev libeigen3-dev yasm libfaac-dev libopencore-amrnb-dev libopencore-amrwb-dev libtheora-dev libvorbis-dev libxvidcore-dev libx264-dev libqt4-dev libqt4-opengl-dev sphinx-common texlive-latex-extra libv4l-dev libdc1394-22-dev libavcodec-dev libavformat-dev libswscale-dev default-jdk ant libvtk5-qt4-dev

wget https://github.com/opencv/opencv/archive/3.3.0.tar.gz
tar -xvzf 3.3.0.tar.gz
wget https://github.com/opencv/opencv_contrib/archive/3.3.0.zip
unzip 3.3.0.zip

cd opencv-3.3.0
mkdir build
cd build
cmake -D WITH_TBB=ON -D BUILD_NEW_PYTHON_SUPPORT=ON -D WITH_V4L=ON -D INSTALL_C_EXAMPLES=ON -D INSTALL_PYTHON_EXAMPLES=ON -D BUILD_EXAMPLES=ON -D WITH_QT=ON -D WITH_FFMPEG=ON -D WITH_OPENGL=ON -D WITH_VTK=ON .. -D CMAKE_BUILD_TYPE=RELEASE -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib-3.3.0/modules ..
make
sudo make install

```

## Authors

* [Shadi El Hajj](https://github.com/shadielhajj) (main author)

Big Thanks to Shea Ako for sharing his expertise with the Tobii Pro API, to [Ryan White](https://github.com/robot-army) for his support and insight and to Ruby Steel for trusting me with this project.

## License

Apache 2.0 - http://www.apache.org/licenses/LICENSE-2.0
