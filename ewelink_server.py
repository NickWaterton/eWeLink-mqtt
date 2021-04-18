#!/usr/bin/env python3

# Author: Nick Waterton <nick.waterton@med.ge.com>
# Description: OH interface to Autoslide Door
# N Waterton 1st January 2019 V1.0: initial release
# N Waterton 8th october 2020 V1.1.0: Add LAN mode and V3 Discovery

from __future__ import print_function

# import the necessary packages
import logging
from logging.handlers import RotatingFileHandler
global HAVE_MQTT
HAVE_MQTT = False
try:
    import paho.mqtt.client as paho
    HAVE_MQTT = True
except ImportError:
    print("paho mqtt client not found")
import time, os, sys, json
import signal
from _thread import start_new_thread
import asyncio

#harmony
#import discovery
from discover import Discover
import ewelink_client

__version__ = __VERSION__ = "1.1.0"
        
def pprint(obj):
    """Pretty JSON dump of an object."""
    return json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': '))
    
def discover():
    """Discover devices in the network (takes ~1 minute)."""
    log.info(
        "Attempting to discover Sonoff LAN Mode devices "
        "on the local network, please wait..."
    )
    found_devices = (
        asyncio.get_event_loop()
        .run_until_complete(Discover.discover(log))
        .items()
    )
    for found_device_id, ip in found_devices:
        log.debug(
            "Found Sonoff LAN Mode device %s at socket %s"
            % (found_device_id, ip)
        )
        
    return found_devices

def get_config(client, arg):
    print('Total number of devices: %s' % len(client.devices))
    if arg.device == 'default':
        print('Listing All devices')
        devices = client.get_config() #list of all devices
        for device in devices:
            print('Listing deviceid %s (%s):' % (device['deviceid'],device['name']))
            print('%s' % (pprint(device)))
    else:
        deviceid = client.get_deviceid(arg.device)
        if deviceid:
            print('Listing deviceid %s (%s):' % (deviceid,client.get_devicename(deviceid)))
            device = client.get_config(deviceid)
            print('%s' % pprint(device))
        else:
            print('deviceid %s Not Found' % arg.device)
    
def door_trigger(client, arg):
    if arg.device == 'default':
        arg.device = '0'
    client.send_command(arg.device, 'door_trigger', arg.trigger)
    
def set_mode(client, arg):
    if arg.device == 'default':
        arg.device = '0'
    client.send_command(arg.device, 'set_mode', arg.mode)
    
def set_option(client, arg):
    if not arg.value.isdigit():
        log.error('option value: %s must be a number' % arg.value)
        return
    if arg.device == 'default':
        arg.device = '0'
    client.send_command(arg.device, 'set_option', ' '.join([arg.option, arg.value]))
    
def send_command(client, arg):
    if arg.device == 'default':
        arg.device = '0'
    client.send_command(arg.device, arg.command, arg.message)
    
def sigterm_handler(signal, frame):
    log.info('Received SIGTERM signal')
    sys.exit(0)

def setup_logger(logger_name, log_file, level=logging.DEBUG, console=False):
    try: 
        l = logging.getLogger(logger_name)
        formatter = logging.Formatter('[%(levelname)1.1s %(asctime)s] (%(name)-20s) %(message)s')
        if log_file is not None:
            fileHandler = logging.handlers.RotatingFileHandler(log_file, mode='a', maxBytes=2000000, backupCount=5)
            fileHandler.setFormatter(formatter)
        if console == True:
            formatter = logging.Formatter('[%(levelname)1.1s %(name)-20s] %(message)s')
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
      
def on_connect(mosq, userdata, flags, rc):
    #log.info("rc: %s" % str(rc))
    log.info("Connected to MQTT Server")
    mosq.subscribe(sub_topic +"#", 0)

def on_publish(mosq, obj, mid):
    #log.info("published: %s %s" % (str(mid), str(obj)))
    pass

def on_subscribe(mosq, obj, mid, granted_qos):
    log.info("Subscribed: %s %s" % (str(mid), str(granted_qos)))

def on_disconnect():
    pass

def on_log(mosq, obj, level, string):
    log.info(string)

def on_message(mosq, obj, msg): #NOTE: This callback is not used
    log.info("message received topic: %s" % msg.topic)
    #log.info("message topic: %s, value:%s received" % (msg.topic,msg.payload.decode("utf-8")))
    command = msg.topic.split('/')[-1]
    log.info("Received Command: %s, Setting: %d" % (image_name,msg.payload.decode("utf-8")))


