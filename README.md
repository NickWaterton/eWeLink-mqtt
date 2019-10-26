# eWeLink-mqtt
Bridge to control Sonoff Devices via MQTT

**Version 1.0**

Full Readme to follow.

**This uses stock firmware, no flashing required.**

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

##Example
Example command line:
```
./ewelink_server.py -em my-email@gmail.com -P my-password -b 192.168.1.119 -l ./sonoff.log -D
```
You set up an account using the ewelink app. Add all your Sonoff devices to the ewelink account as the app described (this can be a PITA, as Sonoff devices can be hard to add).

Now wher you start `ewelink_server.py` with your account credentials, the devices values will be published to your mqtt broker, and you can send commands via mqtt messages.

You can figure out which device id is which (I think its in the app, or you can use `get_config`.

##Devices
Most standard devices are supported (in the devices directory). if you have an unsupported device, the default for a switch is used.
Most functions are supported, including timers etc.
Feel free to add more functions/devices.

##ToDo
Working on jinja2 templates, but may switch to yaml. Not currently implemented.
