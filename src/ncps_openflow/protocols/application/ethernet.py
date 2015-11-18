# -*- coding: utf-8 -*-
"""
protocols.application.ethernet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from protocols.application.application import Server
from protocols.application.application import Client
from protocols.application.application import Filter
from protocols.application.application import PacketProcessor
from protocols import ethernet as EthAgent
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet import ETHERNET as EthModule


ETH_ANY = EthModule.ETHER_ANY
ETH_BCAST = EthModule.ETHER_BROADCAST

log = logging.getLogger('protocols.application.ethernet')


class EthServer(Server):

    protocol = ethernet
    agent    = EthAgent
    PROT     = ethernet.IP_TYPE


    def processPacket(self, packet, *args, **kwargs):
        pkt = self.agent.extract(packet)
        if pkt is None:
            return None

        if not self.matches(pkt, *args, **kwargs):
            return None

        p = self.agent.extractPayload(pkt)
        if p:
            self.payloadReceived(pkt, p, *args, **kwargs)

        resp = self.getReply(pkt, *args, **kwargs)

        return resp


    def matches(self, packet, *args, **kwargs):
        if packet.type == self.PROT:
            return True

        return False


    def getReply(self, packet, *args, **kwargs):
        return None


    def payloadReceived(self, packet, payload, *args, **kwargs):
        """ to be overriden. """


    def sendPayload(self, payload, *args, **kwargs):
        if not self.sendCb:
            return

        packet = self.agent.buildRequest(typ=self.PROT, payload=payload)
        self.sendPkt(packet, *args, **kwargs)
        self.payloadSent(payload, *args, **kwargs)


    def payloadSent(self, payload, *args, **kwargs):
        """ to be overriden. """


class OF_EthServer(EthServer):


    def matches(self, packet, dpid, port):
        return EthServer.matches(self, packet, dpid, port)


    def payloadReceived(self, packet, payload, dpid, port):
        """ to be overriden. """


    def sendPayload(self, payload, dpid, port):
        """ to be overriden. """


class EthClient(Client):

    protocol = ethernet
    agent    = EthAgent


    def __init__(self, src, dst, payload=None):
        self.src = src
        self.dst = dst
        self.payload = payload
        Client.__init__(self)


    def start(self):
        log.debug('ethernet client, start')
        return


    def matches(self, packet, *args, **kwargs):
        log.debug('ethernet client, matches')
        if packet.src != self.dst:
            log.debug('src != self.dst')
            return False
        if packet.dst != self.src:
            log.debug('dst != self.src')
            return False
        return True


    def getReply(self, packet, *args, **kwargs):
        return None


    def sendPayload(self, payload, *args, **kwargs):
        log.debug('ethernet client, sendPayload')
        if not self.sendCb:
            return

        packet = None # TODO
        self.sendFrame(packet.tostring(), *args, **kwargs)
        self.payloadSent(payload, *args, **kwargs)


    def payloadReceived(self, payload, *args, **kwargs):
        log.debug('ethernet client, payloadReceived [%s]' % repr(payload))


    def payloadSent(self, payload, *args, **kwargs):
        log.debug('ethernet client, payloadSent')


class OF_EthClient(EthClient):


    def __init__(self, dpid, port, src, dst, payload=None):
        self.dpid = dpid
        self.port = port
        EthClient.__init__(self, src, dst, payload)


    def matches(self, packet, dpid, port):
        if port != self.port:
            return False
        if dpid != self.dpid:
            return False

        return EthClient.matches(self, packet, dpid, port)


class EthTunnel(PacketProcessor):

    protocol = ethernet
    agent    = EthAgent


    def __init__(self, localMac, tunnelMac):
        self.localMac  = localMac
        self.tunnelMac = tunnelMac


    def matchesIn(self, pkt):
        pkt = self.agent.extract(pkt)
        if pkt is None:
            return False
        if pkt.dst in [ETH_ANY, ETH_BCAST, self.tunnelMac]:
            return True

        return False


    def matchesOut(self, pkt):
        pkt = self.agent.extract(pkt)
        if pkt is None:
            return False
        if pkt.src != self.localMac:
            return False

        return True


    def processInPacket(self, pkt):
        pkt = self.agent.extract(pkt)
        if pkt is None:
            return None

        pkt.dst = self.localMac

        return pkt


    def processOutPacket(self, pkt):
        pkt = self.agent.extract(pkt)
        if pkt is None:
            return None

        pkt.src = self.tunnelMac

        return pkt


