#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Client class for connecting to Sonoff Device."""

'''
Explanation of how Autoslide works:
The Autoslide door has a new WiFi interface, which is produced by iTEAD, using there eWelink technology and IoTgo platform.
This is the same technology as used in their sonoff devices, so we can learn a lot from the common sonoff device usage.

Assuming you can get the Autoslide WiFi module to connect to your WiFi network (I had trouble, and had to use the
eWelink app in "legacy" mode to get it to connect), you should be able to register the device using the Autoslide app
(or the eWelink app - both work, for registration).

Once you have control using the Autoslide app, you can now use this client for connecting and controlling your
Autoslide doors via MQTT, or command line.

NOTE: You often get a strange situation where you can send commands to the Autoslide (and they work), but you receive
nothing back but a Timeout message. The client message you get is shown below:

Received data: {
  "apikey": "530303a6-cf2c-4246-894c-50855b00e6d8",
  "deviceid": "100050a4f3",
  "error": 504,
  "reason": "Request Timeout",
  "sequence": "3"
}

This seems to be something to do with iTEAD's servers. You can get connection back by power cycling the Autoslide,
and reconnecting the app/client.

Power cycling the Autoslide reconnects the Autoslide's websocket client to iTEAD's servers, so you can pick up again (if you are still connected).

Do not hit the servers with too many commands too quickly, max is about 1 per second. You will get Timeouts if you send commands too quickly.

command line options:
client.get_config()
client.set_mode(mode, device=0)
client.trigger_door(trigger, device=0)
client.set_option(option, value, device=0)

where mode is a number (0=auto, 1=stacker, 2=lock, 3=pet)
      trigger is a number (stack=4, pet=3, outdoor=1, indoor=2, none=0)
      option is a letter (or descriptor)    'a':'mode',         #0=auto, 1=stacker, 2=lock, 3=pet
                                            'd':'unknown',
                                            'e':'75%_power',    #(0=ON)
                                            'f':'slam_shut',    #(0=ON)
                                            'g':'unknown',
                                            'h':'heavy_door',   #(0=ON)
                                            'i':'stacker_mode', #(0=ON)
                                            'j':'door_delay',   #(in seconds)
                                            'k':'unknown',
                                            'l':'notifications' #(0=ON
      value is a number 0=ON, 1=OFF, or for delay a number in seconds.
      device is either an index number (device 0,1,2 etc), a deviceid (as given by get_config), or the device description you assigned in the Autoslide app (eg "Patio Door")
      default device is '0', so if you only have one ewelink device, you can leave device out.
      eWelink devices include sonoff switches and other iTEAD devices, so if you have an Autoslide, and other iTEAD devises, you have more then one device, so you need to
      specify the Autoslide device

If you do supply an asyncio loop, you will need to start the loop, with the client.login() - like this:
loop.run_until_complete(client.login())

You can then control the door by publishing to the mqtt topics.
Examples:
mosquitto_pub -t "/ewelink_command/10005d73ab/door_trigger" -m "3"
mosquitto_pub -t "/ewelink_command/10005d73ab/set_mode" -m "3"
      
The actual configuration of all this is gleaned from web sources on the sonoff ewelink protocol, and reverse engineering the data.
I have no engineering documents to go on, so some of the parameters are a best guess as to what they do.

please update me if you have better information, or find out what the 'unknown' parameters are/do. One of them is probably for right hand door vs left hand door,
but I don't know which, and I don't want to mess with my working door to find out.
      
Nick Waterton P.Eng.

'''

import asyncio
import time
import json
import datetime
from jinja2 import Environment, BaseLoader
from MsgTemplate import MsgTemplate

import logging

logger = logging.getLogger('Main.'+__name__)

