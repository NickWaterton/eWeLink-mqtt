#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
see https://github.com/hansharhoff/HASS-sonoff-ewelink for login sequence used
see https://github.com/AlexxIT/SonoffLAN/blob/master/custom_components/sonoff/core/ewelink/cloud.py for new login sequence (10/7/22)
also see https://coolkit-technologies.github.io/eWeLink-API/#/en/DeveloperGuideV2
App ID and secret can be generated/renewed at https://dev.ewelink.cc/#/ when you login (dont forget region), you go to https://dev.ewelink.cc/#/console and click on "View" for your APP.
N. Waterton 13th July 2022 V 2.0.0 Complete re-write based on https://github.com/AlexxIT/SonoffLAN/blob/master/custom_components/sonoff/core/ewelink/cloud.py 
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

import logging
from logging.handlers import RotatingFileHandler
import json, time, sys, hmac, hashlib, base64, collections, re, inspect

import asyncio
from aiohttp import ClientSession, ClientTimeout, ClientConnectorError, WSMessage, ClientWebSocketResponse

from typing import Callable, Dict, List, Optional, TypedDict

from custom_components.sonoff.core.ewelink.__init__ import XRegistry, SIGNAL_ADD_ENTITIES
from custom_components.sonoff.core.ewelink.base import XRegistryBase, XDevice, SIGNAL_UPDATE, SIGNAL_CONNECTED
from custom_components.sonoff.core.ewelink.cloud import XRegistryCloud, AuthError, APP

from ewelink_devices import *
from mqtt import MQTT

_LOGGER = logger = logging.getLogger('Main.'+__name__)

__version__ = '2.0.0'

# appId and secret from https://github.com/skydiver/ewelink-api/blob/master/src/data/constants.js
APP.append(('YzfeftUVcZ6twZw1OoVKPRFYTrGEg01Q', '4G91qSoboqYO4Y0XJ0LPPKIsq8reHdfa'))
# My appId and secret from my AutoslideNet app. can only use with Oauth2 authentication flow, needs to be renewed on 12th July every year
OAUTH = [('tKjp3XDwekm5NROJ0TgfrvpHjGJnrXiq', 'nEu1HrliSwf1TQCqM7j97onLppK0F1LZ')]
                                
