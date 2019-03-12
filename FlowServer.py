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
                        #print 'Flow read error on n.%d'%self.maddr
                        return
                flow = self.maxflow * (f1/16384.0-0.1)/0.8
                return flow

class FlowData:
        Flow=None
        currFlow=None
        Sensor=None
        Name=""
        def __init__(self,name,sensor):
                self.Name=name
                self.Sensor=sensor
        def read(self):
                self.currFlow=self.Sensor.read()
        def initFlow(self):
                self.Flow=self.currFlow
        def updateFlow(self,TimeMult):
                if self.Flow==None:
                        self.initFlow()
                        return
                if self.currFlow==None:
                        return
                self.Flow+=(self.Flow-self.currFlow)*TimeMult
                
#Web server related classes
class FlowClass:
        Flow=[]
        TimeRead=None
        TimeMeas=None
        Cnts=0

        def __init__(self):
                self.i2cbus=i2c()
                self.mult=i2cMult(self.i2cbus)
                t=datetime.now()
                self.TimeRead=t
                self.TimeMeas=t
        def add(self, name, i2caddr):
                self.Flow.append(FlowData(name,FlowSensor(self.i2cbus,self.mult,i2caddr)))
        def data(self):
                self.TimeRead=self.TimeMeas
                data={}
                for flow in self.Flow:
                        data[flow.Name]=flow.Flow
                data['counts']=self.Cnts
                #print(data)
                return data
        def measure(self):
                t=datetime.now()
                for flow in self.Flow:
                        flow.read()
                #print([f.currFlow for f in self.Flow],(t-self.TimeRead).total_seconds())

                for flow in self.Flow:
                        flow.read()
                
                if self.TimeRead==self.TimeMeas:
                        self.TimeMeas=t
                        for flow in self.Flow:
                                flow.initFlow()
                        self.Cnts=1
                else:
                        try:
                                tmult = 1.0*((t-self.TimeMeas).total_seconds())/((t-self.TimeRead).total_seconds())
                        except:
                                # is t == self.TimeRead -> div by 0?
                                return
                        self.TimeMeas=t
                        for flow in self.Flow:
                                flow.updateFlow(tmult)                        
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
        Flow=FlowClass()
        Flow.add('MBE',0)
        Flow.add('CR',1)
        GetFlowData=Flow.data
        addr='127.0.0.1'
        port=8083
        httpd = server( (addr, port),handler)
        print 'Started httpd serivce on %s port %d...' % (addr,port)
        while True:
                httpd.handle_request()
                Flow.measure()
