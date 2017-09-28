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

GAZE_OFFSET_X = 0 # gaze X offset
GAZE_OFFSET_Y = 0 # gaze Y offset
GAZE_THRESHOLD = 10 # detection threshold

import numpy as np
import cv2
import cv2.aruco as aruco
import json
import socket
import time
import threading
from collections import deque
import itertools
import operator
import video_capture as vc
import logging

serial_available = True
try:
    import serial
except ImportError:
    logging.warning('WARNING: Serial port module not installed')
    serial_available = False



running = True

def nothing(x):
    pass

def mksock(peer):
    ''' Create a socket pair for a peer description '''
    iptype = socket.AF_INET
    if ':' in peer[0]:
        iptype = socket.AF_INET6
    return socket.socket(iptype, socket.SOCK_DGRAM)

class KeepAlive:
    ''' Sends keep-alive signals to a peer via a socket (Livestream API) '''

    def __init__(self, sock, peer, streamtype, timeout=1):
        self.timeout = timeout
        jsonobj = json.dumps({
            'op' : 'start',
            'type' : '.'.join(['live', streamtype, 'unicast']),
            'key' : 'anything'})
        sock.sendto(jsonobj, peer)
        td = threading.Timer(0, self.send_keepalive_msg, [sock, jsonobj, peer])
        td.start()

    def send_keepalive_msg(self, socket, jsonobj, peer):
        while running:
            socket.sendto(jsonobj, peer)
            time.sleep(self.timeout)

class BufferSync():
    ''' Sync Gaze data to Video '''

    et_syncs = [] # Eyetracking Sync items
    et_queue = [] # Eyetracking Data items
    video_pts = 0 # The current video frame pts
    last_video_pts = 0 # video pts corresponding to the last sync packet
    last_data_ts = 0 # ts of the last pts sync packet

    def add_et(self, obj):
        ''' Store sync packets and gaze positions '''
        if 'pts' in obj:
            self.et_syncs.append(obj)
            self.last_video_pts = self.video_pts
        elif 'gp' in obj:
            self.et_queue.append(obj)

    def add_pts(self, pts):
        ''' Store video frame pts '''
        self.video_pts = pts

    def sync(self):
        ''' Find gp packet corresponding to the last video pts and return it '''
        pts = int(self.video_pts * 90) # convert from msec to 90khz
        tsoffset = int(self.video_pts*1000 - self.last_video_pts * 1000) # convert to usec
        if len(self.et_syncs) > 0: # do we have gaze data?
            if (pts < self.et_syncs[-1]['pts']): # is gaze data ahead of video?
                # filter all sync packets pre-dating our video frame
                pastpts = filter(lambda x: x['pts'] <= pts, self.et_syncs)
                # discard used sync packets
                self.et_syncs = filter(lambda x: x['pts'] > pts, self.et_syncs)
                if len(pastpts) > 0:
                    # get the ts of the last sync packet
                    self.last_data_ts = pastpts[-1]['ts']
                # get all gaze positions corresponding to the ts of the sync packet
                # plus the offset. the offset is the diff of the current frame pts
                # and the pts of the frame corresponding to the last sync packet
                pastts = filter(lambda x: x['ts'] <= self.last_data_ts + tsoffset, self.et_queue)
                # discard used gaze positions
                self.et_queue = filter(lambda x: x['ts'] > self.last_data_ts + tsoffset, self.et_queue)
                # return gaze position
                if len(pastts) > 0:
                    return pastts[-1]
                else:
                    #logging.error('ERROR: Gaze position packet not found')
                    return None

            else:
                logging.warning('WARNING: Video is ahead of data stream')
                return None



class EyeTracking():
    ''' Read eye-tracking position from data stream '''

    def __init__(self, buffersync):
        self.buffersync = buffersync

    def start(self, peer):
        # start data Keep-Alive
        self.sock = mksock(peer)
        self.sock.setblocking(0)
        self.keepalive = KeepAlive(self.sock, peer, 'data')

    def read(self):
        while True:
            # get raw data is available
            try:
                data, address = self.sock.recvfrom(1024)
            except socket.error:
                return None
            # convert to JSON and store
            dict = json.loads(data)
            self.buffersync.add_et(dict)
            if 'marker2d' in dict:
                print dict

    def stop(self):
        self.sock.close()

