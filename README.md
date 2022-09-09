# eWeLink-mqtt
Server Bridge to control Sonoff Devices via MQTT
**This uses Sonoff stock firmware, no flashing required.**

**Version 2.0.0**
Tested on Ubuntu 20.04, Python 3.8.

## Limitations
This is a python 3.8 program and uses asyncio. you will need several libraries installed including
* asyncio
* paho-mqtt
* aiohttp
* zeroconf
* voluptuous

The eWelink authentication is based on the Home-Assistant SonoffLAN custom component. https://github.com/AlexxIT/SonoffLAN
**You Need to download this custom component to the eWeLink-mqtt directory - See Installation for details**

I have only verified that e-mail logins works.

**NOTE:**
The server only supports one eWeLink account where you can connect using your app email and password, or in place of the email you can use your 
phone number and password (but **I have not tried phone number logins, or regions other that North America and Europe**). Each time an eWeLink is logged in an authentication token is generated and you can only have one token per user, 
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

## Installatiion
Clone this repository:
```
git clone https://github.com/NickWaterton/eWeLink-mqtt.git
```
Clone SonoffLAN:
```
git clone https://github.com/AlexxIT/SonoffLAN.git
```
or download a release from https://github.com/AlexxIT/SonoffLAN/releases
Copy the `custom_components` directory from SonoffLAN to eWeLink-mqtt:
```
cp -R SonoffLAN/custom_components eWeLink-mqtt
```
cd to eWeLink-mqtt:
```
cd eWeLink-mqtt
```
The server can be run by running `./ewelink.py` now.

To update the `custom_components` directory, change to the `SonoffLAN` directory, and run `git pull`. Now copy the `custom_components` directory to `eWeLink-mqtt` as described above.

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
Command to run is `ewelink.py`

```
nick@MQTT-Servers-Host:~/Scripts/eWeLink-mqtt$ ./ewelink.py -h
usage: ewelink.py [-h] [-r {us,cn,eu,as}] [-a APPID] [-O] [-t TOPIC] [-T FEEDBACK] [-b BROKER] [-p PORT] [-U USER]
                  [-P PASSWD] [-poll POLL_INTERVAL] [-pd [POLL_DEVICE [POLL_DEVICE ...]]] [-d DEVICE]
                  [-dp DELAY_PERSON] [-l LOG] [-J] [-D] [--version]
                  login password

Forward MQTT data to Ewelink API

positional arguments:
  login                 Ewelink login (e-mail or phone number) (default: None)
  password              Ewelink password (default: None)

optional arguments:
  -h, --help            show this help message and exit
  -r {us,cn,eu,as}, --region {us,cn,eu,as}
                        Region (default: us)
  -a APPID, --appid APPID
                        AppID to use (default: 0)
  -O, --oauth           Use Oauth2 login (vs v2 login) (default: False)
  -t TOPIC, --topic TOPIC
                        MQTT Topic to send commands to, (can use # and +) default: /ewelink_command/)
  -T FEEDBACK, --feedback FEEDBACK
                        Topic on broker to publish feedback to (default: /ewelink_status)
  -b BROKER, --broker BROKER
                        ipaddress of MQTT broker (default: None)
  -p PORT, --port PORT  MQTT broker port number (default: 1883)
  -U USER, --user USER  MQTT broker user name (default: None)
  -P PASSWD, --passwd PASSWD
                        MQTT broker password (default: None)
  -poll POLL_INTERVAL, --poll_interval POLL_INTERVAL
                        Polling interval (seconds) (0=off) (default: 0)
  -pd [POLL_DEVICE [POLL_DEVICE ...]], --poll_device [POLL_DEVICE [POLL_DEVICE ...]]
                        Poll deviceID (default: None)
  -d DEVICE, --device DEVICE
                        deviceID (default: 100050a4f3)
  -dp DELAY_PERSON, --delay_person DELAY_PERSON
                        Delay in seconds for person trigger (default: None)
  -l LOG, --log LOG     path/name of log file (default: ./ewelink.log)
  -J, --json_out        publish topics as json (vs individual topics) (default: False)
  -D, --debug           debug mode
  --version             Display version of this program

  ```

## Example
Example command lines:
```
./ewelink.py my-email@gmail.com my-password -b 192.168.1.119 -l ./sonoff.log -D
```
You set up an account using the ewelink app. Add all your Sonoff devices to the ewelink account as the app described (this can be a PITA, as Sonoff devices can be hard to add).

Now when you start `ewelink.py` with your account credentials and mqtt broker address, the devices values will be published to your mqtt broker, and you can send commands via mqtt messages.

### Regions
The two tested regions are `us` (default) and `eu`.

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
And this is typical output from the server log (in debug mode):
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
