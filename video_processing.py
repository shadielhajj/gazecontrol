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

from collections import deque
import itertools
import operator
import net_utils
import tobii_api
import cv2
import cv2.aruco as aruco
import config
import logging

def nothing(x):
    pass

class VideoProcessing():
    ''' Detect Fiducial and check if gaze position falls within ROI '''

    def __init__(self, peer):
        self.output_filters = OutputFilters()
        self.lastid = None
        self.lastpts = 0
        # start video Keep-Alive
        self.sock = net_utils.mksock(peer)
        self.keepalive = tobii_api.KeepAlive(self.sock, peer, 'video')

        # init aruco detector
        self.parameters =  aruco.DetectorParameters_create()
        self.aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_100)

        # init GUI
        if not config.HEADLESS:
            self. param_window = 'Gaze Params'
            self. image_window = 'Gaze Image'
            cv2.namedWindow(self.param_window, cv2.WINDOW_NORMAL)
            cv2.namedWindow(self.image_window, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.param_window, 600, 200)
            cv2.resizeWindow(self.image_window, 1280, 720)
            cv2.createTrackbar('X Offset', self.param_window, config.GAZE_OFFSET_X+100, 200, nothing)
            cv2.createTrackbar('Y Offset', self.param_window, config.GAZE_OFFSET_Y+100, 200, nothing)
            cv2.createTrackbar('Threshold', self.param_window, config.GAZE_THRESHOLD, 30, nothing)

    def detect(self, frame, data):
        # detect aruco fiducials
        corners, ids, rejectedImgPoints = aruco.detectMarkers(frame, self.aruco_dict, parameters=self.parameters)
        annotated =  aruco.drawDetectedMarkers(frame, corners)

        if data is not None:
            rows = frame.shape[0]
            cols = frame.shape[1]
            # convert to pixel coords and annotate image
            offsetx = config.GAZE_OFFSET_X
            offsety = config.GAZE_OFFSET_Y
            if not config.HEADLESS:
                offsetx = cv2.getTrackbarPos('X Offset', self.param_window) - 100
                offsety = cv2.getTrackbarPos('Y Offset', self.param_window) - 100
            gazex = int(round(cols*data['gp'][0])) - offsetx
            gazey = int(round(rows*data['gp'][1])) - offsety
            if not config.HEADLESS:
                cv2.circle(annotated, (gazex, gazey), 10, (0, 0, 255), 4)

            detectedid = None
            # check if gaze position falls within roi
            if len(corners) > 0 and ids is not None:
                for roi, id in zip(corners, ids):
                    if cv2.pointPolygonTest(roi, (gazex, gazey), False) == 1:
                        threshold = config.GAZE_THRESHOLD
                        if not config.HEADLESS:
                            threshold = cv2.getTrackbarPos('Threshold', self.param_window)
                        self.output_filters.set_threshold(threshold)
                        detectedid = self.output_filters.process(id[0])
                        if detectedid is not None:
                            logging.info('DETECTED MARKER ' + str(detectedid))
                            self.lastid = detectedid
                        break

            # annotate fiducial id on frame
            if  self.lastid is not None and not config.HEADLESS:
                cv2.putText(annotated, str(self.lastid), (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 4, (0, 255, 0), 2, cv2.LINE_AA)

            # display image
            if not config.HEADLESS:
                cv2.imshow(self.image_window, annotated)
            return detectedid
        else:
            if not config.HEADLESS:
                cv2.imshow(self.image_window, annotated)
            return None

    def stop(self):
        self.keepalive.stop()
        if not config.HEADLESS:
            cv2.destroyAllWindows()


class OutputFilters():
    ''' filter detections '''

    def __init__(self):
        self.queue = deque([None]*config.DWELL_TIME_FRAMES)
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