class Default():
    """ An eweclient class for connecting to unknown devices
        Also used as the base class for a device, just override the sections that are not default for your new device.
        To use this you can publish to /ewelink_command/deviceid/set_<param> <value> (or just <param>) via mqtt, or use the 
        command line option client.send_command(deviceid, command='set_<param>, value=<value>) or
        just client.send_command(deviceid, command=<param>, value=<value>)
        You can also send json using set_json (mqtt or command line).
        deviceid can be the actual device id, or the device name (eg. "Patio Door", "Switch 1" etc.)
        subscribing to /ewelink_status/# will show all the parameters published
        There are some special commands:
        set_switch <on or off>
        set_led <on or off>
        set_json <json string>
        delete_timers
        get_config
        that work on most devices (possibly not all).
        Example:
        mosquitto_pub -t "/ewelink_command/10003a430d/set_switch" -m "off"
        mosquitto_pub -t "/ewelink_command/Switch 1 POW/set_switch" -m "on"
        mosquitto_pub -t "/ewelink_command/Switch 1 POW/get_config" -m ""
    """
    
    productModel    = ["Default"]   #model list used for identifying the correct class
    
    device_type = 'switch'  #device type for template rendering
    
    triggers        =[  ]                           #things used to trigger device eg 'switch'
    settings        ={  }                           #(read/write options) #if you don't fill this in, it will be autopopulated, but won't show params that don't exist yet
    other_params    ={  "fwVersion": "fwVersion",   #(read only stuff)
                        "rssi": "rssi",
                        "staMac": "staMac"
                     }
                     
    numerical_params=[ ]    #all basic parameters are assumed to be strings unless you include the parameter name here (in which case it's converted to an int)
                     
    timers_supported=[  'delay', 'repeat', 'once', 'duration']

    __version__ = '1.1'

    def __init__(self, parent, deviceid, device, productModel, initial_parameters={}):
        self.logger = logging.getLogger('Main.'+__class__.__name__)
        #self.logger.debug('Started Class: %s, version: %s' % (__class__.__name__, __version__))
        self._parent = parent
        self._deviceid = deviceid
        self._config = device
        if device:
            self.devicekey = device.get('devicekey', None)   #this is the apikey for V3 fw encryption (if not in DIY mode)
        self.loop = asyncio.get_event_loop()
        self._update_settings(self._config)
        self.load_template()
        self._productModel = productModel   #we are created as this kind of productModel if there is more than one kind of model(one of self.productModel list)
        for param, value in initial_parameters.items():
            pass
        self.q = asyncio.Queue()
        self.loop.create_task(self._process_queue())
        self.logger.debug('Created %s Device V:%s, model: %s' % (self.__class__.__name__,self.__version__,self._productModel))
        
    async def _process_queue(self):
        while True:
            try:
                command, message = await self.q.get()
                if command is None:
                    #self.logger.debug('deviceid: %s, got EXIT command' % self.deviceid)
                    self.q.task_done()
                    raise RuntimeError('task completed')

                self.logger.debug('deviceid: %s, got command from queue: %s, %s' % (self.deviceid, command, message))
                func = self._on_message(command, message)
                if func: 
                    asyncio.run_coroutine_threadsafe(func,self.loop)
                self.q.task_done()
            except Exception as e:
                self.logger.debug('deviceid: %s, process queue exited: %s' % (self.deviceid,e))
                break
                
    def _update_settings(self,data):
        for param in data['params']:
            if param not in self.settings.keys() and param not in self.other_params.keys():
                self.logger.debug('adding %s to settings' % param)
                self.settings[param]=param
                
    def pprint(self,obj):
        """Pretty JSON dump of an object."""
        return self._parent.pprint(obj)
 
    @property
    def config(self):
        return self._config
        
    @property
    def deviceid(self):
        return self._deviceid
    
    @property
    def name(self):
        return self._config['name']
        
    def is_number(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False
        
    def convert_json(self, message, throw_error=False):
        '''
        converts message to dictionary if it's a valid json string.
        Does not convert single numbers, returns them unchanged.
        If throw_error is set, raises JSONDecodeError on invalid json
        '''
        if isinstance(message, str):
            try:
                if not self.is_number(message):
                    message = json.loads(message.replace("'",'"'))
            except json.JSONDecodeError:
                if throw_error:
                    raise
        return message
    
    def _on_message(self, command, message):
        self.logger.info("%s CLIENT: Received Command: %s, device: %s, Setting: %s" % (__class__.__name__,command, self.deviceid, message))
        func = None
        
        json_message = message
        message = self.convert_json(message.lower())   #make case insensitive as "ON" does not work ("on" does)
        
        for param, description in self.settings.items():
            if command == param or command == description:
                self.logger.debug('Setting parameter for device: %s: %s, %s' % (self.deviceid, param, message))
                func = self._setparameter(param, message)
                break
        else:
        
            if 'set_switch' in command:
                self.logger.debug('set switch mode: %s, %s' % (self.deviceid,message)) 
                func = self._setparameter('switch', message)
        
            elif 'set_led' in command:
                self.logger.debug('set led mode: %s, %s' % (self.deviceid,message)) #example: mosquitto_pub -t "/ewelink_command/100050xxxx/set_led" -m "on" or mosquitto_pub -t "/ewelink_command/Switch 1/set_led" -m "off"
                func = self._setparameter('sledOnline', message)
                
            elif 'send_json' in command:
                '''
                Sets "parms" to whatever you send as a json string (not dict)
                You can use this to send custom json parameters to the device (if you know the format)
                '''
                self.logger.debug('send_json: for device %s' % self.deviceid)
                try:
                    func = self._sendjson(self.convert_json(json_message, True))
                except json.JSONDecodeError as e:
                    self.log.error('Your json is invalid: {}, Error: {}'.format(json_message, e))
                
            elif 'get_config' in command:
                self.logger.debug('get_config: for device %s' % self.deviceid)
                func = self._getparameter()
                
            elif 'add_timer' in command:
                self.logger.debug('add_timer: for device %s' % self.deviceid)
                func = self._addtimer(message)
                
            elif 'list_timer' in command:
                self.logger.debug('list_timers: for device %s' % self.deviceid)
                func = self._list_timers()
                
            elif 'del_timer' in command:
                self.logger.debug('delete_timer: for device %s' % self.deviceid)
                func = self._del_timer(message)
                
            elif 'clear_timers' in command:
                self.logger.debug('clear_timers: for device %s' % self.deviceid)
                func = self._sendjson({'timers': []})
                
            else:
                func = self._on_message_default(command, message)
        
        return func
        
    def _on_message_default(self, command, message):
        '''
        Default which can be overridden by a class for processing special functions for the device while retaining the basic
        commands
        '''
        self.logger.warn('Command: %s not found' % command)
        return None
        
    async def _list_timers(self):
        await self._getparameter(waitResponse=True)
        timers = self._config['params'].get('timers', None)
        if timers:
            for num, timer in enumerate(timers):
                self.logger.info('deviceid: %s, timer %d: type:%s at:%s' % (self.deviceid, num, timer.get('coolkit_timer_type',timer['type']), timer['at']))
        else:
            self.logger.info('deviceid: %s, no timers configured' % self.deviceid)
            
    async def _del_timer(self, message):
        await self._list_timers()
        deleted = 0
        timers = self._config['params'].get('timers', None)
        if timers:
            nums_string = message.replace(',',' ').split()
            nums = sorted([int(num) for num in nums_string if num.isdigit()], reverse=True)
            
            for num in nums:
                try:
                    assert num < len(timers)
                    del_timer = timers.pop(num)
                    deleted +=1
                    self.logger.info('deviceid: %s, timer %d: type:%s at:%s DELETED' % (self.deviceid, num, del_timer.get('coolkit_timer_type',del_timer['type']), del_timer['at']))
                    
                except AssertionError as e:
                    self.logger.error('deviceid: %s, problem deleting timer %d, error %s' % (self.deviceid, num, e))
                
        else:
            self.logger.warn('deviceid: %s, can\'t delete timers: %s no timers found' % (self.deviceid,message))
        
        if deleted > 0:
            self.logger.debug('deviceid: %s,deleted %d timers' % (self.deviceid,deleted))
            func = await self._sendjson({'timers':timers})    
        else:
            func =  None
            
        return func
        
    async def _addtimer(self, message):
        '''
        NOTE Not all devices support all types of timers...
        You can set up to 8 timers, but only 1 loop timer
        see comments for message format
        '''
        await self._list_timers()
        org_message = message
        message = message.split(' ')
        timer_type = message.pop(0)
        if timer_type not in self.timers_supported:
            self.logger.error('timer setting type is incorrect, must be one of %s, you sent: %s' % (timer_type, self.timers_supported))
            return None
            
        timers = {}
        timers['timers'] = self._config['params'].get('timers', [])
        if len(timers['timers'])+1 > 8:
            self.logger.error('deviceid: %s,Cannot set more than 8 timers'  % self.deviceid)
            return None
        self.logger.debug('adding timer: %s, %s' % (len(timers['timers'])+1, org_message))
        if timer_type == 'delay':
            #"countdown" Timer format is 'delay period (channel) switch (manual)' where 'manual' is for TH16/10 to disable auto control and can be left off normally
            auto = True
            try:
                assert len(message) >= 2
                period = message.pop(0)
                if 'CH' in self._productModel: #ie there is more than one channel
                    channel = message.pop(0)
                    assert channel.isdigit()
                    channel = int(channel)
                switch = message.pop(0)
                if len(message) >= 0:
                    auto = False
                assert period.isdigit()
                assert int(period) > 0
                assert switch in ['on','off']
            except (AssertionError, IndexError) as e:
                self.logger.error('delay timer format is "delay period (channel) switch (manual)" - channel and  manual are optional, the rest are mandatory, you sent: %s, error: %s' % (org_message,e))
                return None
            timer = self._create_timer('delay', switch, period, channel=channel, auto=auto)
            timers['timers'].append(timer)
            
        elif timer_type == 'repeat':
            #"Scheduled" Timer format is "repeat at_time(cron format) (channel) switch (manual)' - channel and manual are optional
            #Example cron time (5:00pm EST, every Monday) "0 22 * * 1" (12:05pm EST every week day) "5 17 * * 1,1,3,4,5" 
            auto = True
            at_time = ''
            channel = None
            try:
                assert len(message) >= 2
                switch = message.pop()
                while switch not in ['on','off'] and len(message) > 0:
                    switch = message.pop()
                    auto = False
                if 'CH' in self._productModel: #ie there is more than one channel
                    channel = message.pop()
                    assert channel.isdigit()
                    channel = int(channel)
                if len(message) > 0:
                    at_time = ' '.join(message)

                assert self._parent._validate_cron(at_time)
                assert switch in ['on','off']
            except (AssertionError, IndexError) as e:
                self.logger.error('repeat timer format is "repeat at_time(cron format) (channel) switch (manual)" - manual is optional, you sent: %s error: %s' % (org_message,e))
                return None
            timer =  self._create_timer('repeat', switch, at_time, channel=channel, auto=auto)
            timers['timers'].append(timer)
                                    
        elif timer_type == 'once':
            #"Scheduled" Timer format is "once at_time(ISO format) (channel) switch 9manual)' - channel and manual are optional
            auto = True
            at_time = ''
            channel = None
            try:
                assert len(message) >= 2
                at_time = message.pop(0)
                switch = message.pop()
                while switch not in ['on','off'] and len(message) > 0:
                    switch = message.pop()
                    auto = False
                if 'CH' in self._productModel: #ie there is more than one channel
                    channel = message.pop()
                    assert channel.isdigit()
                    channel = int(channel)     

                assert self._parent._validate_iso8601(at_time)
                assert switch in ['on','off']
                
            except (AssertionError, IndexError) as e:
                self.logger.error('once timer format is "once at_time(ISO format) (channel) switch (manual)" - channel and manual are optional, you sent: %s error: %s' % (org_message,e))
                return None
            timer =  self._create_timer('once', switch, at_time, channel=channel, auto=auto)
            timers['timers'].append(timer)
                                    
        elif timer_type == 'duration':
            #"loop" Timer format is 'duration at_time(ISO UTC) on_time off_time switch_on (switch_off) (manual)' switch_off is optional, manual is optional
            at_time = message.pop(0).upper()
            off_switch = None
            auto = True
            try:
                assert len(message) >= 3
                if len(message) >= 5:
                    auto = False
                if len(message) >= 3:
                    on_duration = message.pop(0)
                    off_duration = message.pop(0)
                    on_switch = message.pop(0)
                if len(message) >= 1:
                    off_switch = message.pop(0)

                assert self._parent._validate_iso8601(at_time)
                assert on_duration.isdigit()
                assert off_duration.isdigit()
                assert on_switch in ['on','off']
                assert off_switch in ['on','off', None]
            except (AssertionError, IndexError) as e:
                self.logger.error('duration timer format is "duration ISO_time on_duration off_duration on_switch (off_switch) (manual)" ISO format eg is 2019-01-18T13:52:58.030Z - off_switch and manual are optional, the rest are mandatory, you sent: %s error:%s' % (org_message,e))
                return None
            
            timer = self._create_timer('duration', on_switch, at_time, on_duration, off_duration, off_switch, auto=auto)
            timers['timers'].append(timer)

        func = await self._sendjson(timers)
        return func
        
    def _create_timer(self, type='delay', on_switch='on', at_time='', on_duration='0', off_duration='0', off_switch=None, channel=None, auto=True):
        '''
        create timer dictionary
        type is delay, repeat or duration
        '''
        timer = {}
        if type == 'duration':
            timer['at']=' '.join([at_time, on_duration, off_duration])
        elif type == 'delay':
            timer['at'] = (datetime.datetime.utcnow() + datetime.timedelta(minutes=int(at_time))).isoformat()[:23]+"Z"
            timer['period'] = at_time
        else:
            timer['at'] = at_time
        timer['coolkit_timer_type']=type
        if off_switch:
            if auto and 'mainSwitch' in self.settings:
                timer['startDo']={'switch':on_switch, 'mainSwitch':on_switch}
                timer['endDo']={'switch':off_switch, 'mainSwitch':off_switch}
            else:
                timer['startDo']={'switch':on_switch}
                timer['endDo']={'switch':off_switch}
        else:
            if auto and 'mainSwitch' in self.settings:
                timer['do']={'switch':on_switch, 'mainSwitch':on_switch}
            else:
                if channel is None:
                    timer['do']={'switch':on_switch}
                else:
                    timer['do']={'outlet': channel,'switch':on_switch}
        timer['enabled']=1
        timer['mId']='87d1dfdf-e9cb-d9ee-af2a-42362079e6a4'
        timer['type']= type if any(s in type for s in('duration', 'repeat')) else 'once'
        
        return timer
        
    def load_template(self):
        # Output state change reporting template.
        self.pub_topic = MsgTemplate(
            topic='/ewelink_status/{{deviceid}}/{{param}}',
            payload='{{value}}',
            )

        # Input on/off command template.
        self.msg_on_off = MsgTemplate(
            topic='/ewelink/{{deviceid}}/{{param}}/set',
            payload='{ "cmd" : "{{value.lower()}}" }',
            )
            
        # Update the MQTT topics and payloads from the config file.
        if self._parent._configuration.get('mqtt', None) is not None:
            self.pub_topic.load_config(self._parent._configuration['mqtt'][self.device_type], 'state_topic', 'state_payload', qos=None)
        
    def _publish(self, param, value):
        topic = self.pub_topic.render_topic({'deviceid':self.deviceid, 'name':self.name, 'param':param, 'value':value})
        #message=self.pub_topic.to_json(value)
        message = self.pub_topic.render_payload({'deviceid':self.deviceid,'value':value, 'param':param, 'name':self.name})
        self._parent._publish(self.deviceid, topic, message)
        
    async def _sendjson(self, message):
        ''' send a dictionary of parameters as a json string '''
        if isinstance(message, str):
            await self._parent._sendjson(self.deviceid, message)
        else:
            await self._parent._sendjson(self.deviceid, json.dumps(message))
        
    async def _getparameter(self, params=[], waitResponse=False):
        await self._parent._getparameter(self.deviceid, params, waitResponse)
          
    async def _setparameter(self, param, targetState, update_config=True, waitResponse=False):
        if param not in self.settings.keys():
            for p,v in self.settings.items():
                if param == v:
                    param = p
                    break
            else:
                self.logger.warn('deviceid: %s, parameter: %s not found in device settings, sending anyway' % (deviceid, param))
             
        if param in self.numerical_params:
            targetState = int(targetState)
        await self._parent._setparameter(self.deviceid, param, targetState, update_config, waitResponse)
        
    def _handle_notification(self, data):
        '''
        receive status in action key 'update' or 'sysmsg'
        '''
        self.logger.debug("Received data %s" % data)
        
        if data.get('error', 0) != 0:
            self.logger.warn('Not Processing error')
            return

        self._parent.update(self._config, data)
        self._config['update']=time.time()
        
        try:
            update = data['params']
            if data.get('action', None):
                if 'update' in data['action']:
                    self._update_settings(data)
                    self.logger.debug("Action Update: Publishing: %s" % (update))
                    self._publish_config(update)
                    self._publish('status', "OK")
                            
                elif 'sysmsg' in data['action']:
                    for param, value in update.items():
                        self.logger.debug("Sysmsg Update: Publishing: %s:%s" % (param, value))
                        self._publish(param, value)
                        if 'online' in param:
                            if value == True:
                                self._parent._update_config = True
                                self._publish('status', "OK")
                                
            elif data.get('params', None):
                self._update_settings(data)
                self.logger.debug("Params Update: Publishing: %s" % (update))
                self._publish_config(update)
            else:
                self.logger.debug("No Action to Publish")
        except KeyError:
            pass
    
    def _publish_config(self, data):
        '''
        _publish dictionary passed in data
        '''
        settings = self.settings.copy()
        settings.update(self.other_params) # make dictionary of settings and other_params
            
        for param, value in data.items():
            if param in settings.keys():
                self._publish(settings[param], value)
                
            else:
                #_publish all other parameters (online, fw version etc)
                self._publish(param, value)
                
        self._publish('last_update', time.ctime())
              
    def send_command(self, command, message):
        '''
        Only used for command line (API) options, not strictly necessary if only mqtt is used, but uses the same format as mqtt
        '''
        asyncio.run_coroutine_threadsafe(self.q.put((command, message)),self.loop)
                    
    def set_parameter(self, param, value=None):
        asyncio.run_coroutine_threadsafe(self._setparameter(param, value),self.loop)
        
    def set_switch(self, mode):  
        asyncio.run_coroutine_threadsafe(self._setparameter('switch', mode),self.loop)
    
    def set_led(self, value):  
        asyncio.run_coroutine_threadsafe(self._setparameter('sledOnline', value),self.loop)
        
    def delete_timers(self):
        asyncio.run_coroutine_threadsafe(self._setparameter('timers', []),self.loop)


class Autoslide(Default):
    """An eweclient class for connecting to Autoslide automatic doors."""
    
    productModel    = ["WFA-1"]   #model list used for identifying the correct class
    
    triggers        =[  'b']
    settings        ={  'a':'mode',         #0=auto, 1=stacker, 2=lock, 3=pet
                        'b':'command',      #app trigger none=0, 1=inside, 2=outside, 3=pet, 4=stacker
                        'd':'unknown_d',
                        'e':'75_percent',   #(0=ON)
                        'f':'slam_shut',    #(0=ON)
                        'g':'unknown_g',
                        'h':'heavy_door',   #(0=ON)
                        'i':'stacker_mode', #(0=ON)
                        'j':'delay',        #door delay (in seconds)
                        'k':'unknown_k',
                        'l':'notifications', #(0=ON)
                        'sledOnline':'sledOnline',  #turn LED indicator on or off
                        }
    other_params    ={  'c':'locked',
                        'm':'open_closed_locked',
                        'n':'trigger',      #door trigger source none=0, 1=inside, 2=outside, 3=pet, 4=stacker
                        "fwVersion": "fwVersion",
                        "rssi": "rssi",
                        "staMac": "staMac"
                        }
                        
    timers_supported=[  'delay', 'repeat']
                           
    __version__ = '1.1'

    def __init__(self, parent, deviceid, device, productModel, initial_parameters={}):
        self.logger = logging.getLogger('Main.'+__class__.__name__)
        #self.logger.debug('Started Class: %s, version: %s' % (__class__.__name__, __version__))
        self._parent = parent
        self._deviceid = deviceid
        self._config = device
        if device:
            self.devicekey = device.get('devicekey', None)   #this is the apikey for V3 fw encryption (if not in DIY mode)
        self._productModel = productModel   #we are created as this kind of productModel if there is more than one kind of model(one of self.productModel list)
        self._org_delay = None
        self._delay_person = None
        self._locked = None
        self._mode = None
        self._hold_open_running = False
        self._restore_delay_task = None
        self.load_template()
        for param, value in initial_parameters.items():
            if param == 'delay_person':
               self._delay_person = value 
        self.q = asyncio.Queue()
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self._process_queue())
        self.logger.debug('Created %s Device V:%s, model: %s' % (self.__class__.__name__ ,self.__version__,self._productModel))
        
    def delay_person(self, delay_person=None):
        if delay_person is not None:
            self._delay_person = delay_person
        return self._delay_person
    
    def _on_message_default(self, command, message):
        self.logger.info("%s CLIENT: Received Command: %s, device: %s, Setting: %s" % (__class__.__name__,command, self.deviceid, message))
        func = None
        
        if 'door_trigger_delay' in command:
            #3=pet, 2=outdoor, 1=indoor, 4=stacker
            trigger, delay = message.split(' ')
            self.logger.debug('Triggering Door Delay: %s, %s, %s' % (trigger, self.deviceid, delay))
            func = self._hold_open(trigger, delay)
            
        elif 'set_delay_person' in command:
            #set delay for person different from pet
            self.logger.debug('setting delay_person to: %s' % message)
            if message == 'None':
                self._delay_person = None
            else:
                self._delay_person = message
            func = self._getparameter()
        
        elif 'door_trigger' in command:
            #3=pet, 2=outdoor, 1=indoor, 4=stacker
            self.logger.debug('Triggering Door: %s, %s' % (self.deviceid,message))
            func = self._setparameter('b', message)
     
        elif 'set_mode' in command:
            #a=mode, 0=auto, 1=stacker, 2=lock, 3=pet
            self.logger.debug('set_mode: Door %s, %s' % (self.deviceid,message)) #example: mosquitto_pub -t "/ewelink_command/100050xxxx/set_mode" -m "3" or mosquitto_pub -t "/ewelink_command/Patio Door/set_mode" -m "3"
            func = self._setparameter('a', message)

        elif 'set_option' in command:
            #options are (0=ON)
            '''
            a=mode, 0=auto, 1=stacker, 2=lock, 3=pet
            d=unknown
            e=75% power
            f=Slam Shut
            g=unknown
            h=Heavy door
            i=Stacker Mode
            j=Door Delay (in seconds)
            k=unknown
            l=Notifications
            '''
            option, setting = message.split()
            self.logger.debug('set_option: Door %s, %s to %s' % (self.deviceid, option, setting))
            func = self._setparameter(option, setting)
            
        else:
            func = super()._on_message_default(command, message)
                               
        return func
        
    async def _setparameter(self, param, targetState, update_config=True, waitResponse=False):
        '''
        a= mode, 0=auto, 1=stacker, 2=lock, 3=pet
        b= app command stack=4, pet=3, outdoor=1, indoor=2, none=0
        c= locked (1) or unlocked (0)
        settings:
        d=
        e= 75% power (0=On)
        f= Slam Shut (0=On) 
        g=
        h= Heavy Door (0=On)
        i= Stacker mode (0=On)
        j= Door open period in seconds
        k=
        l= Notifications (0=On)
        m= closed+locked (2), closed(1), open (0)
        n= local command (received by controller) pet = 3, outdoor=1, indoor=2, none=0
        '''              
        if param not in self.settings.keys():
            for p,v in self.settings.items():
                if param == v:
                    param = p
                    break
            else:
                self.logger.error('deviceid: %s, incorrect parameter: %s, parameters must be one of %s' % (self.deviceid, param, self.settings))
                return
            
        if param == 'j' and len(targetState) == 1:
            targetState = '0'+targetState
            
        if param == 'b':
            self._config['params']['b']=targetState
            self._config['b_update']=time.time() #time app was last triggered
        
        await super()._setparameter(param, targetState, update_config, waitResponse)
        
    def _handle_notification(self, data):
        '''
        receive door status in action key 'update' or 'sysmsg'
        '''
        self.logger.debug("Received data %s" % data)
        
        if data.get('error', 0) != 0:
            self.logger.warn('Not Processing error')
            return

        self._parent.update(self._config, data)
        self._config['update']=time.time()
        
        try:
            update = data['params']
            if data.get('action', None):
                if 'update' in data['action']:
                    self.logger.debug("Action Update: Publishing: %s" % (update))
                    self._publish_config(update)
                    #self._publish('status', "OK")
                    #handle circumstance where door delay for person trigger is different from default (ie Pet) trigger
                    if self._delay_person:
                        c = update.get('c',None)
                        m = update.get('m',None)
                        n = update.get('n',None)
                        b = self._config.get('b','3') #b is last app trigger
                        b_update = self._config.get('b_update',0) #this is when it was last triggered
                        self.logger.debug('ShowNotification: Got b_update: %s' % b_update)
                        if c == '0' and m == '1' and n == '0': #if not triggered locally
                            if time.time()-b_update < 2:  #if app was triggered within the last 2 seconds
                                n = b
                            else: #not triggered by app, and n='0', so manual pull
                                n = '1'
                                self.config['b_update'] = time.time()
                        if n in ['1','2']: #non-app person trigger
                            self.logger.debug('ShowNotification: adding delay to door trigger: %s, %s, %s' % (update['n'], self.deviceid, self._delay_person))
                            self.loop.create_task(self._hold_open(update['n'], self._delay_person))
                            
                elif 'sysmsg' in data['action']:
                    for param, value in update.items():
                        self.logger.debug("Sysmsg Update: Publishing: %s:%s" % (param, value))
                        self._publish(param, value)
                        if 'online' in param:
                            if value == True: 
                                self._parent._update_config = True

            elif data.get('params', None):
                self.logger.debug("Params Update: Publishing: %s" % (update))
                self._publish_config(update)
            else:
                self.logger.debug("No Action to Publish")
        except KeyError:
            pass
    
    def _publish_config(self, data):
        '''
        publish dictionary passed in data
        '''
        settings = self.settings.copy()
        settings.update(self.other_params) # make dictionary of settings and other_params
            
        for param, value in sorted(data.items()):
            if param in settings.keys():
                self._publish(settings[param], value)
                if param == 'a':
                    self._mode = value
                elif param == 'c':
                    self._locked = value
                elif param == 'j':
                    if self._delay_person is None:
                        self._publish('delay_person', value) #_publish person delay value same as default
                    else:
                        self._publish('delay_person', self._delay_person)
                elif param == 'm':  # closed (2), opening(1), closing (0)
                    if value == '0':
                        if self._locked == '1' or self._mode == '1':
                            self._publish('moving', '3')  #open
                        else:
                            self._publish('moving', '2')  #closing
                        self._publish('closed', '0')
                    elif value == '1':  
                        self._publish('closed', '0')
                        if self._mode == '1':
                            self._publish('moving', '3')   #open
                        else:
                            self._publish('moving', '1')   #opening
                    elif value == '2':   
                        self._publish('closed', '1')
                        self._publish('moving', '0')       #closed
                    else:
                        self._publish('closed', value)     #should never get here
                        self._publish('moving', '1')
                                    
            else:
                #_publish all other parameters (online, fw version etc)
                self._publish(param, value)
                
        self._publish('last_update', time.ctime())
        
    async def _hold_open(self, trigger='0', delay=5):
        if self._hold_open_running:
            self.logger.debug('hold_open: already running - ignoring trigger')
            return
        delay = str(delay)
        #self.logger.debug('hold_open: self._config: %s' % self.pprint(self._config))
        if trigger == '0':
            trigger = self._config['params'].get('n','0')
        if trigger == '0':
            trigger = self._config['params'].get('b','0')
        if trigger == '0':
            trigger = '1'
        self._hold_open_running = True
        self.logger.debug('hold_open: triggering door')
        await self._setparameter('b', trigger)
        #await asyncio.sleep(2)
        org_delay = self._config['params']['j']
        self.logger.debug('hold_open: orig delay: %s' % org_delay)
        if int(delay) != int(org_delay):
            if self._restore_delay_task:
                self._restore_delay_task.cancel()
                self.logger.debug('hold_open: cancelled _restore_delay_task')
            else:
                if len(delay) < 2:
                    delay = '0'+delay
                if not self._org_delay:
                    self._org_delay = org_delay
                    self.logger.debug('hold_open: saved org_delay')
                await asyncio.sleep(2) #dont send commands too quickly, but before door is fully open
                self.logger.debug('hold_open: updating delay')
                await self._setparameter('j', delay, update_config=False)

            self._restore_delay_task = self.loop.create_task(self._restore_delay(delay))
        self._hold_open_running = False
            
    async def _restore_delay(self, delay=2):
        self.logger.debug('restore_delay: scheduled, waiting')
        try:
            await asyncio.sleep(int(delay)) #change delay back when closing, so wait for m == 2 (closed)
            while True:
                m = self._config['params'].get('m','0')
                await asyncio.sleep(1)
                if m == '2':
                    break
            self.logger.debug('restore_delay: got org_delay: %s' % self._org_delay)
            await self._setparameter('j', self._org_delay, update_config=False)
            self._org_delay = None
        except asyncio.CancelledError:
            self.logger.debug('restore_delay: cancelled')
            pass
        self._restore_delay_task = None

    def set_mode(self, mode):  
        asyncio.run_coroutine_threadsafe(self._setparameter('a', mode),self.loop)
        
    def trigger_door(self, trigger):  
        asyncio.run_coroutine_threadsafe(self._setparameter('b', trigger),self.loop)
        
    def trigger_door_delay(self, trigger, delay=1):
        asyncio.run_coroutine_threadsafe(self._trigger_door_delay(trigger, delay),self.loop)
    
    def set_option(self, option, value):  
        asyncio.run_coroutine_threadsafe(self._setparameter(option, value),self.loop)

