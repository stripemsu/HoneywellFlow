# HoneywellFlow

This project made for reading data from 2 Honeywell Zephyr HAF Series flow sensors and provide this data as JSON on any requests.

Hardware user: RaspberryPi 3 and I2C Switch TCA9548A

Require python 2

Sensors connected on Ch0 and Ch1 with 2KOhm pull-up resistors.

server script expected at /srv/flow/FlowServer.py

put systemd script to /lib/systemd/system/flowserver.service
