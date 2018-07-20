# HoneywellFlow

Server uses python 2

This project made for reading data from 2 Honeywell Zephyr HAF Series flow sensors and provide this data as JSON on any requests.
Data logged by telegraf using httpjson requests on the same host

Hardware used: RaspberryPi 3, I2C Switch TCA9548A, HAFUHT0100L4AXT sensors

Sensors connected on Ch0 and Ch1 with 2KOhm pull-up resistors.

## Install
server script expected at /srv/flow/FlowServer.py

$ chmod +x /srv/flow/FlowServer.py

put systemd script to /lib/systemd/system/flowserver.service
'''bash
$ sudo systemctl daemon-reload
$ sudo systemctl start flowserver.service
$ sudo systemctl enable flowserver.service
'''
