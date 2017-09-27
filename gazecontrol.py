#   Gaze Control - A real-time control application for Tobii Pro Glasses 2. 
#
#   Copyright 2017 Shadi El Hajj
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


import numpy as np
import cv2
import cv2.aruco as aruco
import json
import socket
import time
import threading
import serial
from collections import deque
from itertools import groupby
import itertools
import operator

VIDEO_STREAM_URI = "rtsp://192.168.71.50:8554/live/scene"
DATA_STREAM_IP = "192.168.71.50"

#VIDEO_STREAM_URI = "rtsp://[fe80::76fe:48ff:fe2c:b7a5]:8554/live/scene"
#DATA_STREAM_IP = "fe80::76fe:48ff:fe2c:b7a5"

DATA_STREAM_PORT = 49152

DWELL_TIME_FRAMES = 30

running = True

def nothing(x):
    pass

def mksock(peer):
    """ Create a socket pair for a peer description """
    iptype = socket.AF_INET
    if ':' in peer[0]:
        iptype = socket.AF_INET6
    return socket.socket(iptype, socket.SOCK_DGRAM)

class KeepAlive:
    """ Sends keep-alive signals to a peer via a socket """
    def __init__(self, sock, peer, streamtype, timeout=1):
        self.timeout = timeout
        jsonobj = json.dumps({
            'op' : 'start',
            'type' : ".".join(["live", streamtype, "unicast"]),
            'key' : 'anything'})
        sock.sendto(jsonobj, peer)
        td = threading.Timer(0, self.send_keepalive_msg, [sock, jsonobj, peer])
        td.start()

    def send_keepalive_msg(self, socket, jsonobj, peer):
        while running:
            socket.sendto(jsonobj, peer)
            time.sleep(self.timeout)

class BufferSync():
    et_syncs = []      # Eyetracking Sync items
    et_queue = []      # Eyetracking Data items
    video_pts = 0
    last_video_ts = 0
    last_data_ts = 0

    def add_et(self, obj):
        if 'pts' in obj:
            #print obj
            self.et_syncs.append(obj)
            self.lastts = self.last_video_ts * 1000
        elif "gp" in obj:
            self.et_queue.append(obj)

    def add_pts(self, pts):
        """ Add pts to offset queue """
        self.video_pts = pts
    
    def sync(self):
        pts = int(self.video_pts * 90)
        tsoffset = int(self.video_pts*1000 - self.last_video_ts)
        if len(self.et_syncs) > 0:
            #print '----'
            #print pts, ' - ', self.et_syncs[-1]['pts']
            if (pts < self.et_syncs[-1]['pts']):
                #print 'VIDEO IS BEHIND'
                pastpts = filter(lambda x: x['pts'] <= pts, self.et_syncs)
                self.et_syncs = filter(lambda x: x['pts'] > pts, self.et_syncs)
                if len(pastpts) > 0:
                    #print pts, ' - ', pastpts[-1]['pts']
                    self.last_data_ts = pastpts[-1]['ts']
                pastts = filter(lambda x: x['ts'] <= self.last_data_ts + tsoffset, self.et_queue)
                self.et_queue = filter(lambda x: x['ts'] > self.last_data_ts + tsoffset, self.et_queue)
                if len(pastts) > 0:
                    return pastts[-1]
                else:
                    return None

            else:
                print 'VIDEO IS AHEAD'
                return None

        

class EyeTracking():
    def __init__(self, buffersync):
        self.buffersync = buffersync

    def start(self, peer):
        self.sock = mksock(peer)
        self.sock.setblocking(0)
        #self.file = self.sock.makefile()
        self.keepalive = KeepAlive(self.sock, peer, "data")

    def read(self):
        while True:
            try:
                data, address = self.sock.recvfrom(1024)
            except socket.error:
                return None
            #data = self.file.readline()
            #print data
            dict = json.loads(data)
            self.buffersync.add_et(dict)
            if 'marker2d' in dict:
                print dict
            #if "gp" in dict:
            #    return dict
   
    def stop(self):
        self.sock.close()