def main():
    '''
    Main routine
    '''
    global log
    import argparse
    parser = argparse.ArgumentParser(description='EweLink MQTT-WS Client and Control for Sonoff devices and Autoslide Doors')
    required_flags = parser.add_mutually_exclusive_group(required=True)
    # Required flags go here.
    required_flags.add_argument('-ph','--phone', action="store", default=None, help='ewelink phone number (used for login)')
    required_flags.add_argument('-em','--email', action="store", default=None, help='ewelink email (used for login)')
    required_flags.add_argument('-cf','--config', action="store", default=None, help='ewelink config file (used for all configurations)')
    # Flags with default values go here.
    parser.add_argument('-P','--e_password', action="store", default=None, help='ewelink password (used for login)')
    parser.add_argument('-i','--imei', action="store", default=None, help='ewelink imei (used for login) - optional')
    parser.add_argument('-d','--device', action="store", default='default', help='Device id of target Device, can be index number, name or deviceid (default is 0)')
    parser.add_argument('-dp','--delay_person', action="store", default=None, help='Delay in seconds for person trigger, default is same as Pet trigger')
    #parser.add_argument('-cid','--client_id', action="store", default=None, help='optional MQTT CLIENT ID (default=None)')
    parser.add_argument('-b','--broker', action="store", default=None, help='mqtt broker to publish sensor data to. (default=None)')
    parser.add_argument('-p','--port', action="store", type=int, default=1883, help='mqtt broker port (default=1883)')
    parser.add_argument('-u','--user', action="store", default=None, help='mqtt broker username. (default=None)')
    parser.add_argument('-pw','--password', action="store", default=None, help='mqtt broker password. (default=None)')
    parser.add_argument('-pt','--pub_topic', action="store",default='/ewelink_status/', help='topic to publish ewelink data to. (default=/ewelink_status/)')
    parser.add_argument('-st','--sub_topic', action="store",default='/ewelink_command/', help='topic to publish ewelink commands to. (default=/ewelink_command/)')
    parser.add_argument('-l','--log', action="store",default="None", help='log file. (default=None)')
    parser.add_argument('-D','--debug', action='store_true', help='debug mode', default = False)
    parser.add_argument('-V','--version', action='version',version='%(prog)s {version}'.format(version=__VERSION__))
    

    subparsers = parser.add_subparsers(dest='command')

    get_config_parser = subparsers.add_parser('get_config', help='Print the device configuration.')
    get_config_parser.set_defaults(func=get_config)

    trigger_door_parser = subparsers.add_parser('door_trigger', help='Trigger Door')
    trigger_door_parser.add_argument('trigger', help='trigger source, 1=outside, 2=inside, 3=pet')
    trigger_door_parser.set_defaults(func=door_trigger)

    set_mode_parser = subparsers.add_parser('set_mode', help='Set Door mode')
    set_mode_parser.add_argument('mode', help='mode to set, 0=Auto, 1=Stacker,2=Locked, 3=Pet')
    set_mode_parser.set_defaults(func=set_mode)
    
    set_option_parser = subparsers.add_parser('set_option', help='Set Door Options, enter: option value')
    set_option_parser.add_argument('option', choices=['mode', '75%_power', 'slam_shut', 'heavy_door', 'stacker_mode','door_delay', 'notifications'], help='option to change')
    set_option_parser.add_argument('value', help='value (must be a number, 0=ON, 1=OFF, delay is in seconds)')
    set_option_parser.set_defaults(func=set_option)
    
    send_command_parser = subparsers.add_parser('send_command', help='Send any valid command, enter: command value')
    send_command_parser.add_argument('command', help='command to send (eg switch)')
    send_command_parser.add_argument('message', help='value (such as on or off)')
    send_command_parser.set_defaults(func=send_command)

    arg = parser.parse_args()
    
    if arg.debug:
      log_level = logging.DEBUG
    else:
      log_level = logging.INFO
    
    #setup logging
    if arg.log == 'None':
        log_file = None
    else:
        log_file=os.path.expanduser(arg.log)
    setup_logger('Main',log_file,level=log_level,console=True)
    
    log = logging.getLogger('Main')
    
    log.debug('Debug mode')
    
    log.info("Python Version: %s" % sys.version.replace('\n',''))
    
    #register signal handler
    signal.signal(signal.SIGTERM, sigterm_handler)

    broker = arg.broker
    port = arg.port
    user = arg.user
    password = arg.password
    
    if not HAVE_MQTT:
        broker = None
    
    global sub_topic
    sub_topic = arg.sub_topic
    mqttc = None
    loop = None
    server = False
    
    if not arg.command and not broker:
        log.critical('You must define an MQTT broker, or give a command line argument')
        parser.print_help()
        sys.exit(2)

    try:
        if broker is not None:
            mqttc = paho.Client()               #Setup MQTT
            mqttc.will_set(arg.pub_topic+"client/status", "Offline at: %s" % time.ctime(), 0, False)
            mqttc.on_connect = on_connect
            mqttc.on_publish = on_publish
            mqttc.on_subscribe = on_subscribe
            if user is not None and password is not None:
                mqttc.username_pw_set(username=user,password=password)
            mqttc.connect(broker, port, 120)
            mqttc.loop_start()
            
            loop = asyncio.get_event_loop()
            if arg.debug:
                loop.set_debug(True)
            log.info("Server Started")
            server = True
            
        found_devices = discover()  #discover V3 fw LAN mode devices
            
        client = ewelink_client.EwelinkClient(arg.phone, arg.email, arg.e_password, arg.imei, loop, mqttc, arg.pub_topic, arg.config)
        
        client.set_initial_parameters(arg.device, delay_person=arg.delay_person)
        
        if not loop:
            while not client.connected:
                time.sleep(0.1)
            log.debug('connected')
            arg.func(client, arg)
            client.disconnect()
        else:
            while True:
                log.info("Connecting Client")
                loop.run_until_complete(client.login())
                log.warn("Client Disconnected")
                time.sleep(60)  #retry every 60 seconds
        
    except (KeyboardInterrupt, SystemExit):
        log.info("System exit Received - Exiting program")
        if loop:
            loop.run_until_complete(client._disconnect())
        else:
            client.disconnect()
            
    except Exception as e:
        if log_level == logging.DEBUG:
            log.exception("Error: %s" % e)
        else:
            log.error("Error: %s" % e)
        
    finally:
        if mqttc:
            mqttc.loop_stop()
            mqttc.disconnect()
        if loop:
            loop.close()
        log.debug("Program Exited")
      

if __name__ == "__main__":
    main()