class EwelinkClient(MQTT, XRegistryCloud):
    """A websocket client for connecting to ITEAD's devices."""
    
    __version__ = __version__
    
    _ISOregex = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$'
    _cronregex = "{0}\s+{1}\s+{2}\s+{3}\s+{4}".format(  "(?P<minute>\*|[0-5]?\d)",
                                                        "(?P<hour>\*|[01]?\d|2[0-3])",
                                                        "(?P<day>\*|0?[1-9]|[12]\d|3[01])",
                                                        "(?P<month>\*|0?[1-9]|1[012])",
                                                        "(?P<day_of_week>\*|[0-6](\-[0-6])?)"
                                                      )
    
    
    def __init__(self, login=None, passw=None, region='us', log=None, **kwargs):
        self.auth = {'at':''}
        MQTT.__init__(self, log=log, **kwargs)
        self.log = log
        if self.log is None:
            self.log = logging.getLogger('Main.'+__class__.__name__)
        global _LOGGER
        _LOGGER = self.log
        self.log.debug('Started Class: %s, version: %s' % (__class__.__name__,self.__version__))
        self._username = login
        self._passw = passw
        self._region = region
        self._match_iso8601 = re.compile(self._ISOregex).match
        self._match_cron = re.compile(self._cronregex).match
        self._devices = []
        self._clients = {}
        self._parameters = {}  #initial parameters for clients
        self._device_classes = {}
        self._load_devices() 
        self._load_custom_devices()
        self.loop = asyncio.get_event_loop()
        
    def _load_devices(self):
        '''
        Load device classes
        '''
        clsmembers = inspect.getmembers(sys.modules[__name__], inspect.isclass) #get devices loaded from modules
        for dev_class in clsmembers:
            try:
                self._device_classes[dev_class[1]] = dev_class[1].productModel
                self.log.debug('loaded device {}, V:{}, for device models: {}'.format(dev_class[0],dev_class[1].__version__,dev_class[1].productModel))
            except AttributeError:
                pass
                
    def _load_custom_devices(self):
        '''
        load custom devices (in this case autoslide device).
        Put the json output for the device in a file called custom_devices.json, wrapped in a list
        This is optional, you only need it if your custome device isn't picked up automatically
        '''
        try:
            with open('custom_devices.json', 'r') as f:
                self._custom_devices = json.load(f)
                self.log.debug('loaded custom devices: {}'.format(self.pprint(self._custom_devices)))
        except Exception as e:
            #self.log.exception(e)
            self._custom_devices = {}
            
    def _on_connect(self, client, userdata, flags, rc):
        '''
        Override Normal MQTT class on_connect(), to subscribe to correct topic
        '''
        self._log.info('MQTT broker connected')
        self.subscribe('{}/#'.format(self._topic))
        self._history = {}
            
    def pprint(self,obj):
        """Pretty JSON dump of an object."""
        return(json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': ')))
        
    def get_config(self, deviceid = ''):
        return self._get_client(deviceid).config if deviceid else [client.config for client in self._clients.values()]
        
    def set_initial_parameters(self, deviceid, **kwargs):
        '''
        set initial parameters for client
        '''
        self._parameters[deviceid] = kwargs
        
    async def start_connection(self, arg):
        try:
            while True:
                async with ClientSession(timeout=ClientTimeout(total=5.0)) as session:
                    XRegistryCloud.__init__(self, session)
                    self.region = self._region
                    
                    if await self._login(self._username, self._passw, arg.appid, arg.oauth):
                        self.log.debug('Connected: auth: {}'.format(self.pprint(self.auth)))
                        homes = await self.get_homes()
                        self.log.debug('Homes: {}'.format(self.pprint(homes)))
                        if homes:
                            self._devices = await self.get_devices(homes)
                            self.log.debug('Devices: {}'.format(self.pprint(self._devices)))
                            self._add_custom_devices(arg.poll_interval if arg.poll_interval else 60)
                            self._create_client_devices()
                            for device in self._devices:    #initial update
                                client = self._get_client(device['deviceid'])
                                client._handle_notification(device)
                            self.log.info('Starting WS receive - waiting for messages')
                            self.start()
                            if await self._wait_for_WS(5):
                                await self._loop_while_online()
                            else:
                                self.log.error('Unable to connect to WS, retry in 60 seconds')
                    else:
                        self.log.warning('auth: {}'.format(self.pprint(self.auth)))
                        self.log.error('Failed to login, retry in 60 seconds')
                await asyncio.sleep(60)
        
        except Exception as e:
            self.log.exception(e)
        return
        
    def _add_custom_devices(self, poll_interval):
        '''
        Adds custom devices (eg patio Door device) if missing.
        Some appId/secret combinations only list Sonoff devices, but you can still access other devices
        '''
        for custom_device in self._custom_devices:
            if custom_device['deviceid'] not in [device['deviceid'] for device in self._devices]:
                self.log.info('Adding {} to _devices'.format(custom_device.get('name', 'unknown')))
                self._devices.append(XDevice(custom_device))
                self.log.info('Adding {} to polling task'.format(custom_device.get('name', 'unknown')))
                self.set_initial_parameters(custom_device['deviceid'], poll=True)
                self._start_polling(poll_interval)
                    
    def _start_polling(self, poll_interval):
        if 'poll_devices' in self._method_dict.keys():
            if not self._poll:
                self.log.info('Creating polling task, poll every {} seconds'.format(poll_interval))
                self._poll = poll_interval
                self._polling = ['poll_devices']
                self._tasks['_poll_status'] = self._loop.create_task(self._poll_status())
            elif not 'poll_devices' in self._polling:
                self._polling.append('poll_devices')
        else:
            self.log.warning('Unable to poll devices')
            
    async def _wait_for_WS(self, timeout):
        count = 0
        while count <= timeout:
            if self.online:
                return True
            await asyncio.sleep(1)
            count += 1
        return False
        
    async def _loop_while_online(self):
        count = 55
        while self.online:
            count += 1
            if count >= 60:
                self.log.debug('Waiting...')
                count = 0
            await asyncio.sleep(1)
        
    async def _login(self, username: str, password: str, app=0, oauth=False) -> bool:
        if oauth:
            APP.extend(OAUTH)
        self.log.debug('Available App ID, secrets: {}'.format(self.pprint(APP)))
        if arg.appid > len(APP)-1:
            self.log.warning('Selected appId({}) index out of range (max{}), using 0'.format(arg.appid, len(APP)-1))
            arg.appid = 0
        self.log.info('Connecting, login: {}, password: {}, appid({}): {}'.format(username, password, 'Oauth2' if oauth else 'v2', APP[app]))
        if arg.oauth:
            return await self.oauth_login(username, password, app)
        return await self.login(username, password, app)
        
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
        return await XRegistryCloud.login(self, username, password, app)
                
    async def _process_ws_msg(self, data: dict):
        self.log.debug(f"RECEIVED cloud msg: {self.pprint(data)}")
        await XRegistryCloud._process_ws_msg(self, data)
        
        #self.log.debug("Received data: %s" % self.pprint(data))
        deviceid = data.get('deviceid', None)
        if deviceid:
            self._publish(deviceid, 'json', json.dumps(data))

            if data.get('error', None) is not None:
                if data['error'] == 0:
                    self.log.debug('command completed successfully')
                    self._publish(deviceid, 'status', "OK")
                else:
                    self.log.warning('error: %s' % self.pprint(data))
                    self._publish(deviceid, 'status', "Error: " + data.get('reason','unknown'))
                    return

            client = self._get_client(deviceid)
            if client:
                client._handle_notification(data)
    
    def _validate_iso8601(self,str_val):
        try:            
            return True if self._match_iso8601( str_val ) is not None else False
        except:
            pass
        return False
        
    def _validate_cron(self,str_val):
        try:            
            return True if self._match_cron( str_val ) is not None else False  
        except:
            pass
        return False
        
    def _get_command(self, msg):
        '''
        extract command and args from MQTT msg
        '''
        self.log.debug("CLIENT: message received topic: %s" % msg.topic)
        #log.info("message topic: %s, value:%s received" % (msg.topic,msg.payload.decode("utf-8")))
        command = msg.topic.split('/')[-1]
        deviceid = self.get_deviceid(msg.topic.split('/')[-2])
        message = msg.payload.decode("utf-8").strip()
        self.log.info("CLIENT: Received Command: %s, device: %s, Setting: %s" % (command, deviceid, message))
        func = None
        
        if deviceid:
            if 'reconnect' in command:
                if message == 'ON':
                    func = self.disconnect()
            else:
                client = self._get_client(deviceid)
                func = client.q.put((command, message))
                
            #have to use this as mqtt client is running in another thread...
            if func:
                asyncio.run_coroutine_threadsafe(func,self.loop)
            
        return None, None
        
    async def _publish_command(self, command, args=None):
        pass
        
    def _publish(self, deviceid, topic, message):
        '''
        mqtt _publish
        '''
        #self._log.info('MQTT PUBLISH, deviceid: {}, topic: {}, message: {}'.format(deviceid, topic, message))
        if deviceid in topic:
            topic = topic.split('/')[-1]
        MQTT._publish(self, f'{deviceid}/{topic}', message)
        
    def _create_client_devices(self):
        '''
        Create client devices
        '''
        for device in self._devices:
            deviceid = device['deviceid']
            model = device['productModel']
            device_name = device.get('name', None)
                
            initial_parameters = self._parameters.get(deviceid, {})
            
            client_class = [client_class for client_class, productModels in self._device_classes.items() for productModel in productModels if model == productModel]
            if client_class:
                #assign first matching class
                self._clients[deviceid] = client_class[0](self, deviceid, device, model, initial_parameters)          
            else:
                self.log.warning('Unsupported device: {}, using Default device'.format(device["productModel"]))
                self._clients[deviceid] = Default(self, deviceid, device, device["productModel"], initial_parameters)
            self.log.info('Created instance of Device: {}, model: {} for: {} ({})'.format(self._clients[deviceid].__class__.__name__, model, deviceid, device_name))
                
        if len(self._clients) == 0:
            self.log.critical('NO SUPPORTED DEVICES FOUND')
        
    async def poll_devices(self):
        for device in self._devices:
            if self._parameters.get(device['deviceid'], {}).get('poll'):
                self.log.info('Polling device: {}'.format(device['deviceid']))
                await self._getparameter(device['deviceid'])
        return {}   #return dict is expected
        
    async def _send_request(self, command, waitResponse=False):
        """Send a payload request to websocket"""
        self.log.debug("Sending command: {}".format(command))
        timeout = 0 if not waitResponse else 5
        result = await self.send(command.get('device'), command.get('params'), timeout=timeout)
        if result:
            self.log.debug('Send response is: {}'.format(result))
            if result == 'timeout':
                device = command.get('device', {})
                self.log.warning('Device: {}({}) is not updating'.format(device.get('deviceid'), device.get('name')))
        return result
        
    async def _sendjson(self, deviceid, message):
        """Send a json payload direct to device"""
        try:
            params = json.loads(message.replace("'",'"'))
            payload = {'params':params, 'device':self.get_config(deviceid)}
            #self.log.debug('sending JSON: {}'.format(self.pprint(payload)))
            await self._send_request(payload)

        except json.JSONDecodeError as e:
            self.log.error('json encoding error inmessage: %s: %s' % (message,e))
        
    async def _getparameter(self, device_id='', params=[], waitResponse=False):
        deviceid = self.get_deviceid(str(device_id))
        if deviceid:
            self.log.debug('Getting params: for device [{}]'.format(self.get_devicename(deviceid)))
            payload = {'device':self.get_config(deviceid)}
            await self._send_request(payload, waitResponse)
        else:
            self.log.error(f'device {device_id} not found')
        
    async def _setparameter(self, device_id, param, targetState, update_config=True, waitResponse=False):
        '''
        sends either a single parameter to the device, or a dictionary of multiple parameters.
        '''
        deviceid = self.get_deviceid(device_id)   
        if deviceid:
            params = {param:targetState}
                
            self.log.debug('Setting param: {} to [{}] for device [{}]'.format(param, targetState, self.get_devicename(deviceid)))
            waitResponse = True if deviceid == patio_door_device['deviceid'] else waitResponse

            payload = {'params':params, 'device':self.get_config(deviceid)}
            await self._send_request(payload, waitResponse)
        else:
            self.log.error(f'device {device_id} not found')
        
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
            if isinstance(v, collections.abc.Mapping):
                d[k] = self.update(d.get(k, {}), v)
            else:
                d[k] = v
        return d
        
    def get_devicename(self, deviceid=None):
        return self._get_client(deviceid).name
        
    def _get_client(self, deviceid):
        deviceid = self.get_deviceid(deviceid)
        return self._clients.get(deviceid, None)
        
    def send_command(self, deviceid, command, message):
        '''
        Only used for command line (API) options, not strictly necessary if only mqtt is used, but uses the same format as mqtt
        '''
        self._get_client(deviceid).send_command(command, message)
        
    async def _disconnect(self, send_close=None):
        """Disconnect from Websocket and delete clients"""
        self.log.debug('Disconnecting')
        for deviceid, client in self._clients.items():
            if client is not None:
                #self.log.debug('waiting for client %s to exit: %s' % (client,client.deviceid))
                await client.q.put((None,None))
                await client.q.join()
                self._clients.pop(deviceid, None)
        self._publish('client', 'status', "Disconnected")
        await self.stop()
        await self.ws.close()
        self.log.info('Disconnected')
            
    def disconnect(self):
        asyncio.run_coroutine_threadsafe(self._disconnect(),self.loop)
        