class BasicSwitch(Default):
    """An eweclient class for connecting to Sonoff Basic Switch"""
    
    productModel    = ["Basic","Basic2"]   #model list used for identifying the correct class
                                           #this is available in self._productModel to allow different responses depending on the model created
    
    triggers        =[  "switch"]
    settings        ={  "pulse"     : "pulse",          #'on', 'off' #param reported:topic to _publish to (sometimes parameters are just letters)
                        "pulseWidth": "pulseWidth",     #int in ms
                        "sledOnline": "sledOnline",     #'on', 'off'
                        "startup"   : "startup",        #'on', 'off'
                        "switch"    : "switch"          #'on', 'off'
                        }
    other_params    ={  "init": "init",                 #int 1 (not sure what this is)
                        "fwVersion": "fwVersion",
                        "rssi": "rssi",
                        "staMac": "staMac"
                     }
                     
    numerical_params=["pulseWidth"]    #all basic parameters are assumed to be strings unless you include the parameter name here (in which case it's converted to an int)
                     
    timers_supported=[  'delay', 'repeat', 'duration']
                         
    __version__ = '1.0'
     
class PowSwitch(Default):
    """An eweclient class for connecting to Sonoff Switch with Power Monitoring"""
    
    productModel    = ["Pow","Pow2","S31"]   #model list used for identifying the correct class
                                             #this is available in self._productModel to allow different responses depending on the model created
    
    triggers        =[  "switch"]
    settings        ={  "sledOnline": "sledOnline",     #'on', 'off'
                        "startup"   : "startup",        #'on', 'off'
                        "switch"    : "switch" ,        #'on', 'off'
                        "alarmPValue": "alarmPValue",   #Pow2 and S31 set Power Limit [min, max] -1 = off (this is a floating point value, min 0.1)
                        "alarmVValue": "alarmVValue",   #Pow2 and S31 set Voltage Limit [min, max] -1 = off
                        "alarmCValue": "alarmCValue",   #Pow2 and S31 set Current Limit [min, max] -1 = off
                        "alarmType" : "alarmType",      #Pow2 and S31 report alarms set "p|v|c" (when tripped limit is reported as above) no alarm set is "pvc" oddly enough
                        "endTime"   : "endTime",        #ISO Zulu (UTC) Time
                        "hundredDaysKwh": "hundredDaysKwh", #'get', 'start', 'stop'
                        "oneKwh"        : "oneKwh",         #'get', 'start', 'stop'
                        "startTime"     : "startTime",      #ISO Zulu (UTC) Time
                        "timeZone"      : "timeZone"        #current timezone offset from UTC (EST= -5)
                     }
    other_params    ={  "init": "init",                 #int 1 (not sure what this is)
                        "power"     : "power",          #reported power consumption (W)
                        "voltage"   : "voltage",        #Pow2 and S31 reported Voltage (V)
                        "current"   : "current",        #Pow2 and S31 reported Current (A)
                        "fwVersion": "fwVersion",
                        "rssi": "rssi",
                        "staMac": "staMac"
                     }

    timers_supported=[  'delay', 'repeat', 'duration']
    
    __version__ = '1.0'

