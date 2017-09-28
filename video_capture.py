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

import multiprocessing as mp
import threading
import Queue
import numpy as np
import cv2
from ctypes import c_uint8
import os
import logging

USE_THREADING = False or os.name == 'nt'

class CaptureProcess():
    def __init__(self, url, dims, use_multi):
        self.url = url
        self.use_multi = use_multi
        if self.use_multi:
            template = np.zeros(dims, np.uint8)
            self.arrayQueue = ArrayQueue(template, 1)
            if USE_THREADING:
                self.exitFlag = threading.Event()
                self.subProcess = threading.Thread(target=subprocess, args=(url, self.arrayQueue, self.exitFlag))
            else:
                self.exitFlag = mp.Event()
                self.subProcess = mp.Process(target=subprocess, args=(url, self.arrayQueue, self.exitFlag))


    def start(self):
        if self.use_multi:
            self.subProcess.start()
        else:
            self.cap = cv2.VideoCapture(self.url)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3);

    def read(self):
        if self.use_multi:
            return self.arrayQueue.get()
        else:
            ret, frame = self.cap.read()
            pts = int(self.cap.get(cv2.CAP_PROP_POS_MSEC))
            return frame, pts


    def stop(self):
        if self.use_multi:
            self.exitFlag.set()
            self.subProcess.join()
        else:
            self.cap.release()


def average_color(img):
    average_color = [img[:, :, i].mean() for i in range(img.shape[-1])]
    return [int(round(c)) for c in average_color]

def subprocess(url, arrayQueue, exitFlag):
    cap = cv2.VideoCapture(url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 3);

    while not exitFlag.is_set():
        ret, frame = cap.read()
        pts = int(cap.get(cv2.CAP_PROP_POS_MSEC))
        arrayQueue.put(frame, pts)

    cap.release()



# https://stackoverflow.com/questions/38666078/fast-queue-of-read-only-numpy-arrays
class ArrayQueue(object):
    def __init__(self, template, maxsize=0):
        if type(template) is not np.ndarray:
            raise ValueError('ArrayQueue(template, maxsize) must use a numpy.ndarray as the template.')
        if maxsize == 0:
            # this queue cannot be infinite, because it will be backed by real objects
            raise ValueError('ArrayQueue(template, maxsize) must use a finite value for maxsize.')

        # find the size and data type for the arrays
        # note: every ndarray put on the queue must be this size
        self.dtype = template.dtype
        self.shape = template.shape
        self.byte_count = len(template.data)

        # make a pool of numpy arrays, each backed by shared memory,
        # and create a queue to keep track of which ones are free
        self.array_pool = [None] * maxsize
        self.free_arrays = mp.Queue(maxsize)
        for i in range(maxsize):
            buf = mp.Array('c', self.byte_count, lock=False)
            self.array_pool[i] = np.frombuffer(buf, dtype=c_uint8).reshape(self.shape)
            #buf = mp.Array(c_uint8, self.byte_count)
            #self.array_pool[i] = np.frombuffer(buf.get_obj(), dtype=c_uint8).reshape(self.shape)
            cv2.circle(self.array_pool[i], (200, 200), 100, (0, 0, 255), 10)
            self.free_arrays.put(i)

        self.q = mp.Queue(maxsize)

    def put(self, item, pts):
        if item.dtype == self.dtype and item.shape == self.shape and len(item.data)==self.byte_count:
            # get the ID of an available shared-memory array
            try:
                arrayid = self.free_arrays.get(False)
            except Queue.Empty:
                #print 'FRAME DROPPED'
                return
            # copy item to the shared-memory array
            #self.array_pool[arrayid][:] = item
            np.copyto(self.array_pool[arrayid], item)
            # put the array's id (not the whole array) onto the queue
            self.q.put((arrayid, pts))
        else:
            raise ValueError('ndarray does not match type or shape of template used to initialize ArrayQueue')

    def get(self):
        items = self.q.get()
        arrayid = items[0]
        pts = items[1]
        # item is the id of a shared-memory array
        # copy the array
        if self.array_pool[arrayid] is not None:
            arr = self.array_pool[arrayid].copy()
            # put the shared-memory array back into the pool
            self.free_arrays.put(arrayid)
            return (arr, pts)
        else:
            return None
