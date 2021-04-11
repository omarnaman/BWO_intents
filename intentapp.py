#!/usr/bin/env python3

import time
import json
import requests
import threading
import traceback
import os

from utilClasses import *
from Graph import Graph


# BASE_URL = 'http://localhost:8181/onos/v1'
# AUTH = ('onos', 'rocks')

def convert_num_to_hostid(num):   # num should <= 255, e.g. convert '14' to '00:00:00:00:00:0e/None'
    num_hex = format(int(num), '02x')
    hostid = '00:00:00:00:00:' + num_hex + '/None'
    return hostid

def gen_linksconfig_fromfile(filename):
    config = {
        "links": dict()
    }
    with open(filename, 'r') as f:
        edges = f.readlines()
        for edge in edges:
            s, d, bw = edge.split()
            if s.startswith('h'): continue
            s_hex = format(int(s), 'x')
            d_hex = format(int(d), 'x')
            s_id = 'of:' + '0'*(16-len(s_hex)) + s_hex + '/%s'%d
            d_id = 'of:' + '0'*(16-len(d_hex)) + d_hex + '/%s'%s
            config["links"][f"{s_id}-{d_id}"] = {"basic":{"bandwidth":bw}}
            config["links"][f"{d_id}-{s_id}"] = {"basic":{"bandwidth":bw}}
    # print(json.dumps(config, indent=4))
    return config

def config_links_ONOS():
    print("\nConfiguring link capacities in ONOS...\n")
    
    url = '{}/network/configuration'.format(BASE_URL)
    response = requests.post(url, auth=AUTH, json=gen_linksconfig_fromfile("g.graph"))
    print(response.text)


class StateManager():
    def __init__(self):
        self.graph = None
        self.hosts = dict()     # {hostId: <Host>}
        self.intents = []       # a list of Intent


    def retrieve_topo_from_ONOS(self):
        print("\nInitiating Graph...\n")
        graph = Graph()
        # graph.edgelist format: {switch1_Id: {switch2_Id: <BiLink>}, switch2_Id: {switch1_Id: <BiLink>}}, the same BiLink will appear twice in this mapping
        
        # Get hosts
        url = '{}/hosts'.format(BASE_URL)
        response = requests.get(url, auth=AUTH).json()
        if 'hosts' in response:
            for host in response['hosts']:
                self.hosts[host['id']] = Host(host)
        
        # Initiate graph.edgelist
        # Get links
        url = '{}/links'.format(BASE_URL)
        response = requests.get(url, auth=AUTH).json()
        if 'links' in response:
            for link in response['links']:
                src_swId = link['src']['device']
                dst_swId = link['dst']['device']

                swlinkmap = graph.edgelist
                # if BiLink btw src_swId and dst_swId already created
                if dst_swId in swlinkmap and src_swId in swlinkmap[dst_swId]:
                    bilink = swlinkmap[dst_swId][src_swId]
                else:
                    sw1 = SwitchPort(link['src'])
                    sw2 = SwitchPort(link['dst'])

                    if 'annotations' in link and 'bandwidth' in link['annotations']:
                        bw = int(link['annotations']['bandwidth'])
                    else:
                        bw = BiLink.DEFAULT_CAPACITY
                    
                    bilink = BiLink(sw1, sw2, bw)
                # associate BiLink with link <src_swId -- dst_swId>
                if src_swId in swlinkmap:
                    swlinkmap[src_swId][dst_swId] = bilink
                else:
                    swlinkmap[src_swId] = {dst_swId: bilink}

        # Initiate graph.hops
        graph.init_hops_from_edgelist()
        self.graph = graph
    
    def update_topo_from_ONOS(self):
        print(f"\nUpdating Graph...\n")

        # Update self.hosts
        hosts_list = list(self.hosts.keys())    # make a list of current host ids
        # Get hosts
        url = '{}/hosts'.format(BASE_URL)
        response = requests.get(url, auth=AUTH).json()
        if 'hosts' in response:
            for host in response['hosts']:
                if host['id'] in hosts_list:
                    hosts_list.remove(host['id'])
                else:
                    self.hosts[host['id']] = Host(host)
        
        if hosts_list:
            # some host disconnected
            print("host disconnected ", hosts_list)
        
        # Update self.graph.edgelist
        swlinkmap = self.graph.edgelist
        # make a copy of current links
        swlinkmap_copy = dict.fromkeys(swlinkmap.keys())
        for key in swlinkmap.keys():
            swlinkmap_copy[key] = dict.fromkeys(swlinkmap[key].keys())
        
        # Get links
        url = '{}/links'.format(BASE_URL)
        response = requests.get(url, auth=AUTH).json()
        if 'links' in response:
            for link in response['links']:
                src_swId = link['src']['device']
                dst_swId = link['dst']['device']

                # if link <src_swId -- dst_swId> in self.graph.edgelist
                if src_swId in swlinkmap and dst_swId in swlinkmap[src_swId]:
                    del swlinkmap_copy[src_swId][dst_swId]
                else:
                    # if BiLink btw src_swId and dst_swId already created in self.graph.edgelist
                    if dst_swId in swlinkmap and src_swId in swlinkmap[dst_swId]:
                        bilink = swlinkmap[dst_swId][src_swId]
                    else:   # create a new BiLink
                        sw1 = SwitchPort(link['src'])
                        sw2 = SwitchPort(link['dst'])

                        if 'annotations' in link and 'bandwidth' in link['annotations']:
                            bw = int(link['annotations']['bandwidth'])
                        else:
                            bw = BiLink.DEFAULT_CAPACITY
                    
                        bilink = BiLink(sw1, sw2, bw)

                    # associate BiLink with link <src_swId -- dst_swId>
                    if src_swId in swlinkmap:
                        swlinkmap[src_swId][dst_swId] = bilink
                    else:
                        swlinkmap[src_swId] = {dst_swId: bilink}
        
        if True in [len(swlinkmap_copy[k]) > 0  for k in swlinkmap_copy]:
            # some link disconnected
            print("link disconnected ", swlinkmap_copy)
        

    def add_intent(self, newIntent: Intent):
        print(f"\nAdding {newIntent}...\n")

        self.intents.append(newIntent)
        path = self.graph.astar(newIntent.src_host, newIntent.dst_host, newIntent.required_bw)
        if path is None:
            self.recalculate()
            return
        self.gen_flowrules_from_path(path, newIntent)

    def recalculate(self):
        flows = self.graph.greedy_alloc(self.intents)
        if flows is None:
            raise NotImplementedError("NO solution found, need to implement a resource sharing algorithm")
            # Do Resource Sharing
            return
        # TODO: clear all flows
        for flow in flows:
            intent = flow[0]
            path = flow[1]
            self.gen_flowrules_from_path(intent, path)
        
    def gen_flowrules_from_path(self, path, intent):
        # path is a list of switch ids [<switch for intent.src_host>, <switch for intent.dst_host>]
        if path is None or len(path) == 0: return
        
        flowRules = []
        src_mac = intent.src_host.mac
        dst_mac = intent.dst_host.mac
        src_host_port = intent.src_host.switchport.port
        dst_host_port = intent.dst_host.switchport.port

        swlinkmap = self.graph.edgelist
        prevBiLink = None

        for i in range(len(path)):
            # set two rules on switch path[i]: in_port => out_port, out_port => in_port
            if i == 0:
                in_port = src_host_port
                prevBiLink = swlinkmap[path[0]][path[1]]
                out_port = prevBiLink.get_port_of_switch(path[0])
            elif i == len(path)-1:
                in_port = prevBiLink.get_port_of_switch(path[i])
                out_port = dst_host_port
            else:
                in_port = prevBiLink.get_port_of_switch(path[i])
                prevBiLink = swlinkmap[path[i]][path[i+1]]
                out_port = prevBiLink.get_port_of_switch(path[i])

            rule = Flow(path[i], src_mac, dst_mac, in_port, out_port)
            flowRules.append(rule)
            rule = Flow(path[i], dst_mac, src_mac, out_port, in_port)    
            flowRules.append(rule)
        
        for rule in flowRules:
            rule.apply()
        
        intent.flowRules = flowRules


