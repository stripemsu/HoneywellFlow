#!/usr/bin/env python

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import json
from datetime import datetime
from time import sleep
import RPi.GPIO as GPIO
import io, fcntl

#Hardware related classes

I2C_SLAVE=0x0703
I2C_BUS=1

GetFlowData=lambda:None

toHex = lambda x: ''.join([hex(ord(c))[2:].zfill(2) for c in x])

class i2c:
        def __init__(self):
                self.i2c_r=io.open("/dev/i2c-"+str(I2C_BUS),"rb",buffering=0)
                self.i2c_w=io.open("/dev/i2c-"+str(I2C_BUS),"wb",buffering=0)
        def __del__(self):
                self.i2c_r.close()
                self.i2c_w.close()
        def SetAddrR(self, addr):
                fcntl.ioctl(self.i2c_r, I2C_SLAVE, addr)
        def SetAddrW(self, addr):
                fcntl.ioctl(self.i2c_w, I2C_SLAVE, addr)
        def write(self,bytes):
                self.i2c_w.write(bytes)
        def read(self,cnt):
                try:
                        return self.i2c_r.read(cnt)
                except:
                        return None

class i2cMult:
        #Magic const, reset on GPIO4, active low
        RstIO=4
        #Magic const, i2c bus number, see /dev/i2c-0 or /dev/i2c-1
        TCA9548_addr=0x70
        def __init__(self,i2c):
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(self.RstIO, GPIO.OUT)
                GPIO.output(self.RstIO, 1);
                self.i2c=i2c
        def reset(self):
                GPIO.output(self.RstIO, 0);
                sleep(0.001);
                GPIO.output(self.RstIO, 1);
        def __del__(self):
                GPIO.cleanup()
        def SetCh(self,ch):
                if ch>7 or ch<0: return
                try:
                        self.i2c.SetAddrW(self.TCA9548_addr)
                        self.i2c.write(chr(1<<ch))
                except:
                        self.reset()
                        self.i2c.write(chr(1<<ch))

class FlowSensor:
        HAFAddr=0x49
        maxflow=100 #100 sccm
        def __init__(self,i2c,mult,multaddr):
                self.i2c=i2c
                self.i2cmlt=mult
                self.maddr=multaddr
        def read(self):
                self.i2cmlt.SetCh(self.maddr)
                self.i2c.SetAddrR(self.HAFAddr)
                fl=self.i2c.read(2)
                try:
                        f1=(ord(fl[0])<<8)|(ord(fl[1]))
                        if(f1&0b1100000000000000!=0):
                                print 'Flow error on n.%d: 0x'%(self.maddr)+toHex(fl)
                                return None
                except:
                        print 'Flow read error on n.%d'%self.maddr
                flow = self.maxflow * (f1/16384.0-0.1)/0.8
                return flow

#Web server related classes
class FlowClass:
        Flow_CR=None
        Flow_MBE=None
        TimeRead=None
        TimeMeas=None
        Cnts=0

        def __init__(self,CR_addr=0,MBE_addr=1):
                i2cbus=i2c()
                mult=i2cMult(i2cbus)
                self.SensCR=FlowSensor(i2cbus,mult,CR_addr)
                self.SensMBE=FlowSensor(i2cbus,mult,MBE_addr)
        def data(self):
                self.TimeRead=self.TimeMeas
                return {'CR':self.Flow_CR, 'MBE': self.Flow_MBE,'counts':self.Cnts}
        def measure(self):
                t=datetime.now()
                f_cr=self.SensCR.read()
                f_mbe=self.SensMBE.read()
                if self.TimeMeas is None:
                        self.TimeMeas=t
                        self.TimeRead=t
                        self.Flow_CR=f_cr
                        self.Flow_MBE=f_mbe
                elif self.TimeRead==self.TimeMeas:
                        self.TimeMeas=t
                        self.Flow_CR=f_cr
                        self.Flow_MBE=f_mbe
                        self.Cnts=0
                else:
                        try:
                                tmult = 1.0*((t-self.TimeMeas).total_seconds())/((t-self.TimeRead).total_seconds())
                        except:
                                return
                        self.TimeMeas=t
                       if f_cr is not None:
                                        self.Flow_CR=(f_cr-self.Flow_CR)*tmult
                        if f_mbe is not None:
                                        self.Flow_MBE=(f_mbe-self.Flow_MBE)*tmult
                        self.Cnts+=1

class server(HTTPServer):
  def server_bind(self):
        HTTPServer.server_bind(self)
        self.socket.settimeout(0.1)

class handler(BaseHTTPRequestHandler):
  def log_request(*args):
    pass;
  def do_GET(self):
        global GetFlowData;

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'Flow': GetFlowData()}))

if __name__ == "__main__":
        #hardware init
        Flow=FlowClass(0,1)
        GetFlowData=Flow.data
        addr='127.0.0.1'
        port=8083
        httpd = server( (addr, port),handler)
        print 'Started httpd serivce on %s port %d...' % (addr,port)
        while True:
                httpd.handle_request()
                Flow.measure()
