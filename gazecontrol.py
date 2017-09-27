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

VIDEO_STREAM_URI = "rtsp://192.168.71.50:8554/live/scene"
DATA_STREAM_IP = "192.168.71.50"
DATA_STREAM_PORT = 49152

#VIDEO_STREAM_URI = "rtsp://[fe80::76fe:48ff:fe2c:b7a5]:8554/live/scene"
#VIDEO_STREAM_URI = "rtsp://0.0.0.0:8554/live/scene"
#DATA_STREAM_IP = "fe80::76fe:48ff:fe2c:b7a5"
#DATA_STREAM_PORT = 49152

running = True

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
    _et_syncs = []      # Eyetracking Sync items
    _et_queue = []      # Eyetracking Data items
    _et_ts = 0          # Last Eyetracking Timestamp
    _pts_queue = []     # Pts queue
    _pts_ts = 0         # Pts timestamp

    def add_et(self, obj):
        if 'pts' in obj:
            print obj
            self._et_syncs.append(obj)
        else:
            self._et_queue.append(obj)

    def add_pts_offset(self, offset, pts):
        """ Add pts to offset queue """
        self._pts_queue.append((offset, pts))

class EyeTracking():
    def __init__(self, buffersync):
        self._buffersync = buffersync

    def start(self, peer):
        self._sock = mksock(peer)
        #self._file = self._sock.makefile()
        self._keepalive = KeepAlive(self._sock, peer, "data")

    def read(self):
        while True:
            data, address = self._sock.recvfrom(1024)
            #data = self._file.readline()
            #print data
            dict = json.loads(data)
            self._buffersync.add_et(dict)
            if "gp" in dict:
                return dict
   
    def stop(self):
        self._sock.close()

class Video():
    def __init__(self, peer, url, buffersync):
        self.lastid = None
        self._buffersync = buffersync
        self._sock = mksock(peer)
        self._keepalive = KeepAlive(self._sock, peer, "video")
        self.cap = cv2.VideoCapture(url)

        self.parameters =  aruco.DetectorParameters_create()
        self.aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_100)

    def read(self):
        ret, frame = self.cap.read()
        pts = self.cap.get(cv2.CAP_PROP_POS_MSEC)
        frames = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
        self._buffersync.add_pts_offset(frames, pts)
        print "pts:", pts
        #print "offset:", frames
        return frame

    def detect(self, frame, data):
        corners, ids, rejectedImgPoints = aruco.detectMarkers(frame, self.aruco_dict, parameters=self.parameters)
        annotated =  aruco.drawDetectedMarkers(frame, corners)

        rows = frame.shape[0]
        cols = frame.shape[1]
        gazex = int(round(cols*data['gp'][0]))
        gazey = int(round(rows*data['gp'][1]))
        cv2.circle(annotated, (gazex, gazey), 5, (0,0,255), 2)
        
        detectedid = None
        if len(corners) > 0 and ids is not None:
            for roi, id in zip(corners, ids):
                if cv2.pointPolygonTest(roi, (gazex, gazey), False) == 1:
                    print id
                    detectedid = id[0]
                    self.lastid = detectedid

        if  self.lastid is not None:
            print self.lastid
            cv2.putText(annotated, str(self.lastid), (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 4, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.imshow('frame', annotated)
        return detectedid

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

    while(True):
        #print "-"*10
        data = et.read()
        #print data
        frame = video.read()
        id = video.detect(frame, data)
        if id is not None and output_port is not None:
            serial.write(str(id))

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    running = False

    video.stop()
    et.stop()
    if output_port is not None:
        serial.close()