class TH16Switch(Default):
    """An eweclient class for connecting to Sonoff Switch with Environment Monitoring"""
    
    productModel    = ["TH16", "TH10"]       #model list used for identifying the correct class
                                             #this is available in self._productModel to allow different responses depending on the model created
    
    triggers        =[  "switch", "mainSwitch"]
    settings        ={  "sledOnline": "sledOnline",     #'on', 'off'
                        "startup"   : "startup",        #'on', 'off'
                        "switch"    : "switch" ,        #'on', 'off' switching the switch manually turns off temp/humidity switching
                        "mainSwitch": "mainSwitch",     #'on', 'off' Seems to enable/disable control by temp or humidity
                        "deviceType": "deviceType",     # switching mode "normal" (manual switch), "temperature" or ,"humidity" use trigger values for on or off, set to "normal" to disable temp or humid modes
                     }
    other_params    ={  "init": "init",                                     #int 1 (not sure what this is)
                        "currentHumidity"    : "currentHumidity",           #reported Temperature (deg C)
                        "currentTemperature" : "currentTemperature",        #reported humidity (%)
                        "sensorType": "sensorType",                         # Type of sensor (example "AM2301")
                        "fwVersion": "fwVersion",
                        "rssi": "rssi",
                        "staMac": "staMac"
                     }

    timers_supported=[  'delay', 'repeat', 'duration']
    
    __version__ = '1.0'
    
    def _on_message_default(self, command, message):
        '''
        Default which can be overridden by a class for processing special functions for the device while retaining the basic
        commands
        Here process commands for setting temperature and humidity triggers.
        hi setting must be lower or the same as low setting
        The high Switch is always the opposite of the low switch (so no need to send high switch)
        format:
        topic: set_temperature
        message: low on|off high so for example "20 on 26" is turn on at 20 deg C and off at 26 deg C.
        topic: set_humidity
        as above, but with humidity values
        topic: set_manual (set deviceType="normal", mainSwitch="off" for manual mode) 
        '''
        if 'set_temperature' in command or 'set_humidity' in command:
            message = message.lower().split(" ")
            if len(message) == 2:
                low = hi = message[0] 
                low_switch = 'on' if message[1] == 'on' else 'off'
                hi_switch = 'on' if low_switch == 'off' else 'off'
            if len(message) >= 3:
                low = message[0] 
                low_switch = 'on' if message[1] == 'on' else 'off'
                hi_switch = 'on' if low_switch == 'off' else 'off'
                hi = message[2]
            else:
                self.logger.error('format of message is lo_value, switch, hi_value, or low/hi_value switch, you sent: %s' % message)
                return None
                
            if not low.isdigit() or not hi.isdigit() or int(low) > int(hi):
                self.logger.error('low and high values must be numbers, and low must be lower or equal to high, with low first, you sent: %s' % message)
                return None
                
            temp = {}
            temp["mainSwitch"]="on"
            temp["targets"]=[]
            temp["targets"].append({"reaction":{"switch": hi_switch if hi_switch == 'on' else 'off'}, "targetHigh": hi}) # high goes first in the list
            temp["targets"].append({"reaction":{"switch": low_switch if low_switch == 'on' else 'off'}, "targetLow": low}) 
            
            if 'temperature' in command:   
                self.logger.debug('set_temperature switching: for device %s to (low) %s degC:%s (hi) %s degC:%s' % (self.deviceid, low, low_switch, hi, hi_switch))
                temp["deviceType"]="temperature"
                                 
            if 'humidity' in command: 
                self.logger.debug('set_humidity switching: for device %s to (low) %s degC:%s (hi) %s degC:%s' % (self.deviceid, low, low_switch, hi, hi_switch))
                temp["deviceType"]="humidity"

            self.logger.info('sending: %s' % self.pprint(temp))
            func = self._sendjson(temp)
        elif 'set_manual' in command:
            self.logger.debug('set_manual switching: for device %s' % self.deviceid)
            temp = { "deviceType": "normal","mainSwitch": "off"}
            func = self._sendjson(temp)
        else:
            func = super()._on_message_default(command, message)
  
        return func

