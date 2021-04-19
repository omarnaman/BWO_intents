#!/usr/bin/env python3

import time
import json
import requests
import threading
import traceback
import os
import uuid

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
        self.intents = {}       # a map of Intent


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
        # Get links: "Does not return links connected to hosts"
        url = '{}/links'.format(BASE_URL)
        response = requests.get(url, auth=AUTH).json()
        if 'links' in response:
            for link in response['links']:
                src_swId = link['src']['device']
                dst_swId = link['dst']['device']
                # # if BiLink btw src_swId and dst_swId already created
                # if dst_swId in swlinkmap and src_swId in swlinkmap[dst_swId]:
                #     bilink = swlinkmap[dst_swId][src_swId]
                if True:
                    sw1 = SwitchPort(link['src'])
                    sw2 = SwitchPort(link['dst'])
                    if 'annotations' in link and 'bandwidth' in link['annotations']:
                        bw = int(link['annotations']['bandwidth'])
                    else:
                        bw = BiLink.DEFAULT_CAPACITY
                    
                    bilink = BiLink(sw1, sw2, bw)
                    # associate BiLink with link <src_swId -- dst_swId>
                graph.add_edge(src_swId, dst_swId, bilink=bilink)

        # Initiate graph.hops
        graph.init_hops_from_edgelist()
        graph.assign_capacities()
        self.graph = graph
        self.graph.draw()
    
    def update_topo_from_ONOS(self):
        # print(f"\nUpdating Graph...\n")

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
            print("hosts disconnected ", hosts_list)
            for host in hosts_list:
                del self.hosts[host]
        # Update self.graph.edgelist
        # swlinkmap = self.graph.edgelist
        # # make a copy of current links
        # swlinkmap_copy = dict.fromkeys(swlinkmap.keys())
        # for key in swlinkmap.keys():
        #     swlinkmap_copy[key] = dict.fromkeys(swlinkmap[key].keys())
        
        # Get links
        url = '{}/links'.format(BASE_URL)
        response = requests.get(url, auth=AUTH).json()
        temp_graph = Graph()
        temp_graph.add_edges_from(self.graph.edges)
        if 'links' in response:
            for link in response['links']:
                src_swId = link['src']['device']
                dst_swId = link['dst']['device']


                if True:
                    # if BiLink btw src_swId and dst_swId already created in self.graph.edgelist
                    if (src_swId, dst_swId) in self.graph.edges:
                        bilink = self.graph[dst_swId][src_swId]["bilink"]
                        temp_graph.remove_edge(src_swId, dst_swId, virtual=True)
                    else:   # create a new BiLink
                        sw1 = SwitchPort(link['src'])
                        sw2 = SwitchPort(link['dst'])

                        if 'annotations' in link and 'bandwidth' in link['annotations']:
                            bw = int(link['annotations']['bandwidth'])
                        else:
                            bw = BiLink.DEFAULT_CAPACITY
                        print(f"Link {src_swId}--{dst_swId} Discovered")
                        bilink = BiLink(sw1, sw2, bw)
                        self.graph.add_edge(sw1, sw2, bilink=bilink)

        removed_intents = set()
        for edge in temp_graph.edges:
            print(f"Link: {edge} disconnected")
            intents = self.graph.remove_edge(*edge)
            for intent in intents:
                removed_intents.add(intent)

        # Recalculate intents affected by the removed edges
        for intent_id in removed_intents:
            print(f"reinstalling intent {self.intents[intent_id]}")
            self.add_intent(self.intents[intent_id])
        del temp_graph

    def add_intent(self, newIntent: Intent):
        print(f"\nAdding {newIntent}...\n")

        if newIntent.id not in self.intents:
            self.intents[newIntent.id] = newIntent

        path = self.graph.allocate_single(newIntent)
        if path is None:
            print("No immediate solution found, recalculating")
            self.recalculate(newIntent.id)
            return
        self.intents[newIntent.id].path = path.copy()
        self.gen_flowrules_from_path(newIntent.id)

    def recalculate(self, new_intent_id):
        flows = self.graph.topk_greedy_allocate(self.intents.values())
        if flows is None:
            res = self.graph.find_best_solution(self.intents, new_intent_id)
            
            if res <= 0:
                print("No solution can be found for this intent")
            else:
                print(f"This intent can be allocated with a maximum capacity of {res}")
            del self.intents[new_intent_id]
            return
            raise NotImplementedError("NO solution found, need to implement a resource sharing algorithm")
            # Do Resource Sharing
            return
        
        self.clear_all_flows(soft_clear=True)
        for intent in flows:
            print(intent)
            self.gen_flowrules_from_path(intent.id)

    def clear_all_flows(self, soft_clear=False):
        for intent in self.intents.values():
            if intent.flowRules is not None:
                for rule in intent.flowRules:
                    rule.delete()
        if not soft_clear:
            del self.intents
            self.intents = {}

    def list_intents(self):
        for intent in self.intents.values():
            print(f"- {intent}")
    
    def remove_intent(self, intent_id):
        if intent_id not in self.intents:
            print(f"Intent {intent_id} not found")
            return
        self.graph.remove_flow(self.intents[intent_id])
        for flow in self.intents[intent_id].flowRules:
            flow.delete()
        del self.intents[intent_id]

    def gen_flowrules_from_path(self, intentUUID):
        # path is a list of switch ids [<switch for intent.src_host>, <switch for intent.dst_host>]
        intent = self.intents[intentUUID]
        path = intent.path
        if path is None or len(path) == 0: return
        print(path)
        flowRules = []
        src_mac = intent.src_host.mac
        dst_mac = intent.dst_host.mac
        src_host_port = intent.src_host.switchport.port
        dst_host_port = intent.dst_host.switchport.port

        prevBiLink: BiLink = None

        for i in range(len(path)):
            # set two rules on switch path[i]: in_port => out_port, out_port => in_port
            
            if len(path) == 1:
                in_port = src_host_port
                out_port = dst_host_port
            # First Switch
            elif i == 0:
                in_port = src_host_port
                prevBiLink = self.graph[path[0]][path[1]]["bilink"]
                out_port = prevBiLink.get_port_of_switch(path[0])
            # Last Switch
            elif i == len(path)-1:
                in_port = prevBiLink.get_port_of_switch(path[i])
                out_port = dst_host_port
            else:
                in_port = prevBiLink.get_port_of_switch(path[i])
                prevBiLink = self.graph[path[i]][path[i+1]]["bilink"]
                out_port = prevBiLink.get_port_of_switch(path[i])

            rule = Flow(path[i], src_mac, dst_mac, in_port, out_port)
            flowRules.append(rule)
            rule = Flow(path[i], dst_mac, src_mac, out_port, in_port)    
            flowRules.append(rule)
        
        for rule in flowRules:
            rule.apply()
        
        self.intents[intentUUID].flowRules = flowRules.copy()


