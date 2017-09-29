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

import socket
import urllib2
import json
import time

def mksock(peer):
    ''' Create a socket pair for a peer description '''
    iptype = socket.AF_INET
    if ':' in peer[0]:
        iptype = socket.AF_INET6
    return socket.socket(iptype, socket.SOCK_DGRAM)


def post_request(base_url, api_action, data=None):
    ''' send an HTTP REST POST request '''
    url = base_url + api_action
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    data = json.dumps(data)
    response = urllib2.urlopen(req, data)
    data = response.read()
    json_data = json.loads(data)
    return json_data


def wait_for_status(base_url, api_action, key, values):
    ''' poll for an HTTP response '''
    url = base_url + api_action
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    response = urllib2.urlopen(req, None)
    data = response.read()
    json_data = json.loads(data)
    if json_data[key] in values:
        return json_data[key]
    else:
        return None