class LEDBulb(Default):
    """An eweclient class for connecting to Sonoff Led Bulb B1"""
    
    productModel    = ["B1"]   #model list used for identifying the correct class
                               #this is available in self._productModel to allow different responses depending on the model created
    
    triggers        =[  ]
    settings        ={  "channel0": "white_cold",   #"0-255", in colour mode (2) these are set to 0
                        "channel1": "white_warm",   #"0-255", in colour mode (2) these are set to 0
                        "channel2": "red",          #"0-255", regular RGB, in white mode (1), these are set to 0
                        "channel3": "green",        #"0-255",
                        "channel4": "blue",         #"0-255",
                                                    #These just seem to be indicators for the app, changing them makes no difference to the bulb
                        "state": "state",           #"on","off", - this does turn the bulb on and off if changed, but does not report the state correctly
                        "type": "type",             #"middle", "warm", "cold", setting of slider switch on app (does not change bulb)
                        "zyx_mode": "mode",         #colour mode 2=colour, 1=white, mode setting in app (does not change bulb) this is a numerical value
                        }
    other_params    ={  "fwVersion": "fwVersion",
                        "rssi": "rssi",
                        "staMac": "staMac"
                     }
                     
    numerical_params=["zyx_mode"]    #all basic parameters are assumed to be strings unless you include the parameter name here (in which case it's converted to an int)
                     
    timers_supported=[  'delay', 'repeat', 'once']
                         
    __version__ = '1.0'
    
