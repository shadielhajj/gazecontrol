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


import json
import socket
import time
import threading
import logging
import net_utils

class KeepAlive:
    ''' Sends keep-alive signals to a peer via a socket (Livestream API) '''
    running = True

    def __init__(self, sock, peer, streamtype, timeout=1):
        self.timeout = timeout
        jsonobj = json.dumps({
            'op' : 'start',
            'type' : '.'.join(['live', streamtype, 'unicast']),
            'key' : 'anything'})
        sock.sendto(jsonobj, peer)
        td = threading.Timer(0, self.__send_keepalive_msg, [sock, jsonobj, peer])
        td.start()

    def __send_keepalive_msg(self, socket, jsonobj, peer):
        while self.running:
            socket.sendto(jsonobj, peer)
            time.sleep(self.timeout)

    def stop(self):
        self.running = False


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
        self.sock = net_utils.mksock(peer)
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
            #if 'marker2d' in dict:
            #    print dict

    def stop(self):
        self.keepalive.stop()
        self.sock.close()


class Calibration():
    ''' calibrate the glasses using the Tobii REST API '''
    is_calibrating = False

    def __create_project(self):
        json_data = net_utils.post_request(self.base_url, '/api/projects')
        return json_data['pr_id']

    def __create_participant(self, project_id):
        data = {'pa_project': project_id}
        json_data = net_utils.post_request(self.base_url, '/api/participants', data)
        return json_data['pa_id']

    def __create_calibration(self, project_id, participant_id):
        data = {'ca_project': project_id, 'ca_type': 'default', 'ca_participant': participant_id}
        json_data = net_utils.post_request(self.base_url, '/api/calibrations', data)
        return json_data['ca_id']

    def create(self, url):
        self.base_url = url
        self.project_id = self.__create_project()
        self.participant_id = self.__create_participant(self.project_id)
        #logging.info("Project: " + project_id + ", Participant: " + participant_id + ", Calibration: " + calibration_id + " ")

    def start(self):
        logging.info('Starting calibration')
        self.calibration_id = self.__create_calibration(self.project_id, self.participant_id)
        net_utils.post_request(self.base_url, '/api/calibrations/' + self.calibration_id + '/start')
        self.is_calibrating = True

    def update(self):
        if self.is_calibrating:
            status = net_utils.wait_for_status(self.base_url, '/api/calibrations/' + self.calibration_id + '/status', 'ca_state', ['failed', 'calibrated'])
            if status is not None:
                self.is_calibrating = False
            return status
        else:
            return None
