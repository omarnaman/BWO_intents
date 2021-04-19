#!/usr/bin/env python3

# Import mininet related packages
from mininet.net import Mininet
from mininet.node import Node, RemoteController, OVSController
from mininet.log import setLogLevel, info
from mininet.link import TCLink
from mininet.util import dumpNodeConnections, dumpNetConnections
from mininet.cli import CLI


def process_graph_file(filename):
    with open(filename, 'r') as f:
        edges = f.readlines()
        swes = set()
        hnums = set()
        hostlinks = []
        swlinks = []
        for edge in edges:
            s, d, bw = edge.split()
            if s.startswith('h'):
                hostlinks.append((int(s[1:]), int(d), int(bw)))
                hnums.add(int(s[1:]))
            else:
                swlinks.append((int(s), int(d), int(bw)))
                swes.update((int(s), int(d)))
    return swlinks, hostlinks, swes, hnums

def run():
    # Construct the network with cpu limited hosts and shaped links
    net = Mininet(link=TCLink, autoStaticArp=True, autoSetMacs=True, cleanup=True)

    swlinks, hostlinks, swes, hnums = process_graph_file("g.graph")

    # Create the network switches
    sw = list() # sw[i] is 'si', e.g. sw[1] is 's1', sw[0] is not used
    sw.append(None)     # let sw[0] = None
    for i in range(1, sorted(swes)[-1]+1):
        if i in swes:
            s = net.addSwitch('s%s' % i)  # dpid='000000000000ff0%s' % i
            sw.append(s)
        else: sw.append(None)

    # Create network hosts
    # h1, h2 = [net.addHost(h) for h in ['h1', 'h2']]
    hosts = list()
    hosts.append(None)     # let hosts[0] = None
    for i in range(1, sorted(hnums)[-1]+1):
        if i in hnums:
            h = net.addHost('h%s' % i)
            hosts.append(h)
        else: hosts.append(None)

    # Tell mininet to use a remote controller located at 127.0.0.1:6653
    c1 = RemoteController('c1', ip='127.0.0.1', port=6653)
    # c1 = OVSController('c1')

    net.addController(c1)

    # Simple topology for testing
    # net.addLink(h1, sw[1], bw=10)
    # net.addLink(h2, sw[2], bw=10)
    # net.addLink(sw[1], sw[2], bw=10)

    # Add link between switches
    # for (s1, s2) in [(sw[1], sw[2]), (sw[1], sw[5]), (sw[1], sw[6]), (sw[2], sw[3]), (sw[3], sw[4]), (sw[4], sw[8]), (sw[5], sw[7]), (sw[6], sw[7]), (sw[7], sw[8])]:
    #     s1_num = int(s1.name[1])
    #     s2_num = int(s2.name[1])
    #     print("s%d, s%d" % (s1_num, s2_num))
    #     # link with a delay of 5ms and 15Mbps bandwidth; s1-eth3 connects to s3, s3-eth1 connects to s1, etc.
    #     net.addLink(s1, s2, port1=s2_num, port2=s1_num, bw=15)      # delay='5ms'

    for (s1_num, s2_num, bandwidth) in swlinks:
        print("s%d, s%d" % (s1_num, s2_num))
        # link with a delay of 5ms and 15Mbps bandwidth; s1-eth3 connects to s3, s3-eth1 connects to s1, etc.
        net.addLink(sw[s1_num], sw[s2_num], port1=s2_num, port2=s1_num, bw=bandwidth)      # delay='5ms'

    for (h_num, s_num, bandwidth) in hostlinks:
        print("h%d, s%d" % (h_num, s_num))
        net.addLink(hosts[h_num], sw[s_num], bw=bandwidth)

    # Add link between a host and a switch
    # for (h, s) in [(h1, sw[0]), (h2, sw[7])]:
    #     h_num = int(h.name[1])
    #     s_num = int(s.name[1])
    #     print("h%d, s%d" % (h_num, s_num))
    #     net.addLink(h, s, bw=10)

    # Start each switch and assign it to the controller
    for i in range(1, len(sw)):    # omit sw[0]
        if sw[i] is not None:
            sw[i].start([c1])

    net.staticArp() # add all-pairs ARP entries to eliminate the need to handle broadcast
    net.start()

    # print "Network connectivity"
    # dumpNetConnections(net)
    # net.pingAll()
    # print(sw[5].intfs)   # print node dict {port# : intf object}
    # print(h1.IP(h1.intfs[3]))   # print IP associated with a specific interface of h1
    # print(sw[5].ports)   # print node dict {intf object : port#}

    CLI(net)  # open command-line interface
    # Start iperf server (-s) in h1
    # h1.cmd('iperf -s &')
    # Run a iperf client on h2 and print the throughput
    # result = h2.cmd('iperf -yc -c ' + h1.IP() + ' -t 2').split(",")[-1] # test for 2 sec, parse the csv row to get the last item (bandwidth in bps)
    # print "Throughput between h1<-->h2: " + str(float(result)/1000000.0) + "Mbps"
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()

    
