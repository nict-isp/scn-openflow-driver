# -*- coding: utf-8 -*-
"""
protocols.application.application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.packet_utils import ethtype_to_str
from protocols import ethernet as Ethernet

log = logging.getLogger('protocols.application')


class ProtApp(object):

    protocol = None
    agent    = None

    def __init__(self):
        self.filters = []


    def addFilter(self, f):
        log.warn("addFilter")
        if not f:
            return

        if f not in self.filters:
            self.filters.append(f)


    def addFilters(self, fs):
        if not fs:
            return

        self.filters += fs


    def delFilter(self, f):
        if not f:
            return

        try:
            self.filters.remove(f)
        except:
            pass


    def delFilters(self, fs):
        for f in fs:
            self.delFilter(f)


class Filter(ProtApp):

    def __init__(self):
        self.inActive  = False
        self.outActive = False
        ProtApp.__init__(self)


    def packetIn(self, packet):
        pkt = self.processPacketIn(packet)
        if not self.inActive:
            return packet

        return pkt


    def packetOut(self, packet):
        _pkt = packet
        if isinstance(packet, str):
            _pkt = ethernet(arr=packet)

        pkt = self.processPacketOut(_pkt)
        if not self.outActive:
            return packet

        return pkt


    def processPacketIn(self, packet):
        """ to be overriden. Should return a packet"""


    def processPacketOut(self, packet):
        """ to be overriden. """


class VerboseFilter(Filter):

    protocol = ethernet
    agent    = Ethernet


    def __init__(self):
        Filter.__init__(self)


    def processPacketIn(self, packet):
        log.debug("VerboseFilter.processPacketIn, %s" % str(packet))


    def processPacketOut(self, packet):
        log.debug("VerboseFilter.processPacketOut, %s" % str(packet))


class Application(ProtApp):

    sendCb     = None
    finishedCb = None


    def __init__(self):
        ProtApp.__init__(self)


    def processPacket(self, packet, *args, **kwargs):
        """ packetを処理し、返事が必要なら返事のpacketを返す。 """
        pkt = self.agent.extract(packet)
        if pkt is None:
            return None

        if not self.matches(packet, *args, **kwargs):
            return None

        for f in self.filters:
            packet = f.packetIn(packet)

        m = self.agent.__dict__.get('extractPayload', None)
        if m:
            p = m(pkt)
            if p:
                self.payloadReceived(packet, p, *args, **kwargs)

        resp = self.getReply(packet, *args, **kwargs)
        return resp


    def matches(self, packet, *args, **kwargs):
        raise NotImplementedError("should be implemented.")


    def getReply(self, packet, *args, **kwargs):
        raise NotImplementedError("should be implemented.")


    def sendPayload(self, payload, *args, **kwargs):
        """ to be overriden. """


    def payloadSent(self, payload, *args, **kwargs):
        """ to be overriden. """


    def payloadReceived(self, packet, payload, *args, **kwargs):
        """ to be overriden. """


    def sendPkt(self, pkt, *args, **kwargs):
        """packetを送信する。"""
        if not self.sendCb:
            return

        try:
            for f in self.filters:
                pkt = f.packetOut(pkt, *args, **kwargs)

            self.sendCb(pkt.pack(), *args, **kwargs)

        except Exception as e:
            log.exception(e)


    def finished(self):
        if not self.finishedCb:
            return

        self.finishedCb(self)



class Server(Application):

    def __init__(self):
        Application.__init__(self)


class Client(Application):

    def __init__(self):
        Application.__init__(self)


    def start(self):
        """ to be overriden. """



class PacketProcessor(object):

    protocol = None


    def matchesIn(self, pkt):
        """ to be overriden """
        return True


    def matchesOut(self, pkt):
        """ to be overriden """
        return True


    IN_CALLBACK = 'doProcessInPacket'
    def doProcessInPacket(self, pkt):
        if not self.matchesIn(pkt):
            return pkt

        return self.processInPacket(pkt)


    OUT_CALLBACK = 'doProcessOutPacket'
    def doProcessOutPacket(self, pkt):
        if not self.matchesOut(pkt):
            return pkt

        return self.processOutPacket(pkt)


    def processInPacket(self, pkt):
        """ to be overriden. """
        return pkt


    def processOutPacket(self, pkt):
        """ to be overriden. """
        return pkt


class VerboseProcessor(PacketProcessor):

    protocol = ethernet

    def processInPacket(self, pkt):
        log.debug('pkt type = %s' % ethtype_to_str(pkt.type))
        return pkt

    def processOutPacket(self, pkt):
        log.debug('pkt = [%s]' % str(pkt))
        return pkt