class Video():
    ''' Detect Fiducial and check if gaze position falls within ROI '''

    def __init__(self, peer):
        self.output_filters = OutputFilters()
        self.lastid = None
        self.lastpts = 0
        # start video Keep-Alive
        self.sock = mksock(peer)
        self.keepalive = KeepAlive(self.sock, peer, 'video')

        # init aruco detector
        self.parameters =  aruco.DetectorParameters_create()
        self.aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_100)

        # init GUI
        if not HEADLESS:
            self. param_window = 'Gaze Params'
            self. image_window = 'Gaze Image'
            cv2.namedWindow(self.param_window, cv2.WINDOW_NORMAL)
            cv2.namedWindow(self.image_window, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.param_window, 600, 200)
            cv2.resizeWindow(self.image_window, 1280, 720)
            cv2.createTrackbar('X Offset', self.param_window, GAZE_OFFSET_X+100, 200, nothing)
            cv2.createTrackbar('Y Offset', self.param_window, GAZE_OFFSET_Y+100, 200, nothing)
            cv2.createTrackbar('Threshold', self.param_window, GAZE_THRESHOLD, 30, nothing)

    def detect(self, frame, data):
        # detect aruco fiducials
        corners, ids, rejectedImgPoints = aruco.detectMarkers(frame, self.aruco_dict, parameters=self.parameters)
        annotated =  aruco.drawDetectedMarkers(frame, corners)

        if data is not None:
            rows = frame.shape[0]
            cols = frame.shape[1]
            # convert to pixel coords and annotate image
            offsetx = GAZE_OFFSET_X
            offsety = GAZE_OFFSET_Y
            if not HEADLESS:
                offsetx = cv2.getTrackbarPos('X Offset', self.param_window) - 100
                offsety = cv2.getTrackbarPos('Y Offset', self.param_window) - 100
            gazex = int(round(cols*data['gp'][0])) - offsetx
            gazey = int(round(rows*data['gp'][1])) - offsety
            if not HEADLESS:
                cv2.circle(annotated, (gazex, gazey), 10, (0, 0, 255), 4)

            detectedid = None
            # check if gaze position falls within roi
            if len(corners) > 0 and ids is not None:
                for roi, id in zip(corners, ids):
                    if cv2.pointPolygonTest(roi, (gazex, gazey), False) == 1:
                        threshold = GAZE_THRESHOLD
                        if not HEADLESS:
                            threshold = cv2.getTrackbarPos('Threshold', self.param_window)
                        self.output_filters.set_threshold(threshold)
                        detectedid = self.output_filters.process(id[0])
                        if detectedid is not None:
                            logging.info('DETECTED MARKER ' + str(detectedid))
                            self.lastid = detectedid
                        break

            # annotate fiducial id on frame
            if  self.lastid is not None and not HEADLESS:
                cv2.putText(annotated, str(self.lastid), (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 4, (0, 255, 0), 2, cv2.LINE_AA)

            # display image
            if not HEADLESS:
                cv2.imshow(self.image_window, annotated)
            return detectedid
        else:
            if not HEADLESS:
                cv2.imshow(self.image_window, annotated)
            return None

    def stop(self):
        if not HEADLESS:
            cv2.destroyAllWindows()

class Serial():
    ''' handle serial port communication '''
    def __init__(self, port):
        self.ser = serial.Serial()
        self.ser.baudrate = 9600
        self.ser.port = port
        logging.info('Opened serial port ' + str(self.ser))
        self.ser.open()

    def write(self, data):
        if self.ser.is_open:
            self.ser.write(data + '\r\n')

    def close(self):
        self.ser.close()

class OutputFilters():
    ''' filter detections '''

    def __init__(self):
        self.queue = deque([None]*DWELL_TIME_FRAMES)
        self.threshold = 0

    def set_threshold(self, threshold):
        self.threshold = threshold

    # return most common element in a list
    # https://stackoverflow.com/questions/1518522/python-most-common-element-in-a-list
    def most_common(self, L):
        # get an iterable of (item, iterable) pairs
        SL = sorted((x, i) for i, x in enumerate(L))
        groups = itertools.groupby(SL, key=operator.itemgetter(0))
        # auxiliary function to get 'quality' for an item
        def _auxfun(g):
            item, iterable = g
            count = 0
            min_index = len(L)
            for _, where in iterable:
                count += 1
                min_index = min(min_index, where)
            return count, -min_index
        # pick the highest-count/earliest item
        return max(groups, key=_auxfun)[0]

    def process(self, id):
        self.queue.append(id)
        # get most detected fiducial id
        most_id = self.most_common(self.queue)
        # if we have more than threshold detections per time frame, it's a hit!!
        count = self.queue.count(most_id)
        if count >= self.threshold:
            return id
        else:
            return None

def signal_handler(signal, frame):
    global running
    running = False


if __name__=='__main__':
    import sys
    import signal

    signal.signal(signal.SIGINT, signal_handler)

    # init logging
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(logging.StreamHandler(sys.stderr))

    # parse command line
    if len(sys.argv) <= 1:
        output_port = None
        logging.warning('WARNING: No serial port specified. Usage: %s PORT ' % sys.argv[0])
    else:
        output_port = sys.argv[1]

    # init all object and start capturing
    peer = (DATA_STREAM_IP, DATA_STREAM_PORT)
    buffersync = BufferSync()
    video = Video(peer)

    captureProcess = vc.CaptureProcess(VIDEO_STREAM_URI, (1080, 1920, 3), USE_MULTIPROCESSING)
    captureProcess.start()

    et = EyeTracking(buffersync)
    et.start(peer)

    if output_port is not None and serial_available:
        serial = Serial(output_port)

    lastdata = None

    while(running):
        et.read()

        # read a video frame from video capture process
        frame, pts = captureProcess.read()
        buffersync.add_pts(pts)

        # read data from stream
        data = buffersync.sync()
        if data is not None:
            lastdata = data

        # detect fiducials
        id = video.detect(frame, lastdata)
        # write hits to serial port
        if id is not None and output_port is not None:
            serial.write(str(id))

        if not HEADLESS:
            if cv2.waitKey(1) & 0xFF == ord('q'):
                running = False
                break


    # shutdown
    captureProcess.stop()
    video.stop()
    et.stop()
    if output_port is not None:
        serial.close()
