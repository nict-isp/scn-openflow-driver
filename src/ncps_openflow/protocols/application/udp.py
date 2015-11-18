# -*- coding: utf-8 -*-
"""
protocols.application.udp
~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from protocols.application.application import Server
from protocols.application.application import Client
from protocols import udp as UdpAgent
from pox.lib.packet.udp import udp

from random import randint


log = logging.getLogger('protocols.application.udp')


class UdpServer(Server):

    protocol = udp
    agent    = UdpAgent


    def __init__(self, lport):
        self.lport = lport
        Server.__init__(self)


    def matches(self, packet, *args, **kwargs):
        dstip, dstport = self.agent.extractDst(packet)
        if dstport == self.lport:
            return True


    def getReply(self, packet, *args, **kwargs):
        return None


class OF_UdpServer(UdpServer):


    def __init__(self, lport, dpid=None, port=None):
        self.dpid = dpid
        self.port = port
        UdpServer.__init__(self, lport)


    def matches(self, packet, dpid, port):
        if self.dpid and self.dpid != dpid:
            return False

        if self.port and self.port != port:
            return False

        return UdpServer.matches(self, packet, dpid, port)


class UdpClient(Client):

    protocol = udp
    agent    = UdpAgent


    def __init__(self, src, dst, payload=''):
        self.srcMac = src[0]
        self.srcIp  = src[1]
        if len(src) == 3:
            self.srcPort = src[2]
        else:
            self.srcPort = randint(40000, 60000)
        self.src = (self.srcMac, self.srcIp, self.srcPort)

        self.dstMac  = dst[0]
        self.dstIp   = dst[1]
        self.dstPort = dst[2]
        self.dst     = (self.dstMac, self.dstIp, self.dstPort)

        self.ipId = randint(0, 2**16-1)

        self.payload = payload
        Client.__init__(self)


    def start(self):
        log.debug('udp client, start')
        return


    def matches(self, packet, *args, **kwargs):
        log.debug('udp client, matches')

        srcIp, srcPort = self.agent.extractSrc(packet)
        src = (packet.src, srcIp, srcPort)
        if src != self.dst:
            log.debug('src != self.dst')
            return False

        dstIp, dstPort = self.agent.extractDst(packet)
        dst = (packet.dst, dstIp, dstPort)
        if dst != self.src:
            log.debug('dst != self.src')
            return False

        return True


    def getReply(self, packet, *args, **kwargs):
        return None


    def sendPayload(self, payload, *args, **kwargs):
        if not self.sendCb:
            return

        self.ipId += 1
        packet = self.agent.buildRequest(self.src, self.dst, payload=payload, ipId=self.ipId)
        self.sendPkt(packet, *args, **kwargs)
        self.payloadSent(payload, *args, **kwargs)


    def payloadReceived(self, packet, payload, *args, **kwargs):
        log.debug('udp client, payloadReceived [%s]' % repr(payload))


class OF_UdpClient(UdpClient):


    def __init__(self, dpid, port, src, dst, payload=None):
        self.dpid = dpid
        self.port = port
        UdpClient.__init__(self, src, dst, payload)


    def matches(self, packet, dpid, port):
        if self.dpid != dpid:
            return False
        if self.port != port:
            return False

        return UdpClient.matches(self, packet, dpid, port)

