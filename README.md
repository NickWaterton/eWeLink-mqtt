# eWeLink-mqtt
Server Bridge to control Sonoff Devices via MQTT

**Version 1.0**

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

**This uses Sonoff stock firmware, no flashing required.**

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
Example command line:
```
./ewelink_server.py -em my-email@gmail.com -P my-password -b 192.168.1.119 -l ./sonoff.log -D
```
You set up an account using the ewelink app. Add all your Sonoff devices to the ewelink account as the app described (this can be a PITA, as Sonoff devices can be hard to add).

Now when you start `ewelink_server.py` with your account credentials, the devices values will be published to your mqtt broker, and you can send commands via mqtt messages.

You can figure out which device id is which (it's in the ewelink app, or you can use `get_config`.

## Devices
Most standard devices are supported (in the devices directory). if you have an unsupported device, the default for a switch is used.
Most functions are supported, including timers etc.
Feel free to add more functions/devices.

## ToDo
Working on jinja2 templates, but may switch to yaml. Not currently implemented.