class Video():
    def __init__(self, peer, url, buffersync):
        self.output_filters = OutputFilters()
        self.lastid = None
        self.lastpts = 0
        self.buffersync = buffersync
        self.sock = mksock(peer)
        self.keepalive = KeepAlive(self.sock, peer, "video")
        self.cap = cv2.VideoCapture(url)

        self.parameters =  aruco.DetectorParameters_create()
        self.aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_100)
        self. param_window = "Gaze Params"
        self. image_window = "Gaze Image"
        cv2.namedWindow(self.param_window, cv2.WINDOW_NORMAL)
        cv2.namedWindow(self.image_window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.param_window, 600, 200)
        cv2.resizeWindow(self.image_window, 1280, 720)
        cv2.createTrackbar("X Offset", self.param_window, 100, 200, nothing)
        cv2.createTrackbar("Y Offset", self.param_window, 100, 200, nothing)
        cv2.createTrackbar("Threshold", self.param_window, 10, 30, nothing)

    def read(self):
        ret, frame = self.cap.read()
        pts = self.cap.get(cv2.CAP_PROP_POS_MSEC)
        #pts = int(pts * 90) # convert to data pts resolution (90khz)
        self.buffersync.add_pts(pts)
        return frame

    def detect(self, frame, data):
        corners, ids, rejectedImgPoints = aruco.detectMarkers(frame, self.aruco_dict, parameters=self.parameters)
        annotated =  aruco.drawDetectedMarkers(frame, corners)

        if data is not None:
            rows = frame.shape[0]
            cols = frame.shape[1]
            gazex = int(round(cols*data['gp'][0])) - (cv2.getTrackbarPos('X Offset', self.param_window)-100)
            gazey = int(round(rows*data['gp'][1])) - (cv2.getTrackbarPos('Y Offset', self.param_window)-100)
            cv2.circle(annotated, (gazex, gazey), 10, (0, 0, 255), 4)
        
            detectedid = None
            if len(corners) > 0 and ids is not None:
                for roi, id in zip(corners, ids):
                    if cv2.pointPolygonTest(roi, (gazex, gazey), False) == 1:
                        threshold = cv2.getTrackbarPos('Threshold', self.param_window)
                        self.output_filters.set_threshold(threshold)
                        detectedid = self.output_filters.process(id[0])
                        if detectedid is not None:
                            print detectedid
                            self.lastid = detectedid
                        break

            if  self.lastid is not None:
                cv2.putText(annotated, str(self.lastid), (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 4, (0, 255, 0), 2, cv2.LINE_AA)
        
            cv2.imshow(self.image_window, annotated)
            return detectedid
        else:
            cv2.imshow(self.image_window, annotated)
            return None

    def stop(self):
        self.cap.release()
        cv2.destroyAllWindows()

class Serial():
    def __init__(self, port):
        self.ser = serial.Serial()
        self.ser.baudrate = 9600
        self.ser.port = port
        print self.ser
        self.ser.open()
    
    def write(self, data):
        print self.ser.is_open
        if self.ser.is_open:
            self.ser.write(data + '\r\n')

    def close(self):
        self.ser.close()

class OutputFilters():
    def __init__(self):
        self.queue = deque([None]*DWELL_TIME_FRAMES)
        self.threshold = 0

    def set_threshold(self, threshold):
        self.threshold = threshold

    # https://stackoverflow.com/questions/1518522/python-most-common-element-in-a-list
    def most_common(self, L):
        # get an iterable of (item, iterable) pairs
        SL = sorted((x, i) for i, x in enumerate(L))
        # print 'SL:', SL
        groups = itertools.groupby(SL, key=operator.itemgetter(0))
        # auxiliary function to get "quality" for an item
        def _auxfun(g):
            item, iterable = g
            count = 0
            min_index = len(L)
            for _, where in iterable:
                count += 1
                min_index = min(min_index, where)
            # print 'item %r, count %r, minind %r' % (item, count, min_index)
            return count, -min_index
        # pick the highest-count/earliest item
        return max(groups, key=_auxfun)[0]

    def process(self, id):
        self.queue.append(id)
        most_id = self.most_common(self.queue)
        count = self.queue.count(most_id)
        if count >= self.threshold:
            #print self.queue
            return id
        else:
            return None

if __name__=="__main__":

    import sys
    if len(sys.argv) <= 1:
        output_port = None
    else:
        output_port = sys.argv[1]

    peer = (DATA_STREAM_IP, DATA_STREAM_PORT)

    sync = BufferSync()

    video = Video(peer, VIDEO_STREAM_URI, sync)

    et = EyeTracking(sync)
    et.start(peer)

    if output_port is not None:
        serial = Serial(output_port)

    lastdata = None
    while(True):
        #print "-"*10
        et.read()

        frame = video.read()
        data = sync.sync()
        if data is not None:
            lastdata = data

        id = video.detect(frame, lastdata)
        if id is not None and output_port is not None:
            serial.write(str(id))

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    running = False

    video.stop()
    et.stop()
    if output_port is not None:
        serial.close()