class StateThread(threading.Thread):
    POLLING_INTERVAL = 5

    def __init__(self, stateManager):
        self._stopevent = threading.Event()
        self.stateManager:StateManager = stateManager
        self._pendinginput = set()
        threading.Thread.__init__(self)

    def run(self):
        # print("State thread id: ", threading.get_ident())

        while not self._stopevent.isSet():
            # update topology in stateManager
            self.stateManager.update_topo_from_ONOS()

            while self._pendinginput:
                # Fastest way to get the first element of a set without popping
                for userinput in self._pendinginput: break
                print(f"\nProcessing Input '{userinput}'...\n")
                args = userinput.split()
                command = args[0]
                if len(args) > 1:
                    args = args[1:]
                try:
                    if command == 'add':
                        h1, h2, bw = args
                        if not h1.endswith('/None'):    # treat h1 as a number
                            h1 = convert_num_to_hostid(h1)
                        if not h2.endswith('/None'):    # treat h2 as a number
                            h2 = convert_num_to_hostid(h2)
                        bw = int(bw)    # treat bw as a number
                        hosts = self.stateManager.hosts
                        assert (h1 in hosts), f"HostId {h1} is invalid"
                        assert (h2 in hosts), f"HostId {h2} is invalid"
                    
                        newIntent = Intent(hosts[h1], hosts[h2], bw)
                        self.stateManager.add_intent(newIntent)

                    elif command in ["list", "ls"]:
                        self.stateManager.list_intents()
                    elif command in ["rm", "delete", "remove"]:
                        intent_id = args[0]
                        if intent_id == "all":
                            self.stateManager.clear_all_flows()
                        else:
                            self.stateManager.remove_intent(intent_id)
                    else:
                        print(f"Command {command} not supported")

                except Exception as e:
                    print(f"Failed to process input '{userinput}': " + str(e))
                    traceback.print_exc()
                self._pendinginput.pop()
            time.sleep(self.POLLING_INTERVAL)

    def stop(self):
        self._stopevent.set()
        self.stateManager.clear_all_flows()
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
            if stateThread._pendinginput:
                continue
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


    
