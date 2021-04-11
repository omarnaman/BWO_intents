import json
import requests

BASE_URL = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')

class SwitchPort:
    def __init__(self, json=None):
        if json is not None:
            self.device = json['device']
            self.port = json['port']

    def fill(self, id, port):
        self.device = id
        self.port = port

    def __repr__(self):
        return 'SwitchPort{{ Device: {}, Port: {} }}'.format(self.device, self.port)

class Host:    
    def __init__(self, json):
        self.id = json['id']
        self.mac = json['mac']
        location = json["locations"][0]
        sw = SwitchPort()
        sw.fill(location["elementId"], location["port"])
        self.switchport = sw

    def __repr__(self):
        return "Host{{ ID: {}\nMAC: {}\nLocation: {} }}\n".format(self.id, self.mac, self.switchport)

class Flow:
    priority = 40001
    timeout = 0
    isPermanent = True
        
    def __init__(self, device_id, src_mac, dst_mac, in_port, out_port):
        self.src_mac = src_mac
        self.dst_mac = dst_mac
        self.in_port = in_port
        self.out_port = out_port
        self.deviceId = device_id
        self.id = None

    def json(self):
        res = {}
        res["priority"] = self.priority
        res["timeout"] = self.timeout
        res["isPermanent"] = self.isPermanent
        res["deviceId"] = self.deviceId
        
        treatment = {}
        instructions = []
        inst = {}
        inst["type"] = "OUTPUT"
        inst["port"] = str(self.out_port)
        instructions.append(inst)
        treatment["instructions"] = instructions

        crit_port = {
            "type": "IN_PORT",
            "port": str(self.in_port),
        }
        crit_src = {
            "type": "ETH_SRC",
            "mac": self.src_mac 
        }
        crit_dst = {
            "type": "ETH_DST",
            "mac": self.dst_mac 
        }
        criteria = [crit_port, crit_dst, crit_src]
    
        res["selector"] = {"criteria": criteria}
        res["treatment"] = treatment
        return json.dumps(res, indent=2)
    
    def apply(self):
        data = self.json()
        url = "{}/flows/{}".format(BASE_URL, self.deviceId)
        res = requests.post(url, data, auth=AUTH)
        self.id = res.headers["Location"].split('/')[-1]
        return res
    
    def delete(self):
        url = "{}/flows/{}/{}".format(BASE_URL, self.deviceId, self.id)
        res = requests.delete(url, auth=AUTH)
        return res

class Intent:
    def __init__(self, src_host, dst_host, required_bw):
        self.src_host = src_host
        self.dst_host = dst_host
        self.required_bw = int(required_bw)
        self.path = None        # a list of BiLink
        self.flowRules = None   # a list of Flow

    def __repr__(self):
        return 'Intent{{ {} -- {}, {} }}'.format(self.src_host.id, self.dst_host.id, self.required_bw)

class BiLink:   # bidirectional link
    DEFAULT_CAPACITY = 10

    def __init__(self, switch1, switch2, capacity=None):
        self.switch1 = switch1      # type: SwitchPort
        self.switch2 = switch2      # type: SwitchPort
        self.capacity = capacity
        self.intents = []
     
    def __repr__(self):
        return 'BiLink{{ {} -- {}, {} }}'.format(self.switch1.device, self.switch2.device, self.capacity)

    def get_port_of_switch(self, switchId):
        if switchId == self.switch1.device:
            return self.switch1.port
        else:
            return self.switch2.port