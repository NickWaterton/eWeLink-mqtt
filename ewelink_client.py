#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
see https://github.com/hansharhoff/HASS-sonoff-ewelink for login sequence used
see https://github.com/AlexxIT/SonoffLAN/blob/master/custom_components/sonoff/core/ewelink/cloud.py for new login sequence (10/7/22)
also see https://coolkit-technologies.github.io/eWeLink-API/#/en/DeveloperGuideV2
N Waterton 11th Jan 2019 V1.0 First release
N. Waterton 18th April 20201 V 1.2 Updated login method.
N. Waterton 19th April 20201 V 1.2.1 Added region selector to constructor.
N. Waterton 8th July 20202 V 1.2.2 Added retry on login failure, new appId and AppSecret added
N. Waterton 13th July 20202 V 2.0.0 Complete re-write based on https://github.com/AlexxIT/SonoffLAN/blob/master/custom_components/sonoff/core/ewelink/cloud.py 
'''

'''
Client class for connecting to iTEAD ewelink devices.
uses Itead's IoTgo framework see https://github.com/itead/IoTgo for more details
see http://www.pgeorgiev.com/how-do-sonoff-devices-work/ for a full explanation of how this works

You need to download the ewelink app (android or ios) and create an account, using either a phone number or e-mail
and password. You then add your device to the ewelink app.

This was specifically written for the Autoslide door device https://autoslide.com/ but I expanded it to cover other Sonoff devices.

For Autoslide doors, you can also do this using the Autoslide app (see ewelink_devices for more explanation of the autoslide device)
You can't control an Autoslide door using the ewelink app, but you can register it.

Assuming you can get the device to connect to your WiFi network (I had trouble, and had to use the
eWelink app in "legacy" mode to get it to connect), you should be able to register the device.

Once you have control using the app, you can now use this client for connecting and controlling your
device via MQTT, or command line/API.
 
Now you are registered, you should have your e-mail address (or phone number) and a password for your Autoslide/eWelink account.
When you instantiate the client, you need to pass the e-mail address (or phone number) and password to the client constructor.
eg:
client = ewelink_client.EwelinkClient(email, password)
or
client = ewelink_client.EwelinkClient(phone, password)
 
This is the minimum needed to connect the client.
 
iTEAD eWelink uses cloud servers to authenticate your login, and issue an authorization token, the authorization token is
re-issued every time you log in. We then take the authorization token, and use this to open a websocked client to iTEADs servers.
This websocket interface is the connection to the Autoslide device. This is an indirect connection - ie we send to iTEAD's servers
- Autoslide connects to iTEAD's servers, and the servers pass messages back and forth. This is where the disconnects and Timeouts can happen..

Do not hit the servers with too many commands too quickly, max is about 1 per second. You will get Timeouts if you send commands too quickly.

