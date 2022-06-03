import requests as r
import sys

class Lumix:
    def __init__(self, ip):
        self.ip = ip
        self.resp = None
        self.baseurl = "http://{ip}/cam.cgi".format(ip=self.ip)
        self.start()
        
    def start(self):
        self.resp = r.get(self.baseurl, params = {"mode": "camcmd", "value": "recmode"})
        self.check_resp()
        print('Connected')
        
    def capture(self):
        params = {"mode": "camcmd", "value": "capture"}
        self.resp = r.get(self.baseurl, params = params)
        self.check_resp()
        
    def check_resp(self):
        if self.resp != None:
            if self.resp.status_code != 200:
                raise Exception(self.resp.text)
            
if __name__ == '__main__':
    l = Lumix(sys.argv[1])
    l.capture()
