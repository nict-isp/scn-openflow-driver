# -*- coding: utf-8 -*-
"""
scn.plugins.virtualNode
~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from pox.core import core
from pox.lib.revent import *
from pox.lib.addresses import *

from scn.parser import IP
from scn.parser import INTFNAME

from protocols.application.arp import OF_ArpServer
from protocols.application.icmp import OF_IcmpServer

NAME = __file__.split('/')[-1].split('.')[0]
log = core.getLogger()


class VirtualNodeCreator(EventMixin):

    _wantComponents = set(['topology'])

    def __init__(self):
    #    EventMixin.__init__(self)
        core.listenToDependencies(self, self._wantComponents)
        self.nodeList = []


    def _handle_topology_SwitchJoin(self, event):
        ofs   = event.switch
        ofsIp = ofs.ipaddr.toStr()
        for section in core.parser.getSwitchsSections():
            ip = core.parser.getValue(section, IP)
            if ip != ofsIp:
                continue

            ports = core.parser.getPortsSections(section)
            for port in ports:
                name = core.parser.getValue(port, INTFNAME)
                ofp = None
                for p in ofs.ports.values():
                    if p.name != name: continue
                    ofp = p

                if not ofp:
                    continue

                ofpIp = core.parser.getValue(port, IP)
                if not ofpIp:
                    continue

                self.setNode(ofp, ofpIp)


    def setNode(self, ofp, ip):
        ofp.ipAddr = IPAddr(ip)
        arpServer  = VirtualArpServer(ofp)
        icmpServer = VirtualIcmpServer(ofp)
        core.protocols.addServer(arpServer)
        core.protocols.addServer(icmpServer)


class VirtualArpServer(OF_ArpServer):

    def __init__(self, ofp):
        self.ofp = ofp
        OF_ArpServer.__init__(self)


    def matches(self, packet, dpid, port):
        if not dpid == self.ofp.ofs.dpid:
            return False

        if not port == self.ofp.number:
            return False

        ip = self.agent.extractRequestedIp(packet)
        if not ip:
            return False

        if ip != self.ofp.ipAddr:
            return False

        return True


    def getReply(self, packet, dpid, port):
        arpPkt = self.agent.extractRequest(packet)
        if arpPkt is None:
            return None

        arpResp = self.agent.buildResponse(packet, arpPkt, self.ofp.hwAddr)
        return arpResp


class VirtualIcmpServer(OF_IcmpServer):

    def __init__(self, ofp):
        OF_IcmpServer.__init__(self)
        self.ofp = ofp


    def matches(self, packet, dpid, port):
        if not dpid == self.ofp.ofs.dpid:
            return False

        if not port == self.ofp.number:
            return False

        ip = self.agent.extractRequestedIp(packet)
        if not ip:
            return False
        if ip != self.ofp.ipAddr:
            return False

        return True


    def getReply(self, packet, dpid, port):
        icmpPkt = self.agent.extractRequest(packet)
        if icmpPkt is None:
            return None

        resp = self.agent.buildEcho(packet, icmpPkt)
        return resp


def launch(**kwargs):
    if core.hasComponent(NAME):
        return None

    comp = VirtualNodeCreator()
    core.register(NAME, comp)

    return comp

