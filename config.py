#   Gaze Control - A real-time control application for Tobii Pro Glasses 2.
#
#   Copyright 2017 Shadi El Hajj
#
#   Licensed under the Apache License, Version 2.0 (the 'License');
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an 'AS IS' BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

# Wifi IP is fixed
VIDEO_STREAM_URI = 'rtsp://192.168.71.50:8554/live/scene'
DATA_STREAM_IP = '192.168.71.50'

# IPv6 Ethernet IP is now working for now
#VIDEO_STREAM_URI = 'rtsp://[fe80::76fe:48ff:fe2c:b7a5]:8554/live/scene'
#DATA_STREAM_IP = 'fe80::76fe:48ff:fe2c:b7a5'

DATA_STREAM_PORT = 49152 # Livestream API port
DWELL_TIME_FRAMES = 30 # Detection time-frame in frames
USE_MULTIPROCESSING = True # Enable multiprocessing on UNIX and multi-threading on Windows
HEADLESS = False # disable GUI

#compute distances
DISTANCES = True

GAZE_OFFSET_X = 0 # gaze X offset
GAZE_OFFSET_Y = 0 # gaze Y offset
GAZE_THRESHOLD = 10 # detection threshold

