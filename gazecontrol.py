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


import cv2
import video_capture as vc
import video_processing as vp
import tobii_api
import logging
import com_utils
import config
import time

serial_available = True
try:
    import serial
except ImportError:
    logging.warning('WARNING: Serial port module not installed')
    serial_available = False

running = True

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

    # init calibration
    calibration = tobii_api.Calibration()
    calibration.create('http://'+config.DATA_STREAM_IP)

    # init all object and start capturing

    if output_port is not None and serial_available:
        serialport = com_utils.Serial(output_port)

    peer = (config.DATA_STREAM_IP, config.DATA_STREAM_PORT)
    buffersync = tobii_api.BufferSync()
    video = vp.VideoProcessing(peer)

    captureProcess = vc.CaptureProcess(config.VIDEO_STREAM_URI, (1080, 1920, 3), config.USE_MULTIPROCESSING)
    captureProcess.start()

    et = tobii_api.EyeTracking(buffersync)
    et.start(peer)


    lastdata = None

    framecounter = 0
    newframetime = 0
    lastframetime = 0
    framestocount = 20
    while(running):
        et.read()

        # read a video frame from video capture process
        frame, pts = captureProcess.read()
        buffersync.add_pts(pts)
        framecounter = framecounter + 1

        if framecounter % framestocount == 0:
            newframetime = time.time() 
            logging.info('FPS: ' + str(framestocount/(newframetime-lastframetime)))
            lastframetime = time.time()
        # read data from stream
        data = buffersync.sync()
        if data is not None:
            lastdata = data

        # detect fiducials
        id, serialangledist = video.detect(frame, lastdata)
        # write hits to serial port
        if serialangledist is not None and output_port is not None:
            serialport.write(serialangledist)
            logging.info('Serialangledist: '+serialangledist)



        status = calibration.update()
        if status == 'failed':
            logging.warn('WARNING: Calibration failed, using default calibration instead')
            if output_port is not None:
                serialport.write('F')
        elif status == 'calibrated':
            logging.info('Calibration successful')
            if output_port is not None:
                serialport.write('S')

        if not config.HEADLESS:
            key = cv2.waitKey(1)
            if key & 0xFF == ord('c'): # calibrate
                status = calibration.start()
            elif key & 0xFF == ord('q'): # quit
                running = False
                break


    # shutdown
    captureProcess.stop()
    video.stop()
    et.stop()
    if output_port is not None:
        serialport.close()