def parse_args():
    
    #-------- Command Line -----------------
    parser = argparse.ArgumentParser(
        description='Forward MQTT data to Ewelink API')
    parser.add_argument(
        'login',
        action='store',
        type=str,
        default=None,
        help='Ewelink login (e-mail or phone number) (default: %(default)s)')
    parser.add_argument(
        'password',
        action='store',
        type=str,
        default=None,
        help='Ewelink password (default: %(default)s)')
    parser.add_argument(
        '-r', '--region',
        action='store',
        type=str,
        choices=['us', 'cn', 'eu', 'as'],
        default='us',
        help='Region (default: %(default)s)')
    parser.add_argument(
        '-a', '--appid',
        action='store',
        type=int,
        default=0,
        help='AppID to use (default: %(default)s)')
    parser.add_argument(
        '-O', '--oauth',
        action='store_true',
        default = False,
        help='Use Oauth2 login (vs v2 login) (default: %(default)s)')
    parser.add_argument(
        '-t', '--topic',
        action='store',
        type=str,
        default="/ewelink_command/",
        help='MQTT Topic to send commands to, (can use # '
             'and +) default: %(default)s)')
    parser.add_argument(
        '-T', '--feedback',
        action='store',
        type=str,
        default="/ewelink_status",
        help='Topic on broker to publish feedback to (default: '
             '%(default)s)')
    parser.add_argument(
        '-b', '--broker',
        action='store',
        type=str,
        default=None,
        help='ipaddress of MQTT broker (default: %(default)s)')
    parser.add_argument(
        '-p', '--port',
        action='store',
        type=int,
        default=1883,
        help='MQTT broker port number (default: %(default)s)')
    parser.add_argument(
        '-U', '--user',
        action='store',
        type=str,
        default=None,
        help='MQTT broker user name (default: %(default)s)')
    parser.add_argument(
        '-P', '--passwd',
        action='store',
        type=str,
        default=None,
        help='MQTT broker password (default: %(default)s)')
    parser.add_argument(
        '-poll', '--poll_interval',
        action='store',
        type=int,
        default=0,
        help='Polling interval (seconds) (0=off) (default: %(default)s)')
    parser.add_argument(
        '-pd', '--poll_device',
        nargs='*',
        action='store',
        type=str,
        default=None,
        help='Poll deviceID (default: %(default)s)')
    parser.add_argument(
        '-d', '--device',
        action='store',
        type=str,
        default='100050a4f3',
        help='deviceID (default: %(default)s)')
    parser.add_argument(
        '-dp', '--delay_person',
        action='store',
        type=int,
        default=None,
        help='Delay in seconds for person trigger (default: %(default)s)')
    parser.add_argument(
        '-l', '--log',
        action='store',
        type=str,
        default="./ewelink.log",
        help='path/name of log file (default: %(default)s)')
    parser.add_argument(
        '-J', '--json_out',
        action='store_true',
        default = False,
        help='publish topics as json (vs individual topics) (default: %(default)s)')
    parser.add_argument(
        '-D', '--debug',
        action='store_true',
        default = False,
        help='debug mode')
    parser.add_argument(
        '--version',
        action='version',
        version="%(prog)s ({})".format(__version__),
        help='Display version of this program')
    return parser.parse_args()
    