class FourChannelSwitch(Default):
    """An eweclient class for connecting to Sonoff 4 Channel Switch"""
    
    productModel    = ["4CH Pro"]   #model list used for identifying the correct class
                                    #this is available in self._productModel to allow different responses depending on the model created
    
    triggers        =[ ]
    settings        ={  "pulse"     : "pulse",          #'on', 'off' #param reported:topic to _publish to (sometimes parameters are just letters)
                        "pulseWidth": "pulseWidth",     #int in ms
                        "sledOnline": "sledOnline",     #'on', 'off'
                        "configure"   : "configure",    #list of switches (4 of them)
                        "switches"    : "switches"      #list of switches (4 of them)
                        }
    other_params    ={  "init": "init",                 #int 1 (not sure what this is)
                        "fwVersion": "fwVersion",
                        "rssi": "rssi",
                        "staMac": "staMac"
                     }
                     
    numerical_params=["pulseWidth"]    #all basic parameters are assumed to be strings unless you include the parameter name here (in which case it's converted to an int)
                     
    timers_supported=[  'delay', 'repeat', 'once']
                         
    __version__ = '1.0'
    
    async def _setparameter(self, param, targetState, update_config=True, waitResponse=False):
        '''
        4 channel switch has two special parameters "configure" and "switches" which are lists of channel:switch dicts. like this:
            "configure":[{"outlet": 0,"startup": "off"},...]
            "switches":[{"outlet": 0,"switch": "off"},...]
        so need to handle these parameters differently
        '''
        try:
            if param == 'configure' or param == 'switches':
                values = targetState.split()
                if len(values) % 2 == 0:    #even number of setting/value pairs
                    if param == 'configure':
                        target = 'startup'
                    else:
                        target = 'switch'
                    setting = [{'outlet':int(values[x]) if values[x].isdigit and values[x] in ['0','1','2','3'] else None, 
                                target:values[x+1] if values[x+1] in ['on','off'] else None} for x in range(0, len(values), 2)]

                    for check in setting:
                        if check['outlet'] is None or check.get('startup', 'OK') is None or check.get('switch','OK') is None:
                            raise valueError('not a valid channel or setting')
                else:
                    raise ValueError('not an even number of pairs')
                targetState = setting
        except ValueError as e:
            self.logger.error('deviceid: %s, must be an even number of channel (number), setting (on|off) pairs for param: %s, you sent: %s : error: %s' % (self.deviceid,param,targetState,e))
            return
        
        await super()._setparameter(param, targetState, update_config, waitResponse)