eWelink uses "regions" to determine which servers to use. This client is set to use the US (North Amrican as I'm in Canada) servers by
default, and is supposed to select other regions if that doesn't work - but I haven't tried this out.

The client is an asynchronous (asycio) websocket client, and is written for Python 3.6.
You can optionally pass in your own asyncio loop, and/or an MQTT client object (using paho-mqtt) with an optional publication topic.
There is an optional iemi string, but I'm not sure what this is for and I supply a random string as default (which works).
You can supply your own or leave it as default.

If you don't supply an asyncio loop, the client will create it's own, or pick up a pre-existing loop if there is one, and start it in a new thread.

So to _publish/receive commands via MQTT you would create an MQTT client instance, and create the ewelink client like this:

client = ewelink_client.EwelinkClient(phoneNumber=None, email='e-mail@gmail.com', password='myPassword', imei=None, loop=None, mqttc, pub_topic='/ewelink_status/')

where mqttc is a paho-mqtt client instance.

if loop is None, you can now use client functions like:
client.get_config()
client.set_option(option, value, device=0)

If you do supply an asyncio loop, you will need to start the loop, with the client.login() - like this:
loop.run_until_complete(client.login())

see ewelink_server.py for a full working example.  
      
The actual configuration of all this is gleaned from web sources on the IoTgo protocol, and reverse engineering the data.
I have no engineering documents to go on, so some of the parameters are a best guess as to what they do.

Please update me if you have better information, or find out what unknown parameters are/do.

The actual devices themselves are defined in ewelink_devices.py, with one class per device type. The correct class will be instantiated for a 
device based on the 'productModel' returned by the servers (and defined in the class). If no productModel/class match is found, a Default class
is used for the device that gives basic control.

device parameters are published to an mqtt topic like this:
/ewelink_status/deviceid/param value
You can define /ewelink_status/ to be what you want (this is the client default)
deviceid is the deviceid hard coded into the device
param is either the default parameters name returned by the server, or a user defined string (defined in the device class).
The complete json response from the device is published to:
/ewelink_status/deviceid/json {json_string}

in linux using mosqitto mqtt client tools the command would be:
mosquitto_sub -v -t "/ewelink_status/#"

You can control the device by publishing to:
/ewelink_command/deviceid/param value
(where the components are the same as above).
You can define /ewelink_command/ to be what you want (this is what you subscribe to when you create the mqtt client)
You can send a complete json string to:
/ewelink_command/deviceid/set_json {json_string}
This will update just the params of the device, and can be used for setting timers etc. See the section on timers in the client class.

Example Linux commands are:
mosquitto_pub -t "/ewelink_command/10005d73ab/set_switch" -m "off"
mosquitto_pub -t "/ewelink_command/10005d73ab/send_json" -m "{'timers': [{'enabled': 1, 'coolkit_timer_type': 'repeat', 'at': '* * * * * *', 'period': '1', 'type': 'repeat', 'do': {'switch': 'on'}, 'mId': '87d1dfdf-e9cb-d9ee-af2a-42362079e6a4'}]}"
You should use " for json (not ') but the client will convert for you.
You can also add timers using the 'add_timer" command, list them with 'list_timers' and so on. The timers are complex, so best to use the built in commands rather than json.

Device initialization parameters can be set using client.set_initial_parameters(deviceid, **kwargs) method,
and are passed to the device client on creation, the client class decides what to do with the parameters.

There are only a few devices defined in ewelink_devices.py (I only have a few to test), but feel free to add more, or update the existing ones.
      
Nick Waterton P.Eng.
'''

'''
Autoslide device:
  {
    "name": "Patio Door",
    "deviceid": "100050a4f3",
    "apikey": "530303a6-cf2c-4246-894c-50855b00e6d8",
    "extra": {
      "uiid": 54,
      "description": "20180813001",
      "brandId": "5a6fcf00f620073c67efc280",
      "apmac": "d0:27:00:a1:47:37",
      "mac": "d0:27:00:a1:47:36",
      "ui": "\u63a8\u62c9\u5ba0\u7269\u95e8",
      "modelInfo": "5af3f5332c8642b001540dac",
      "model": "PSA-BTA-GL",
      "manufacturer": "\u9752\u5c9b\u6fb3\u601d\u5fb7\u667a\u80fd\u95e8\u63a7\u7cfb\u7edf\u6709\u9650\u516c\u53f8",
      "staMac": "68:C6:3A:D5:9E:E6"
    },
    "brandName": "AUTOSLIDE",
    "brandLogo": "",
    "showBrand": true,
    "productModel": "WFA-1",
    "devConfig": {},
    "settings": {
      "opsNotify": 0,
      "opsHistory": 1,
      "alarmNotify": 1,
      "wxAlarmNotify": 0,
      "wxOpsNotify": 0,
      "wxDoorbellNotify": 0,
      "appDoorbellNotify": 1
    },
    "devGroups": [],
    "family": {
      "familyid": "5f7de770e962cd0007681550",
      "index": -1,
      "members": [
        "0f824698-9928-4d56-8658-1a914f04465a"
      ],
      "roomid": "5f7de770e962cd000768154d"
    },
    "shareTo": [],
    "devicekey": "4123ec79-d2c3-4d32-930a-037ca3b5d0ef",
    "online": true,
    "params": {
      "sledOnline": "off",
      "rssi": -71,
      "fwVersion": "2.7.0",
      "staMac": "68:C6:3A:D5:9E:E6",
      "c": "1",
      "m": "2",
      "n": "0",
      "b": "3",
      "a": "3",
      "j": "00"
    },
    "isSupportGroup": false,
    "isSupportedOnMP": false,
    "deviceFeature": {}
  },
'''

import json
import asyncio
import websockets
from aiohttp import ClientSession, ClientTimeout, ClientConnectorError, WSMessage, ClientWebSocketResponse
import time
import math
import sys
import random
import uuid
import string
import hmac
import hashlib
import base64
import collections
import re
import yaml
from ewelink_devices import *
import inspect

import logging

from typing import Callable, Dict, List, Optional, TypedDict

from custom_components.sonoff.core.ewelink.__init__ import XRegistry, SIGNAL_ADD_ENTITIES
from custom_components.sonoff.core.ewelink.base import XRegistryBase, XDevice, SIGNAL_UPDATE, SIGNAL_CONNECTED
from custom_components.sonoff.core.ewelink.cloud import XRegistryCloud, AuthError, APP

_LOGGER = logger = logging.getLogger('Main.'+__name__)

__version__ = '2.0.0'

# appId and secret from https://github.com/skydiver/ewelink-api/blob/master/src/data/constants.js
APP.append(('YzfeftUVcZ6twZw1OoVKPRFYTrGEg01Q', '4G91qSoboqYO4Y0XJ0LPPKIsq8reHdfa'))
# My appId and secret from my AutoslideNet app. can only use with Oauth2 authentication flow, needs to be renewed on 12th July every year
OAUTH = [('tKjp3XDwekm5NROJ0TgfrvpHjGJnrXiq', 'nEu1HrliSwf1TQCqM7j97onLppK0F1LZ')]

patio_door_device = json.loads('''{ "name": "Patio Door",
                                    "deviceid": "100050a4f3",
                                    "apikey": "530303a6-cf2c-4246-894c-50855b00e6d8",
                                    "extra": {
                                      "uiid": 54,
                                      "description": "20180813001",
                                      "brandId": "5a6fcf00f620073c67efc280",
                                      "apmac": "d0:27:00:a1:47:37",
                                      "mac": "d0:27:00:a1:47:36",
                                      "ui": "\u63a8\u62c9\u5ba0\u7269\u95e8",
                                      "modelInfo": "5af3f5332c8642b001540dac",
                                      "model": "PSA-BTA-GL",
                                      "manufacturer": "\u9752\u5c9b\u6fb3\u601d\u5fb7\u667a\u80fd\u95e8\u63a7\u7cfb\u7edf\u6709\u9650\u516c\u53f8",
                                      "staMac": "68:C6:3A:D5:9E:E6"
                                    },
                                    "brandName": "AUTOSLIDE",
                                    "brandLogo": "",
                                    "showBrand": true,
                                    "productModel": "WFA-1",
                                    "devConfig": {},
                                    "settings": {
                                      "opsNotify": 0,
                                      "opsHistory": 1,
                                      "alarmNotify": 1,
                                      "wxAlarmNotify": 0,
                                      "wxOpsNotify": 0,
                                      "wxDoorbellNotify": 0,
                                      "appDoorbellNotify": 1
                                    },
                                    "devGroups": [],
                                    "family": {
                                      "familyid": "5f7de770e962cd0007681550",
                                      "index": -1,
                                      "members": [
                                        "0f824698-9928-4d56-8658-1a914f04465a"
                                      ],
                                      "roomid": "5f7de770e962cd000768154d"
                                    },
                                    "shareTo": [],
                                    "devicekey": "4123ec79-d2c3-4d32-930a-037ca3b5d0ef",
                                    "online": true,
                                    "params": {
                                      "sledOnline": "off",
                                      "rssi": -63,
                                      "fwVersion": "2.7.0",
                                      "staMac": "68:C6:3A:D5:9E:E6",
                                      "c": "1",
                                      "m": "2",
                                      "n": "0",
                                      "b": "3",
                                      "a": "3",
                                      "j": "00"
                                    },
                                    "isSupportGroup": false,
                                    "isSupportedOnMP": false,
                                    "deviceFeature": {}
                                }''')

class EwelinkClient(XRegistryCloud):
    """A websocket client for connecting to ITEAD's devices."""
    
    __version__ = __version__
    
    _ISOregex = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$'
    _cronregex = "{0}\s+{1}\s+{2}\s+{3}\s+{4}".format(  "(?P<minute>\*|[0-5]?\d)",
                                                        "(?P<hour>\*|[01]?\d|2[0-3])",
                                                        "(?P<day>\*|0?[1-9]|[12]\d|3[01])",
                                                        "(?P<month>\*|0?[1-9]|1[012])",
                                                        "(?P<day_of_week>\*|[0-6](\-[0-6])?)"
                                                      )
                                                      
    APP = [# ("oeVkj2lYFGnJu5XUtWisfW4utiN4u9Mq", "6Nz4n0xA8s8qdxQf2GqurZj2Fs55FUvM"),  #old - no longer works 10/7/22
            ("KOBxGJna5qkk3JLXw3LHLX3wSNiPjAVi", "4v0sv6X5IM2ASIBiNDj6kGmSfxo40w7n"),   #Working as of 13/7/22
            ("R8Oq3y0eSZSYdKccHlrQzT1ACCOUT9Gv", "1ve5Qk9GXfUhKAn1svnKwpAlxXkMarru"),   #Does not show Autoslide device, but can still use it (if you know the deviceid)
            ('YzfeftUVcZ6twZw1OoVKPRFYTrGEg01Q', '4G91qSoboqYO4Y0XJ0LPPKIsq8reHdfa'),   #appId and secret from https://github.com/skydiver/ewelink-api/blob/master/src/data/constants.js
            ('tKjp3XDwekm5NROJ0TgfrvpHjGJnrXiq', 'nEu1HrliSwf1TQCqM7j97onLppK0F1LZ')    #My appId and secret from my AutoslideNet app. can only use with Oauth2 authentication flow, needs to be renewed on 12th July every year
          ]
    
    def __init__(self, phoneNumber=None,email=None, password=None, loop=None, mqttc=None, pub_topic='/ewelink_status/', region='us', configuration_file=None):
        #super().__init__(session)
        self._region = region
        self.logger = logging.getLogger('Main.'+__class__.__name__)
        global _LOGGER
        _LOGGER = self.logger
        self.logger.debug('Started Class: %s, version: %s' % (__class__.__name__,self.__version__))
        self.wsc_url = None
        self.apikey = 'UNCONFIGURED'
        self.authenticationToken = 'UNCONFIGURED'
        self.poll = False

        self._match_iso8601 = re.compile(self._ISOregex).match
        self._match_cron = re.compile(self._cronregex).match
        
        self._devices = []
        self._clients = {}
        self._parameters = {}  #initial parameters for clients
        self.app_key = 0
        #client initialization parameters
        self._configuration = {}
        self._phoneNumber, self._email, self._password, self._region, self._pub_topic = self.get_initialization_parameters(configuration_file, phoneNumber, email, password, region, pub_topic)
        
        if self._password is None or (self._phoneNumber is None and self._email is None) :
            self.logger.error('phone number/email or password cannot be empty')
            sys.exit(1)
        
        self._mqttc = mqttc
        if self._mqttc:
            self._mqttc.on_message = self._on_message
            #self._pub_topic = pub_topic
        self._device_classes = {}
        clsmembers = inspect.getmembers(sys.modules[__name__], inspect.isclass) #get devices loaded from modules
        for dev_class in clsmembers:
            try:
                self._device_classes[dev_class[1]] = dev_class[1].productModel
                self.logger.debug('loaded device %s, V:%s, for device models: %s' % (dev_class[0],dev_class[1].__version__,dev_class[1].productModel))
            except AttributeError:
                pass    
        
        if not loop:
            self.loop = asyncio.get_event_loop()
            if not self.loop.is_running():
                #run login in another thread, otherwise client blocks
                from threading import Thread
                self.t = Thread(target=self.loop.run_until_complete, args=(self.login(),))
                self.t.start()
                
                if sys.platform != 'win32':     #linux only stuff
                    import signal
                    for signame in ('SIGINT', 'SIGTERM'):
                        self.loop.add_signal_handler(getattr(signal, signame),self.disconnect)
        else:
            self.loop = loop
            
    def get_initialization_parameters(self, file, phoneNumber, email, password, region, pub_topic):
        if file:
            if self.load_config(file):
                my_phoneNumber = self._configuration['log_in'].get('phoneNumber', phoneNumber)
                my_email       = self._configuration['log_in'].get('email',email)
                my_password    = self._configuration['log_in'].get('password',password)
                my_region      = self._configuration['log_in'].get('region',region)
                my_pub_topic   = self._configuration['mqtt'].get('pub_topic',pub_topic)
                
                if my_phoneNumber is None:
                    my_phoneNumber = phoneNumber
                if my_email is None:
                    my_email = email
                if my_password is None:
                    my_password = password
                if my_region is None:
                    my_region = region
                if my_pub_topic is None:
                    my_pub_topic = pub_topic
                    
                return my_phoneNumber, my_email, my_password, my_region, my_pub_topic 
                
        return phoneNumber, email, password, region, pub_topic  
        
    def load_config(self, file):
        with open(file, 'r') as stream:
            try:
                self._configuration = yaml.load(stream)
                return True
            except yaml.YAMLError as e:
                self.logger.exception(e)
                return False
            
    def pprint(self,obj):
        """Pretty JSON dump of an object."""
        return(json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': ')))
        
    @property
    def devices(self):
        return self._devices
        
    def get_config(self, deviceid = ''):
        if deviceid:
            client = self._get_client(deviceid)
            return client.config
        else:
            device_list = []
            for client in self._clients.values():
               device_list.append(client.config)
        return device_list
        
    def set_initial_parameters(self, deviceid, **kwargs):
        '''
        set initial parameters for client
        '''
        if deviceid == 'default':
            deviceid = '0'
        self._parameters[deviceid] = kwargs
        
    async def start_connection(self, app=0, oauth=False):
        username = self._email if self._email else self._phoneNumber
        password = self._password
        try:
            async with ClientSession(timeout=ClientTimeout(total=5.0)) as session:
                super().__init__(session)
                self.region = self._region
                if oauth:
                    APP.extend(OAUTH)
                if app > len(APP)-1:
                    self.logger.warning('Selected appId({}) index out of range (max{}), using 0'.format(app, len(APP)-1))
                    app = 0
                self.app_key = app
                self.logger.info('Connecting, login: {}, password: {}, appid({}): {}'.format(username, password, 'Oauth2' if oauth else 'v2', APP[app]))
                if oauth:
                    connected = await self.oauth_login(username, password, app)
                else:
                    connected = await self.login(username, password, app)
                
                if connected:
                    self.logger.info('Connected: auth: {}'.format(json.dumps(self.auth, indent=2)))
                    homes = await self.get_homes()
                    self.logger.info('Homes: {}'.format(json.dumps(homes, indent=2)))
                    if homes:
                        self._devices = await self.get_devices(homes)
                        self.logger.info('Devices: {}'.format(json.dumps(self._devices, indent=2)))
                        if patio_door_device['deviceid'] not in [device['deviceid'] for device in self._devices]:
                            self.logger.info('Adding Patio Door to _devices')
                            self._devices.append(XDevice(patio_door_device))
                            self.poll = True
                        if self._devices:
                            self._create_client_devices()
                            self.logger.info('Started WS receive - waiting for messages')
                            self.start()
                            count = 0
                            while not self.online and count < 5:
                                await asyncio.sleep(1)
                                count += 1
                            count = 0
                            while self.online:
                                self.logger.debug('Waiting...')
                                await asyncio.sleep(60)
                                if self.poll:
                                    await self.send(patio_door_device['deviceid'])
                else:
                    self.logger.error('Failed to login')
        
        except Exception as e:
            self.logger.exception(e)
        return
        
    async def oauth_login(self, username: str, password: str, app=0) -> bool:
        self._publish('client', 'status', "Starting")
        if username == "token":
            self.region, token = password.split(":")
            return await self.login_token(token, 1)

        # https://coolkit-technologies.github.io/eWeLink-API/#/en/DeveloperGuideV2
        appid, appsecret = APP[app]
        ts = time.time()
        payload = {
            "password": password,
            "countryCode": "+86",
        }
        payload['ts'] = int(ts)
        payload['appid'] = appid
        
        if "@" in username:
            payload["email"] = username
        elif username.startswith("+"):
            payload["phoneNumber"] = username
        else:
            payload["phoneNumber"] = "+" + username

        # ensure POST payload and Sign payload will be same
        data = json.dumps(payload).encode()
        hex_dig = hmac.new(appsecret.encode(), data, hashlib.sha256).digest()

        headers = {
            "Authorization": "Sign " + base64.b64encode(hex_dig).decode(),
            "Content-Type": "application/json",
            "X-CK-Appid": appid,
        }
        r = await self.session.post(
            self.host.replace('apia','api') + ":8080/api/user/login", data=data, headers=headers,
            timeout=30
        )
        resp = await r.json()

        # wrong default region
        if resp.get("error") == 301:
            self.region = resp["region"]
            r = await self.session.post(
                self.host.replace('apia','api') + ":8080/api/user/login", data=data, headers=headers,
                timeout=30
            )
            resp = await r.json()
        _LOGGER.debug('Oauth2 response: {}'.format(json.dumps(resp, indent=2)))
        if resp.get("error",0) != 0:
            raise AuthError(resp.get("msg", resp))

        self.auth = resp
        self.auth["appid"] = appid

        return True
        
    async def login(self, username: str, password: str, app=0) -> bool:
        return await super().login(username, password, app)
                
    async def _process_ws_msg(self, data: dict):
        self.logger.debug(f"RECEIVED cloud msg: {self.pprint(data)}")
        await super()._process_ws_msg(data)
        
        #self.logger.debug("Received data: %s" % self.pprint(data))
        deviceid = data.get('deviceid', None)
        self._publish('device', '{}/json'.format(deviceid), json.dumps(data))
                
        if data.get('error', None) is not None:
            if deviceid:
                if data['error'] == 0:
                    self.logger.debug('command completed successfully')
                    self._publish('device', '{}/status'.format(deviceid), "OK")
                else:
                    self.logger.warn('error: %s' % self.pprint(data))
                    self._publish('device', '{}/status'.format(deviceid), "Error: " + data.get('reason','unknown'))
                    self._update_config = False

        if deviceid:
            client = self._get_client(deviceid)
            if client:
                client._handle_notification(data)
    
    def _validate_iso8601(self,str_val):
        try:            
            if self._match_iso8601( str_val ) is not None:
                return True
        except:
            pass
        return False
        
    def _validate_cron(self,str_val):
        try:            
            if self._match_cron( str_val ) is not None:
                return True
        except:
            pass
        return False
    
    def _on_message(self, mosq, obj, msg):
        self.logger.debug("CLIENT: message received topic: %s" % msg.topic)
        #log.info("message topic: %s, value:%s received" % (msg.topic,msg.payload.decode("utf-8")))
        command = msg.topic.split('/')[-1]
        deviceid = msg.topic.split('/')[-2]
        message = msg.payload.decode("utf-8").strip()
        self.logger.info("CLIENT: Received Command: %s, device: %s, Setting: %s" % (command, deviceid, message))
        
        if 'reconnect' in command:
            func = self._reconnect()
        else:
            client = self._get_client(deviceid)
            func = client.q.put((command, message))
               
        #have to use this as mqtt client is running in another thread...
        asyncio.run_coroutine_threadsafe(func,self.loop)
        
    def _publish(self, deviceid, topic, message):
        '''
        mqtt _publish
        '''
        if self._mqttc is None:
            self.logger.debug('No MQTT client configured')
            return
        if deviceid is None:
            return
        elif deviceid == 'client':
            new_topic = self._pub_topic+deviceid+'/'+topic
        elif deviceid == 'device':
            new_topic = self._pub_topic+topic
        else:
            new_topic = topic #new template system passes full topic directly.
        try:
            if isinstance(message, (dict,list)):
                message = json.dumps(message)
            self._mqttc.publish(new_topic, message)
            self.logger.info('published: %s: %s' % (new_topic, message))
        except TypeError as e:
            self.logger.warn('Unable to _publish: %s:%s, %s' % (topic,message,e))
        
    def _create_client_devices(self):
        '''
        Create client devices
        '''
        for device in self._devices:
            found = False
            deviceid = device.get('deviceid', None)
            device_name = device.get('name', None)
            if not deviceid:
                self.logger.error('Device id not found!')
                return

            for device_id, params in self._parameters.items():
                real_deviceid = self.get_deviceid(device_id)
                if real_deviceid == deviceid:
                    initial_parameters = params
                    break
            else:
                initial_parameters = {}
                
            for client_class, productModels in self._device_classes.items():
                for productModel in productModels:
                    if device["productModel"] == productModel:
                        self._clients[deviceid] = client_class(self, deviceid, device, productModel, initial_parameters)
                        self.logger.debug('Created instance of Device: %s, model: %s for: %s (%s)' % (client_class.__name__, productModel, deviceid, device_name))
                        found = True
                        break
                        
            if not found:
                self.logger.warn('Unsupported device: %s, using Default device' % device["productModel"])
                self._clients[deviceid] = Default(self, deviceid, device, device["productModel"], initial_parameters)
                self.logger.debug('Created instance of Device: %s, model: %s for: %s (%s)' % (self._clients[deviceid].__class__.__name__, device["productModel"], deviceid, device_name))
                
        if len(self._clients) == 0:
            self.logger.critical('NO SUPPORTED DEVICES FOUND')

    async def _disconnect(self, send_close=None):
        """Disconnect from Websocket"""
        self.logger.debug('Disconnecting')
        for deviceid, client in self._clients.items():
            if client is not None:
                self.logger.debug('waiting for client %s to exit: %s' % (client,client.deviceid))
                await client.q.put((None,None))
                await client.q.join()
                self._clients[deviceid]=None
        self._publish('client', 'status', "Disconnected")
        await self.stop()
        
    async def _send_request(self, command, waitResponse=False):
        """Send a payload request to websocket"""
        self.logger.debug("Sending command: {}".format(command))
        timeout = 0 if not waitResponse else 5
        return await self.send(command.get('device'), command.get('params'), timeout=timeout)  
        
    async def _sendjson(self, deviceid, message):
        """Send a json payload direct to device"""

        try:
            params = json.loads(message.replace("'",'"'))
            payload = {}
            payload['params'] = params
            payload['device'] = self.get_config(deviceid)
     
            #self.logger.debug('sending JSON: {}'.format(self.pprint(payload)))

            await self._send_request(payload)
            
            if deviceid == patio_door_device['deviceid']:
                await asyncio.sleep(1)
                await self._getparameter(deviceid)
        
        except json.JSONDecodeError as e:
            self.logger.error('json encoding error inmessage: %s: %s' % (message,e))
        
    async def _getparameter(self, sel_device='', params=[], waitResponse=False):
        self._update_config = False
        
        updated = 0
        device_id = None
        
        if sel_device:
            device_id = self.get_deviceid(str(sel_device))
            if not device_id:
                self.logger.error('device %s not found' % sel_device)
                return
        
        for num, device in enumerate(self._devices):
            if not sel_device or device['deviceid'] == device_id:
                updated+=1
                deviceid = device['deviceid']

                self.logger.debug("Getting params: for device [%s]" % (device['name']))

                payload = {}
                payload['device'] = self.get_config(deviceid)

                #self.logger.debug('sending: {}'.format(self.pprint(payload)))

                await self._send_request(payload, waitResponse)
                
        if updated == 0:
            self.logger.warn('device not found: %s' % sel_device)
        
    async def _setparameter(self, sel_device, param, targetState, update_config=True, waitResponse=False):
        '''
        sends either a single parameter to the device, or a dictionary of multiple parameters.
        '''
        #self.logger.debug('PARENT setting parameter: %s, to %s for %s' % (param, targetState, sel_device))
        
        deviceid = self.get_deviceid(sel_device)
        if not deviceid:
            self.logger.error('device %s not found' % sel_device)
            return    

        params = {param:targetState}
            
        self.logger.debug("Setting param: %s to [%s] for device [%s]" % (param, targetState, self.get_devicename(deviceid)))

        payload = {}
        payload['params'] = params
        payload['device'] = self.get_config(deviceid)

        #self.logger.debug('sending: {}'.format(self.pprint(payload)))

        await self._send_request(payload, waitResponse)
        
        if update_config or deviceid == patio_door_device['deviceid']:
            await asyncio.sleep(1)
            self.logger.debug('GETTING parameters for: {}'.format(deviceid))
            await self._getparameter(deviceid)
        
    def get_deviceid(self, sel_device=0):
        deviceid = None
        num_device = -1
        sel_device = str(sel_device)
        if len(sel_device) <= 2 and sel_device.isdigit():    #assume an index number in the range 0-99
            num_device = int(sel_device)
        for num, device in enumerate(self._devices):
            if device['deviceid'] == sel_device or device['name'] == sel_device or num == num_device:
                deviceid = device['deviceid']
                break
        
        return deviceid
        
    def update(self, d, u):
        '''
        Update nested dictionaries
        '''
        for k, v in u.items():
            if isinstance(v, collections.Mapping):
                d[k] = self.update(d.get(k, {}), v)
            else:
                d[k] = v
        return d
        
    def get_devicename(self, deviceid=None):
        client = self._get_client(deviceid)
        return client.name
        
    def _get_client(self, deviceid):
        deviceid = self.get_deviceid(deviceid)
        client = self._clients.get(deviceid, None)
        return client
        
    def send_command(self, deviceid, command, message):
        client = self._get_client(deviceid)
        client.send_command(command, message)
            
    def disconnect(self):
        asyncio.run_coroutine_threadsafe(self._disconnect(),self.loop)
        