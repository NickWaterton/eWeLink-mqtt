#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
N Waterton 11th Jan 2019 V1.0 First release
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

import json
import asyncio
import websockets
from aiohttp import ClientSession
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

logger = logging.getLogger('Main.'+__name__)

__version__ = '1.1'

class EwelinkClient():
    """A websocket client for connecting to ITEAD's devices."""

    __version__ = '1.0'

    _ISOregex = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$'
    _cronregex = "{0}\s+{1}\s+{2}\s+{3}\s+{4}".format(  "(?P<minute>\*|[0-5]?\d)",
                                                        "(?P<hour>\*|[01]?\d|2[0-3])",
                                                        "(?P<day>\*|0?[1-9]|[12]\d|3[01])",
                                                        "(?P<month>\*|0?[1-9]|1[012])",
                                                        "(?P<day_of_week>\*|[0-6](\-[0-6])?)"
                                                      )

    def __init__(self, phoneNumber=None,email=None,password=None, imei='01234567-89AB-CDEF-0123-456789ABCDEF', loop=None, mqttc=None, pub_topic='/ewelink_status/', configuration_file=None):
        self.logger = logging.getLogger('Main.'+__class__.__name__)
        self.logger.debug('Started Class: %s, version: %s' % (__class__.__name__,self.__version__))
        self.wsc_url = None
        self.apikey = 'UNCONFIGURED'
        self.authenticationToken = 'UNCONFIGURED'
        # self.apiHost = 'us-api.coolkit.cc:8080'
        # self.webSocketApi = 'us-pconnect3.coolkit.cc'
        self.apiHost = 'eu-api.coolkit.cc:8080'
        self.webSocketApi = 'eu-pconnect3.coolkit.cc'

        self._nonce = ''.join([str(random.randint(0, 9)) for i in range(8)])
        self._sequence = int(time.time()*1000)
        self.connected = False

        self._match_iso8601 = re.compile(self._ISOregex).match
        self._match_cron = re.compile(self._cronregex).match

        self._websocket = None
        self._disconnecting = False
        self._recconect_connection = False
        self._ping_timeout = None
        self._keepalive_task = None
        self._received_sequence = ''
        self._devices = []
        self._clients = {}
        self._parameters = {}  #initial parameters for clients
        self._update_config = True
        self._timeout = 0
        self._version = '6'
        self._os = 'iOS'
        self._appid = 'oeVkj2lYFGnJu5XUtWisfW4utiN4u9Mq'
        self._model         = 'iPhone' + random.choice(['6,1', '6,2', '7,1', '7,2', '8,1', '8,2', '8,4', '9,1', '9,2', '9,3', '9,4', '10,1', '10,2', '10,3', '10,4', '10,5', '10,6', '11,2', '11,4', '11,6', '11,8'])
        self._romVersion    = random.choice([
            '10.0', '10.0.2', '10.0.3', '10.1', '10.1.1', '10.2', '10.2.1', '10.3', '10.3.1', '10.3.2', '10.3.3', '10.3.4',
            '11.0', '11.0.1', '11.0.2', '11.0.3', '11.1', '11.1.1', '11.1.2', '11.2', '11.2.1', '11.2.2', '11.2.3', '11.2.4', '11.2.5', '11.2.6', '11.3', '11.3.1', '11.4', '11.4.1',
            '12.0', '12.0.1', '12.1', '12.1.1', '12.1.2', '12.1.3', '12.1.4', '12.2', '12.3', '12.3.1', '12.3.2', '12.4', '12.4.1', '12.4.2',
            '13.0', '13.1', '13.1.1', '13.1.2', '13.2'
        ])
        self._appVersion    = random.choice(['3.5.3', '3.5.4', '3.5.6', '3.5.8', '3.5.10', '3.5.12', '3.6.0', '3.6.1', '3.7.0', '3.8.0', '3.9.0', '3.9.1', '3.10.0', '3.11.0', '3.12.0'])

        #client initialization parameters
        self._configuration = {}
        self._phoneNumber, self._email, self._password, self._imei, self._pub_topic = self.get_initialization_parameters(configuration_file, phoneNumber, email, password, imei, pub_topic)

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

    def get_initialization_parameters(self, file, phoneNumber, email, password, imei, pub_topic):
        if imei is None:
            imei = str(uuid.uuid4())
        if file:
            if self.load_config(file):
                my_phoneNumber = self._configuration['log_in'].get('phoneNumber', phoneNumber)
                my_email       = self._configuration['log_in'].get('email',email)
                my_password    = self._configuration['log_in'].get('password',password)
                my_imei        = self._configuration['log_in'].get('imei',imei)
                my_pub_topic   = self._configuration['mqtt'].get('pub_topic',pub_topic)

                if my_phoneNumber is None:
                    my_phoneNumber = phoneNumber
                if my_email is None:
                    my_email = email
                if my_password is None:
                    my_password = password
                if my_imei is None:
                    my_imei = imei
                if my_pub_topic is None:
                    my_pub_topic = pub_topic

                return my_phoneNumber, my_email, my_password, my_imei, my_pub_topic

        return phoneNumber, email, password, imei, pub_topic

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
    def sequence(self):
        self._sequence = int(time.time()*1000)
        return str(self._sequence)

    @property
    def timestamp(self):
        return int(time.time())

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

    async def login(self):
        #if (not self._phoneNumber and not self._email) or not self._password or not self._imei:
        #    self.logger.error('phoneNumber / email / password / imei not entered, exiting')
        #    self._publish('status', "Offline")
        #    return
        self._publish('client', 'status', "Starting")

        data = {}
        if self._phoneNumber:
            data['phoneNumber'] = self._phoneNumber
        elif self._email:
            data['email'] = self._email

        data['password'] = self._password
        data['version'] = self._version
        data['ts'] = self.timestamp
        data['_nonce'] = self._nonce
        data['appid'] = self._appid
        data['imei'] = self._imei
        data['os'] = self._os
        data['model'] = self._model
        data['romVersion'] = self._romVersion
        data['appVersion'] = self._appVersion

        json_data = json.dumps(data)
        self.logger.debug('Sending login request with user credentials: %s' % json_data)

        decryptedAppSecret = '6Nz4n0xA8s8qdxQf2GqurZj2Fs55FUvM'
        hmac_result = hmac.new(decryptedAppSecret.encode('utf-8'), json_data.encode('utf-8'), hashlib.sha256)
        sign = base64.b64encode(hmac_result.digest()).decode('utf-8')

        self.logger.debug('Login signature: %s', sign)
        self.logger.debug('Login data: %s', json_data)

        """Retrieve the ewelink information."""
        self.logger.debug("Retrieving ewelink information.")
        url = 'https://{}/api/user/login'.format(self.apiHost)
        headers = {
            'Authorization': 'Sign %s' % sign,
            'Content-Type': 'application/json;charset=UTF-8',
        }
        json_request = json.loads(json_data)

        self.logger.debug('url: %s, headers: %s, data: %s' % (url, headers,json_request))
        async with ClientSession() as session:
            async with session.post(url, json=json_request, headers=headers) as response:
                json_response = await response.json()

            # If we receive 301 error, switch to new region and try again (untested...)
            self.logger.debug('received response status: %s' %  response.status)
            self.logger.debug('received response: %s' %  self.pprint(json_response))
            if response.status == 301:
                if json_response.get('error', None) or json_response.get('region', None):
                    if '-' not in self.apiHost:
                        self.logger.debug("Received new region [%s]. However we cannot construct the new API host url." % json_response.get('region', None))
                        return
                newApiHost = json_response.get('region', '') + self.apiHost.split('-')[1]
                if self.apiHost != newApiHost:
                    self.logger.debug("Received new region [%s], updating API host to [%s]." % (json_response['region'], newApiHost))
                    self.apiHost = newApiHost
                    self.login()
                    #return
            elif response.status == 200:
                if json_response.get('error',None):
                    self.logger.error('login error: %d, :%s' %(json_response['error'], json_response['info']))
                    return
            '''
            Example good Response:
            received response: {
              "at": "bxxxdd05065xxxxxxxe71989xxxxx4becad64",
              "region": "us",
              "rt": "d5bxxx86c5axxe62xxx1856fc1bexxxd9f5",
              "user": {
                "_id": "5xx6fbxxx9bxxx82xxxx353a2",
                "apikey": "530303a6-cf2c-4246-894c-xxxxxxxxxxxx",
                "appId": "SFjcK1b2tlVMIXIa8G61irex6aBkr7MN",
                "createdAt": "2018-11-10T15:40:47.101Z",
                "email": "e-mail@gmail.com",
                "ip": "xxx.xx.xx.xxx",
                "lang": "en",
                "location": "",
                "offlineTime": "2018-12-31T15:32:02.787Z",
                "online": false,
                "onlineTime": "2018-12-31T15:31:57.323Z",
                "userStatus": "2"
              }
            }
                '''
        self.apikey = json_response['user']['apikey']
        self.logger.debug('Authentication token received [%s]', json_response['at']);
        self.authenticationToken = json_response['at']
        await self.get_device_list()
        await self._getWebSocketHost()

    async def _getWebSocketHost(self):
        data = {}
        data['accept'] = 'mqtt,ws'
        data['version'] = self._version
        data['ts'] = self.timestamp
        data['_nonce'] = self._nonce
        data['appid'] = self._appid
        data['imei'] = self._imei
        data['os'] = self._os
        data['model'] = self._model
        data['romVersion'] = self._romVersion
        data['appVersion'] = self._appVersion

        json_data = json.dumps(data)
        self.logger.debug('sending get websocket host data: %s' % json_data)

        """Retrieve the ewelink websocket information."""
        self.logger.debug("Retrieving ewelink websocket information.")
        url = 'https://{}/dispatch/app'.format(self.apiHost.replace('-api', '-disp'))
        headers = {
            'Authorization': 'Bearer %s' % self.authenticationToken,
            'Content-Type': 'application/json;charset=UTF-8',
        }
        json_request = json.loads(json_data)

        self.logger.debug('url: %s, headers: %s, data: %s' % (url, headers,json_request))
        async with ClientSession() as session:
            async with session.post(url, json=json_request, headers=headers) as response:
                json_response = await response.json()

            self.logger.debug('received response status: %s' %  response.status)
            self.logger.debug('received response: %s' %  self.pprint(json_response))
            if response.status != 200:
                self.logger.error('error: %s received' % response.status)
                return
            if not json_response.get('domain', None):
                self.logger.error('Server did not response with a websocket host. Response was [%s]' % json_response)
                return
        self.logger.debug('WebSocket host received [%s]', json_response['domain'])
        self.webSocketApi = json_response['domain']
        self.wsc_url = 'wss://{}:{}/api/ws'.format(json_response['domain'], json_response['port'])
        self.logger.debug('Websockets api host: %s' % self.wsc_url)
        await self.connect()

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
        #new_topic = self._pub_topic+deviceid+'/'+topic
        new_topic = topic
        try:
            if isinstance(message, (dict,list)):
                message = json.dumps(message)
            self._mqttc.publish(new_topic, message)
            self.logger.info('published: %s: %s' % (new_topic, message))
        except TypeError as e:
            self.logger.warn('Unable to _publish: %s:%s, %s' % (topic,message,e))

    async def get_device_list(self):
        """Retrieve the device information. returns a list of devices (may be just 1)"""
        self.logger.debug("Retrieving device list information.")
        #url = 'https://{}/api/user/device'.format(self.apiHost)    #suddenly stopped worrking, so use
        '''
        #full version
        url = 'https://{}/api/user/device?lang=en&apiKey={}&getTags=1&version={}&ts={}&nonce={}&appid={}&imei={}&os={}&model={}&romVersion={}&appVersion={}'.format(self.apiHost,
                                                                                                                                                                    self.apikey,
                                                                                                                                                                    self.timestamp,
                                                                                                                                                                    self._version,
                                                                                                                                                                    self._nonce,
                                                                                                                                                                    self._appid,
                                                                                                                                                                    self._imei,
                                                                                                                                                                    self._os,
                                                                                                                                                                    self._model,
                                                                                                                                                                    self._romVersion,
                                                                                                                                                                    self._appVersion)
        '''
        url = 'https://{}/api/user/device?version={}&appid={}'.format(self.apiHost, self._version, self._appid)
        headers = {
            'Authorization': 'Bearer %s' % self.authenticationToken,
        }
        self.logger.debug('url: %s, headers: %s' % (url, headers))
        async with ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                json_response = await response.json()

            self.logger.debug('received response status: %s' %  response.status)
            self.logger.debug('received response: %s' %  self.pprint(json_response))
            if response.status != 200:
                self.logger.error('error: %s received' % response.status)
                return

        if json_response.get("devicelist"):
            self.logger.info('New response format found')
            json_response = json_response["devicelist"]

        self.logger.debug('number of device(s) is: %d' % len(json_response))

        self._devices = json_response   #list of devices and current configurations

        self._create_client_devices()

        '''
        Example Response:
         [
          {
            "__v": 0,
            "_id": "5becffa6d2b4a3c34cb79b38",
            "apikey": "530303a6-cf2c-4246-894c-xxxxxxxxxxx",
            "brandName": "AUTOSLIDE",
            "createdAt": "2018-11-15T05:09:58.341Z",
            "deviceStatus": "",
            "deviceUrl": "",
            "deviceid": "100050xxxxx",
            "devicekey": "4123ec79-d2c3-4d32-930a-xxxxxxxxxxxxx",
            "extra": {
              "_id": "xxxxxxxxxxxxxxxx",
              "extra": {
                "apmac": "xx:xx:xx:xx:xx:xx",
                "brandId": "5a6fcf00f620073c67efc280",
                "description": "20180813001",
                "mac": "xx:xx:xx0:xx:xx:xx",
                "manufacturer": "\u9752\u5c9b\u6fb3\u601d\u5fb7\u667a\u80fd\u95e8\u63a7\u7cfb\u7edf\u6709\u9650\u516c\u53f8",
                "model": "PSA-BTA-GL",
                "modelInfo": "5af3f5332c8642b001540dac",
                "ui": "\u63a8\u62c9\u5ba0\u7269\u95e8",
                "uiid": 54
              }
            },
            "group": "",
            "groups": [],
            "ip": "xxx.xx.xx.xxx",
            "location": "",
            "name": "Patio Door",
            "offlineTime": "2018-12-31T07:23:31.018Z",
            "online": true,
            "onlineTime": "2018-12-31T12:19:33.216Z",
            "params": {
              "a": "3",
              "b": "3",
              "c": "1",
              "d": "1",
              "e": "1",
              "f": "1",
              "fwVersion": "2.0.2",
              "g": "0",
              "h": "1",
              "i": "0",
              "j": "00",
              "k": "0",
              "l": "1",
              "m": "2",
              "n": "0",
              "rssi": -53,
              "staMac": "xx:xx:xx:xx:xx:xx"
            },
            "productModel": "WFA-1",
            "settings": {
              "alarmNotify": 1,
              "opsHistory": 1,
              "opsNotify": 0
            },
            "sharedTo": [
              {
                "note": "",
                "permit": 15,
                "phoneNumber": "e-mail@gmail.com",
                "shareTime": 1542259546087
              }
            ],
            "showBrand": true,
            "type": "10",
            "uiid": 54
          }
        ]

        or New format:
        {
          "devicelist": [
            {
              "__v": 0,
              "_id": "5c3665d012d28ae6ba4943c8",
              "apikey": "530303a6-cf2c-4246-894c-50855b00e6d8",
              "brandLogoUrl": "https://us-ota.coolkit.cc/logo/KRZ54OifuGmjoEMxT1YYM3Ybu2fj5K2C.png",
              "brandName": "Sonoff",
              "createdAt": "2019-01-09T21:21:20.402Z",
              "devConfig": {},
              "devGroups": [],
              "deviceStatus": "",
        ... as before
        '''

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


    async def _keepalive(self):
        self.logger.debug('starting keepalive task with timeout of %ss' % self._ping_timeout)
        while self._ping_timeout and self._websocket.open:
            try:
                await asyncio.sleep(self._ping_timeout)
                await self._send_request('ping')
            except asyncio.CancelledError:
                break
        self.logger.debug('exited keepalive loop')

    async def _perform_connect(self):
        """Connect to Hub Web Socket"""
        # Return connected if we are already connected.
        if self._websocket:
            if self._websocket.open:
                return True

        self.logger.debug("Starting connect.")

        self.logger.debug("Connecting to %s" % self.wsc_url)
        self._websocket = await websockets.connect(self.wsc_url)

        #We need to authenticate upon opening the connection
        payload = {}

        payload['action'] = "userOnline"
        payload['userAgent'] = 'app'
        payload['version'] = 6
        payload['_nonce'] = self._nonce
        #payload['apkVesrion'] = "1.8"
        payload['apkVersion'] = "1.8"
        payload['os'] = 'ios'
        payload['at'] = self.authenticationToken
        payload['apikey'] = self.apikey
        payload['ts'] = self.timestamp
        payload['model'] = 'iPhone10,6'
        payload['romVersion'] = '11.1.2'
        payload['sequence'] = self.sequence

        string = json.dumps(payload);

        self.logger.debug('Sending login request [%s]' % string);

        await self._send_request(string)

    async def connect(self):
        """Connect to Hub Web Socket"""
        await self._perform_connect()

        self.logger.debug("ewelink Connected")
        self._publish('client', 'status', "Connected")
        self._disconnecting = False

        await self._receive_loop()

    async def _receive_loop(self):
        while self._websocket.open:
            try:
                self.logger.debug('waiting for data')

                response_json = await self._websocket.recv()
                #self.logger.debug("Received text data: %s", response_json)
                if response_json == 'pong':
                    self.logger.debug('Received Pong')
                    pass    #ignore _keepalive
                else:
                    response = json.loads(response_json)
                    self.logger.debug("Received data: %s" % self.pprint(response))
                    deviceid = response.get('deviceid', None)
                    self._publish(deviceid, 'json', response_json)
                    if response.get('config', None):
                        if response['config'].get('hb',0) == 1:
                            self._ping_timeout = response['config'].get('hbInterval', None)
                            self.logger.debug('setting keepalive timeout to %s' % self._ping_timeout)
                            self._keepalive_task = self.loop.create_task(self._keepalive())

                    if response.get('error', None) is not None:
                        self._received_sequence = response.get('sequence', None)
                        self.logger.debug('received sequence: %s, sent sequence: %s' % (self._received_sequence, self._sequence))
                        if deviceid:
                            if response['error'] == 0:
                                self.logger.debug('command completed successfully')
                                self._publish(deviceid, 'status', "OK")
                            else:
                                self.logger.warn('error: %s' % self.pprint(response))
                                self._publish(deviceid, 'status', "Error: " + response.get('reason','unknown'))
                                self._update_config = False

                    if deviceid:
                        client = self._get_client(deviceid)
                        if client:
                            client._handle_notification(response)
                        self.connected = True

                if self._update_config:
                    self._update_config = False
                    await self._getparameter(deviceid)

            except websockets.exceptions.ConnectionClosed:
                self.logger.debug('WS connection closed')
                break

            except Exception as e:
                self.logger.exception(e)
                break

        await self._disconnect()
        self.logger.debug('Exited Receive Loop')

        if self._recconect_connection:
            self._recconect_connection = False
            await self.connect()

    async def _disconnect(self, send_close=None):
        """Disconnect from Websocket"""
        if self._disconnecting: #if we are already disconnecting
            return
        self.logger.debug('Disconnecting')
        self._disconnecting = True
        self._recconect_connection = False
        for deviceid, client in self._clients.items():
            if client is not None:
                #self.logger.debug('waiting for client %s to exit: %s' % (client,client.deviceid))
                await client.q.put((None,None))
                await client.q.join()
                self._clients[deviceid]=None

        self._ping_timeout = None
        if self._keepalive_task:
            self._keepalive_task.cancel()
        if self._websocket:
            await self._websocket.close()
        self._websocket = None
        self.connected = False
        self._publish('client', 'status', "Disconnected")

    async def _reconnect(self):
        self._publish('client', 'status', "Reconnecting")
        self._disconnecting = True
        self._recconect_connection = True
        self._ping_timeout = None
        if self._keepalive_task:
            self._keepalive_task.cancel()
        await self._websocket.close()
        self.logger.debug('Reconnecting')

    async def _send_request(self, command, waitResponse=False):
        """Send a payload request to websocket"""
        # Make sure we're connected.
        await self._perform_connect()

        while self._timeout > 0:
            self.logger.debug('waiting for previous command response')
            await asyncio.sleep(1)

        self.logger.debug("Sending command: %s", command)
        await self._websocket.send(command)
        if waitResponse and self.connected:
            while (int(self._received_sequence) < int(self._sequence)) and self._timeout < 5:
                self._timeout += 1
                self.logger.debug('waiting for response sequence: %s, current sequence: %s' % (self._sequence,self._received_sequence))
                await asyncio.sleep(1)
            self._timeout = 0

    async def _sendjson(self, deviceid, message):
        """Send a json payload direct to device"""

        try:
            params = json.loads(message.replace("'",'"'))
            payload = {}
            payload['action'] = 'update'
            payload['userAgent'] = 'app'
            payload['from'] = 'app'
            payload['params'] = params
            payload['apikey'] = self.apikey
            #payload['selfApiKey'] = self.apikey    #this is the apikey of the owner (to show that you are the owner)
            payload['deviceid'] = deviceid
            payload['ts'] = self.timestamp
            payload['sequence'] = self.sequence

            string = json.dumps(payload)
            self.logger.debug('sending: %s' %  self.pprint(payload))

            await self._send_request(string)

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
                payload['action'] = 'query'
                payload['userAgent'] = 'app'
                payload['from'] = 'app'
                #payload['value'] = 'params' #in theory you can also use payload['params'] = [] where you can include a list of the params you want ([] means all params)
                payload['params'] = params
                payload['ts'] = self.timestamp
                payload['apikey'] = self.apikey
                payload['deviceid'] = deviceid
                payload['sequence'] = self.sequence

                string = json.dumps(payload);
                self.logger.debug('sending: %s' %  self.pprint(payload) )

                await self._send_request(string, waitResponse)

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

        #sequence and selfApiKey are optional...

        payload = {}
        payload['action'] = 'update'
        payload['userAgent'] = 'app'
        payload['from'] = 'app'
        payload['params'] = params
        payload['apikey'] = self.apikey
        #payload['selfApiKey'] = self.apikey #according to https://github.com/CoolKit-Technologies/open-coolkit-android/blob/master/doc/sdk_Reference_draft.pdf indicates if you are the owner
        payload['deviceid'] = deviceid
        payload['ts'] = self.timestamp
        payload['sequence'] = self.sequence

        string = json.dumps(payload);
        self.logger.debug('sending: %s' %  self.pprint(payload) )

        await self._send_request(string, waitResponse)

        if update_config:
            await asyncio.sleep(1)
            self._update_config = True

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
