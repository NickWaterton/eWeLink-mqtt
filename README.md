# eWeLink-mqtt
Server Bridge to control Sonoff Devices via MQTT
**This uses Sonoff stock firmware, no flashing required.**

**Version 1.0**
Tested on Ubuntu 18.04, Python 3.6.

## Limitations
This is a python 3.6 program and uses asyncio. you will need several libraries installed including
* asyncio
* paho-mqtt
* websockets
* aiohttp
* yaml  __note: yaml is not actually used, but some experimental code is in there....__

I have only verified that e-mail logins works, and can only test the North America region.

**NOTE:**
The server only supports one eWeLink account where you can connect using your app email and password, or in place of the email you can use your 
phone number and password (but **I have not tried phone number logins, or regions other that North America**). Each time an eWeLink is logged in an authentication token is generated and you can only have one token per user, 
so after starting the server, you must keep your eWeLink account logged off. Otherwise, if you try to use eWeLink at the same time as the server with your paired devices, 
both applications will be contending for a login session and neither will stay online.

Alternatively, you can create a secondary account on eWeLink and your primary account to share devices with this secondary account. 
Then simply use the secondary account with the server and keep your primary account online with eWeLink without the risk of having the session expired because of the server running.

This applies to the Autoslide app as well if you use it.

**Autoslide Patio Door Openers are Supported if you have the WiFi module**

I wrote this bridge specifically to control my Autoslide patio Door opener, I just added all the other Sonoff stuff because it was easy.
I do find that the Autoslide Controller goes off line from time to time, but you can still send it commands (like to trigger the door opening for "pet" or "auto" and changing modes),
it's the feedback that seems to be the problem. Power cycling the door controller fixes it, but I'm hoping for an updated firmware from Autoslide (or Itead) to fix it.
Current F/W is 2.7 (with no updates for a year or so).

## Supported Devices
I included support for a number of basic devices, such as:
* Basic,Basic2 Switches
* Pow,Pow2,S31 Switches
* TH16,TH10 Switches
* 4CH Pro Switch
* B1 LED Bulb
* Autoslide Patio Door Controller

Anything not on this list will get added as a Basic switch (ie you get on and off control and feedback).

## Starting The Server
Command to run is `ewelink_server.py`

```
nick@MQTT-Servers-Host:~/Scripts/ewelink$ ./ewelink_server.py -h
usage: ewelink_server.py [-h] (-ph PHONE | -em EMAIL | -cf CONFIG)
                         [-P E_PASSWORD] [-i IMEI] [-d DEVICE]
                         [-dp DELAY_PERSON] [-b BROKER] [-p PORT] [-u USER]
                         [-pw PASSWORD] [-pt PUB_TOPIC] [-st SUB_TOPIC]
                         [-l LOG] [-D] [-V]
                         {get_config,door_trigger,set_mode,set_option,send_command}
                         ...

EweLink MQTT-WS Client and Control for Sonoff devices and Autoslide Doors

positional arguments:
  {get_config,door_trigger,set_mode,set_option,send_command}
    get_config          Print the device configuration.
    door_trigger        Trigger Door
    set_mode            Set Door mode
    set_option          Set Door Options, enter: option value
    send_command        Send any valid command, enter: command value

optional arguments:
  -h, --help            show this help message and exit
  -ph PHONE, --phone PHONE
                        ewelink phone number (used for login)
  -em EMAIL, --email EMAIL
                        ewelink email (used for login)
  -cf CONFIG, --config CONFIG
                        ewelink config file (used for all configurations)
  -P E_PASSWORD, --e_password E_PASSWORD
                        ewelink password (used for login)
  -i IMEI, --imei IMEI  ewelink imei (used for login) - optional
  -d DEVICE, --device DEVICE
                        Device id of target Device, can be index number, name
                        or deviceid (default is 0)
  -dp DELAY_PERSON, --delay_person DELAY_PERSON
                        Delay in seconds for person trigger, default is same
                        as Pet trigger
  -b BROKER, --broker BROKER
                        mqtt broker to publish sensor data to. (default=None)
  -p PORT, --port PORT  mqtt broker port (default=1883)
  -u USER, --user USER  mqtt broker username. (default=None)
  -pw PASSWORD, --password PASSWORD
                        mqtt broker password. (default=None)
  -pt PUB_TOPIC, --pub_topic PUB_TOPIC
                        topic to publish ewelink data to.
                        (default=/ewelink_status/)
  -st SUB_TOPIC, --sub_topic SUB_TOPIC
                        topic to publish ewelink commands to.
                        (default=/ewelink_command/)
  -l LOG, --log LOG     log file. (default=None)
  -D, --debug           debug mode
  -V, --version         show program's version number and exit
  ```