class StateThread(threading.Thread):
    POLLING_INTERVAL = 5

    def __init__(self, stateManager):
        self._stopevent = threading.Event()
        self.stateManager = stateManager
        self._pendinginput = set()
        threading.Thread.__init__(self)

    def run(self):
        # print("State thread id: ", threading.get_ident())

        while not self._stopevent.isSet():
            # update topology in stateManager
            self.stateManager.update_topo_from_ONOS()

            while self._pendinginput:
                userinput = self._pendinginput.pop()
                print(f"\nProcessing Input '{userinput}'...\n")
                try:
                    command, h1, h2, bw = userinput.split()
                    if not h1.endswith('/None'):    # treat h1 as a number
                        h1 = convert_num_to_hostid(h1)
                    if not h2.endswith('/None'):    # treat h2 as a number
                        h2 = convert_num_to_hostid(h2)
                    bw = int(bw)    # treat bw as a number
                    hosts = self.stateManager.hosts
                    assert (h1 in hosts), f"HostId {h1} is invalid"
                    assert (h2 in hosts), f"HostId {h2} is invalid"
                    
                    if command == 'add':
                        newIntent = Intent(hosts[h1], hosts[h2], bw)
                        self.stateManager.add_intent(newIntent)
                    else:
                        print(f"Command {command} not supported")

                except Exception as e:
                    print(f"Failed to process input '{userinput}': " + str(e))
                    traceback.print_exc()
            
            time.sleep(self.POLLING_INTERVAL)

    def stop(self):
        self._stopevent.set()

    def add_input(self, userinput):
        self._pendinginput.add(userinput)  


# just for testing purpose
def getResponse():
    url = '{}/links'.format(BASE_URL)
    response = requests.get(url, auth=AUTH)
    print(response.text)

def main():
    config_links_ONOS()
    stateManager = StateManager()
    stateManager.retrieve_topo_from_ONOS()

    # print("Parent process id = ", os.getpid())
    # print("Parent thread id: ", threading.get_ident())
    stateThread = StateThread(stateManager)

    try:
        stateThread.start()

        userinput = ''
        while True:
            # Ask for user input
            userinput = input("Enter command or 'exit': ")
            if userinput != 'exit':
                stateThread.add_input(userinput)
            else:
                break
        
        # cleanup before exit
        stateThread.stop()
        
    except (KeyboardInterrupt, SystemExit):
        stateThread.stop()

if __name__ == "__main__":
    main()
    # getResponse()


    
