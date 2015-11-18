# -*- coding: utf-8 -*-
"""
protocols.application.arp
~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from protocols.application.application import Server
from protocols.application.application import Client
from protocols.application.application import PacketProcessor
from protocols import arp as ArpAgent
from pox.lib.packet.arp import arp

log = logging.getLogger('protocols.application.arp')


class ArpServer(Server):

    protocol = arp
    agent    = ArpAgent


    def __init__(self):
        Server.__init__(self)


    def getReply(self, packet, *args, **kwargs):
        arpPkt = self.agent.extractRequest(packet)
        if arpPkt is None:
            return None

        ip  = self.agent.extractRequestedIp(arpPkt)
        mac = self.getMacFromIp(ip)
        if mac is None:
            return

        arpResp = self.agent.buildResponse(packet, arpPkt, mac)

        return arpResp


    def getMacFromIp(self, ip):
        raise NotImplementedError("should be implemented.")


class OF_ArpServer(ArpServer):

    def __init__(self):
        ArpServer.__init__(self)


    def matches(self, packet, dpid, port):
        raise NotImplementedError("should be implemented.")


class ArpClient(Client):

    protocol = arp
    agent = ArpAgent

    # TODO call finished when finished
    def __init__(self, srcMac, srcIp, dstIp):
        self.srcMac = srcMac
        self.srcIp  = srcIp
        self.dstIp  = dstIp
        self.count  = 0
        self.pkt    = None
        Client.__init__(self)


    def start(self):
        self.pkt = self.agent.buildArpRequest(self.srcMac, self.srcIp, self.dstIp)
        self.sendArpPkt()


    def sendArpPkt(self):
        self.count += 1
        self.sendPkt(self.pkt)


    def matches(self, packet, *args, **kwargs):
        if packet.dst != self.pkt.src:
            return False

        arpRespPkt = self.agent.extractResponse(packet)
        if not arpRespPkt:
            return False

        arpReqPkt = self.pkt.next
        if not arpReqPkt.hwsrc == arpRespPkt.hwdst:
            return False

        if not arpReqPkt.protodst == arpRespPkt.protosrc:
            return False

        return True


    def getReply(self, packet, *args, **kwargs):
        log.debug("arp client getReply")
        self.macReceived(packet.next.hwsrc)
        self.finished()


    def macReceived(self, dst):
        """ to be overriden """



from protocols.application.ethernet import EthTunnel
class ArpTunnel(PacketProcessor):

    protocol = arp
    agent    = ArpAgent


    def __init__(self, localMac, tunnelMac):
        self.localMac  = localMac
        self.tunnelMac = tunnelMac
        self.ethTunnel = EthTunnel(localMac, tunnelMac)


    def matchesIn(self, pkt):
        res = self.ethTunnel.matchesIn(pkt)
        if not res:
            return False

        arpPkt = self.agent.extract(pkt)
        if not arpPkt:
            return False

        return True


    def matchesOut(self, pkt):
        res = self.ethTunnel.matchesOut(pkt)
        if not res:
            return False

        arpPkt = self.agent.extract(pkt)
        if not arpPkt:
            return False

        if self.localMac not in [arpPkt.hwsrc or arpPkt.hwdst]:
            return False

        return True


    def processInPacket(self, pkt):
        pkt = self.ethTunnel.processInPacket(pkt)
        if not pkt:
            return None

        arpPkt = self.agent.extract(pkt)
        if arpPkt.hwsrc == self.tunnelMac:
            arpPkt.hwsrc = self.localMac
        if arpPkt.hwdst == self.tunnelMac:
            arpPkt.hwdst = self.localMac

        pkt.set_payload(arpPkt)

        return pkt


    def processOutPacket(self, pkt):
        pkt = self.ethTunnel.processOutPacket(pkt)
        if not pkt:
            return None

        arpPkt = self.agent.extract(pkt)
        if arpPkt.hwsrc == self.localMac:
            arpPkt.hwsrc = self.tunnelMac
        if arpPkt.hwdst == self.localMac:
            arpPkt.hwdst = self.tunnelMac

        pkt.set_payload(arpPkt)

        return pkt


