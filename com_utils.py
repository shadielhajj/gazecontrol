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

import serial
import logging

class Serial():
    ''' handle serial port communication '''
    def __init__(self, port):
        self.ser = serial.Serial()
        self.ser.baudrate = 115200
        self.ser.port = port
        logging.info('Opened serial port ' + str(self.ser))
        self.ser.open()

    def write(self, data):
        if self.ser.is_open:
            self.ser.write(data + '\r\n')

    def close(self):
        self.ser.close()