def setuplogger(logger_name, log_file, level=logging.DEBUG, console=False):
    try: 
        l = logging.getLogger(logger_name)
        formatter = logging.Formatter('[%(asctime)s][%(levelname)5.5s](%(name)-20s) %(message)s')
        if log_file is not None:
            fileHandler = logging.handlers.RotatingFileHandler(log_file, mode='a', maxBytes=10000000, backupCount=10)
            fileHandler.setFormatter(formatter)
        if console == True:
            #formatter = logging.Formatter('[%(levelname)1.1s %(name)-20s] %(message)s')
            streamHandler = logging.StreamHandler()
            streamHandler.setFormatter(formatter)

        l.setLevel(level)
        if log_file is not None:
            l.addHandler(fileHandler)
        if console == True:
          l.addHandler(streamHandler)
             
    except Exception as e:
        print("Error in Logging setup: %s - do you have permission to write the log file??" % e)
        sys.exit(1)
            
if __name__ == "__main__":
    import argparse
    arg = parse_args()
    
    if arg.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    #setup logging
    log_name = 'Main'
    setuplogger(log_name, arg.log, level=log_level,console=True)

    log = logging.getLogger(log_name)

    log.info("*******************")
    log.info("* Program Started *")
    log.info("*******************")
    
    log.debug('Debug Mode')

    log.info("{} Version: {}".format(sys.argv[0], __version__))

    log.info("Python Version: {}".format(sys.version.replace('\n','')))
    
    poll = None
    if arg.poll_interval and arg.poll_device:
        log.info(f'Polling {arg.poll_device} every {arg.poll_interval}s')
        poll = (arg.poll_interval, 'poll_devices')
    
    loop = asyncio.get_event_loop()
    loop.set_debug(arg.debug)
    try:
        if arg.broker:
            r = EwelinkClient(  arg.login,
                                arg.password,
                                arg.region,
                                ip=arg.broker,
                                port=arg.port,
                                user=arg.user,
                                password=arg.passwd,
                                pubtopic=arg.feedback,
                                topic=arg.topic,
                                name=None,
                                poll=poll,
                                json_out=arg.json_out,
                                #log=log
                                )
            if arg.device:
                r.set_initial_parameters(arg.device, delay_person=arg.delay_person)
            if poll:
                for device in arg.poll_device:
                    r.set_initial_parameters(device, poll=True)
            asyncio.gather(r.start_connection(arg), return_exceptions=True)
            loop.run_forever()
        else:
            r = EwelinkClient(arg.login, arg.password, arg.region, log=log)
            if arg.device:
                r.set_initial_parameters(arg.device, delay_person=arg.delay_person)
            if poll:
                for device in arg.poll_device:
                    r.set_initial_parameters(device, poll=True)
            log.info(loop.run_until_complete(r.start_connection(arg)))
            
    except (KeyboardInterrupt, SystemExit):
        log.info("System exit Received - Exiting program")
        if arg.broker:
            r.disconnect()
        
    finally:
        pass

        