## Example
Example command lines:
```
./ewelink_server.py -em my-email@gmail.com -P my-password -b 192.168.1.119 -l ./sonoff.log -D
./ewelink_server.py -em my-email@gmail.com -P my-password get_config
```
You set up an account using the ewelink app. Add all your Sonoff devices to the ewelink account as the app described (this can be a PITA, as Sonoff devices can be hard to add).

Now when you start `ewelink_server.py` with your account credentials and mqtt broker address, the devices values will be published to your mqtt broker, and you can send commands via mqtt messages.

You can figure out which device id is which (it's in the ewelink app, or you can use `get_config`.

If no broker address is given then a command is expected to be given (like `get_config`) - you have to supply one of these two options. See the examples above.

## Devices
Many standard devices are supported (built in). if you have an unsupported device, the default for a Basic switch is used.
Most functions are supported, including timers etc.
Feel free to add more functions/devices.

## Controling Devices
You send `on` or `off` to `/ewelink_command/1000861ac4/switch` to turn the switch on or off (or change any of the other `settings` or `trigger` parameters).
eg using Ubuntu and `mosquitto` 
```
mosquitto_pub -t "/ewelink_command/1000861ac4/get_config" -m 0
mosquitto_pub -t "/ewelink_command/1000861ac4/switch" -m on
mosquitto_pub -t "/ewelink_command/1000861ac4/switch" -m off
```
and so on.

## Adding Devices
It is fairly easy to add new devices, you just add a `<devicename>.py` file (give it a unique name) in the `devices` directory with this format (this is the definition of the `B1` bulb):
```
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
```
Give the class a meaningful name ('FanControler' or something), and fill in the data. You can see the names of the fields in the log of the bridge, just match them up with whatever you want then to be in mqtt. 
You need to enter `productModel` correctly, this is how the device is identified.
EG: This is the class for the Pow, Pow2 and S31 Switches:
```
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
```
And this is the output from the server log after sending `get_config`:
```
[D 2020-04-06 15:35:07,262] (Main.EwelinkClient  ) Received data: {
  "apikey": "530203b6-cf2c-1246-894e-30851b00a6d8",
  "deviceid": "1000861ac4",
  "error": 0,
  "params": {
    "alarmCValue": [
      -1,
      -1
    ],
    "alarmPValue": [
      -1,
      -1
    ],
    "alarmType": "pcv",
    "alarmVValue": [
      -1,
      -1
    ],
    "current": "0.01",
    "fwVersion": "2.8.0",
    "init": 1,
    "oneKwh": "stop",
    "power": "2.81",
    "rssi": -53,
    "sledOnline": "on",
    "staMac": "BC:DD:C2:EA:B5:AC",
    "startup": "on",
    "switch": "on",
    "timeZone": -4,
    "uiActive": 60,
    "voltage": "121.94"
  },
  "sequence": "1586201707166"
}

```
You can see that "current" in the json is set to publish to "current" in mqtt, and so on. As you change things in the app, you can watch the json, 
and figure out what the parameters are, or send `get_config` to get them all.

This will publish the following:
```
[I 2020-04-06 15:35:07,267] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/oneKwh: stop
[I 2020-04-06 15:35:07,268] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/current: 0.01
[I 2020-04-06 15:35:07,268] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/rssi: -53
[I 2020-04-06 15:35:07,269] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/alarmType: pcv
[I 2020-04-06 15:35:07,270] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/alarmCValue: [-1, -1]
[I 2020-04-06 15:35:07,271] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/alarmVValue: [-1, -1]
[I 2020-04-06 15:35:07,272] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/fwVersion: 2.8.0
[I 2020-04-06 15:35:07,273] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/power: 2.81
[I 2020-04-06 15:35:07,274] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/alarmPValue: [-1, -1]
[I 2020-04-06 15:35:07,275] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/switch: on
[I 2020-04-06 15:35:07,276] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/voltage: 121.94
[I 2020-04-06 15:35:07,277] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/sledOnline: on
[I 2020-04-06 15:35:07,277] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/staMac: BC:DD:C2:EA:B5:AC
[I 2020-04-06 15:35:07,278] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/init: 1
[I 2020-04-06 15:35:07,279] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/timeZone: -4
[I 2020-04-06 15:35:07,280] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/startup: on
[I 2020-04-06 15:35:07,281] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/uiActive: 60
[I 2020-04-06 15:35:07,282] (Main.EwelinkClient  ) published: /ewelink_status/1000861ac4/last_update: Mon Apr  6 15:35:07 2020
```
To your mqtt server.

See `ewelink_devices.py` to see the definition of all the devices. Do **NOT** change `Default` as that is the base class for all devices!

## ToDo
Working on jinja2 templates, but may switch to yaml. Not currently implemented.
