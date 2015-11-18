# -*- coding: utf-8 -*-
"""
protocols.application.tcp
~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from protocols.application.application import Server
from protocols.application.application import Client
from protocols import ipv4 as Ipv4Agent
from protocols import tcp as TcpAgent
from protocols.tcp import TcpSegment
from protocols.tcp import TcpConnection
from pox.core import core
from pox.lib.packet.tcp import tcp
from random import randint

log = logging.getLogger('protocols.application.tcp')


class TcpServer(Server):
    """Implements a basic TCP Server which handles raw TCP packets passed to it."""

    protocol = tcp
    agent    = TcpAgent


    def __init__(self, lport, max_active_conns=1000):   #was max_active_conns=250
        """port is the port the TCPServer should listen for SYN packets on."""
        assert lport>=0 and lport<65536, "Port must be between 0 and 65536 (exclusive)"

        self.lport            = lport
        self.connections      = {}
        self.max_active_conns = max_active_conns
        Server.__init__(self)


    def processPacket(self, packet, *args, **kwargs):
        tcpPkt = self.agent.extract(packet)
        if tcpPkt is None:
            return None

        if not self.matches(packet, *args, **kwargs):
            return None

        for f in self.filters:
            packet = f.packetIn(packet)

        conn = self.getConnection(packet, *args, **kwargs)
        if not conn:
            return None

        conn = self.processTcpPkt(conn, packet, tcpPkt)
        if not conn or conn.closed:
            return None

        conn = self.processTcpData(conn, packet, tcpPkt, *args, **kwargs)
        _tcpPkt = self.getReply(packet, *args, **kwargs)
        if _tcpPkt is None:
            return None

        resp = self.agent.buildStandardTcpResponse(packet, _tcpPkt, payload=_tcpPkt.next, ipId=None if not conn.ipId else conn.ipId+1)
        if conn.ipId is None:
            ipId = Ipv4Agent.extractId(resp)
            if ipId == 0:
                ipId = randint(0, 2**16-1)
            conn.ipId = ipId
        conn.ipId += 1

        return resp


    def matches(self, packet, *args, **kwargs):
        dstip, dstport = self.agent.extractDst(packet)
        if dstport == self.lport:
            return True

        return False


    def getReply(self, packet, *args, **kwargs):
        conn = self.getConnection(packet, *args, **kwargs)
        if conn is None:
            return None

        pkts = conn.get_packets_to_send()
        if not pkts:
            return

        return pkts[0]


    def getConnection(self, packet, *args, **kwargs):
        socPair = self.agent.extractConnection(packet)
        key     = self.agent.socPairInt(socPair)
        conn    = self.connections.get(key)
        if not conn:
            conn = self.createConnection(packet, socPair, *args, **kwargs)
            if conn is None:
                return conn

            self.connections[key] = conn
            log.debug("{TcpServer} adding the %dth connection [%s]" % (len(self.connections), key))

        return conn


    def createConnection(self, packet, socPair, *args, **kwargs):
        if len(self.connections) >= self.max_active_conns:
            s  = 'Ignoring new connection request:'
            s += 'already have %d active connections'
            log.warn(s % self.max_active_conns)
            return None

        if not self.agent.isSyn(packet):
            return None

        _kwargs = {}
        _kwargs.update(kwargs)
        _kwargs['connection_over_cb']  = self.connectionClosed
        _kwargs['has_data_to_send_cb'] = self.connHasDataToSend
        conn = TcpConnection.createFromPacket(packet, **_kwargs)

        return conn


    def connHasDataToSend(self, conn):
        if conn is None:
            return None

        pkts = conn.get_packets_to_send()
        if len(pkts)==0:
            return None

        tcpPkt = pkts[0]
        pkt    = self.agent.buildFrameFromConn(conn, tcpPkt)
        self.sendConnectionPkt(conn, pkt)


    def sendConnectionPkt(self, conn, pkt):
        self.sendPkt(pkt)


    def processTcpPkt(self, conn, packet, tcpPkt):
        seq = self.agent.extractSeq(tcpPkt)
        if seq is None:
            return None

        try:
            if len(tcpPkt.next) > 0:
                segment = TcpSegment(seq, tcpPkt.next)
                conn.add_segment(segment)

        except Exception as inst:
            log.exception(inst)
            conn.close()
            return None

        if self.agent.isFin(tcpPkt):
            conn.fin_received(seq)

        window = self.agent.extractWin(tcpPkt)
        if window is None:
            return None

        conn.window = max(1460, window)  # ignore requests to shrink the window below an MTU
        if self.agent.isAck(tcpPkt):
            ack = self.agent.extractAck(tcpPkt)
            if ack is None:
                return None

            conn.set_ack(ack)
        return conn


    def processTcpData(self, conn, packet, tcpPkt, *args, **kwargs):
        if not conn or conn.closed:
            return conn
        if not conn.has_ready_data():
            return conn

        data = conn.get_data()
        self.payloadReceived(packet, data, *args, **kwargs)
        conn.segments = []

        return conn


    def sendPayload(self, payload, *args, **kwargs):
        """ TODO """


    def connectionClosed(self, *args, **kwargs):
        """Called when it is ready to be removed.  Removes the connection."""
        if len(args) == 0:
            return

        conn = args[0]
        if not conn:
            return

        socPair = conn.get_socket_pair()
        socPair = socPair[::-1]
        key     = self.agent.socPairInt(socPair)

        try:
            conn = self.connections[key]
            core.callDelayed(1, self.delConnection, key)

            if not conn.closed:
                conn.close()

        except KeyError:
            log.warn('Tried to remove connection which is not in our dictionary: %s' % str(key))
            pass


    def delConnection(self, key):
        try:
            del self.connections[key]
            log.debug("Deleting the %dth connection [%s]" % (len(self.connections)+1, key))
        except:
            log.error("unable to delete this connection [%s]" % key)
            pass


class OF_TcpServer(TcpServer):


    def sendConnectionPkt(self, conn, pkt):
        self.sendPkt(pkt, conn.dpid, conn.port)


    def getConnection(self, packet, dpid, port, *args, **kwargs):
        socPair = self.agent.extractConnection(packet)
        key     = self.agent.socPairInt(socPair)
        conn    = self.connections.get(key)
        if not conn:
            kwargs['dpid'] = dpid
            kwargs['port'] = port
            conn = self.createConnection(packet, socPair, *args, **kwargs)
            if conn is None:
                return conn

            self.connections[key] = conn
            log.debug("{OF_TcpServer} Adding the %dth connection [%s]" % (len(self.connections), key))

        return conn


class TcpClient(Client, TcpConnection):

    protocol = tcp
    agent    = TcpAgent

    def __init__(self, src, dst, payload=''):
        kwargs = {}
        kwargs['my_mac'] = src[0]
        kwargs['my_ip']  = src[1]
        if len(src) == 3:
            srcport = src[2]
            kwargs['my_port'] = srcport

        kwargs['other_mac']           = dst[0]
        kwargs['other_ip']            = dst[1]
        kwargs['other_port']          = dst[2]
        kwargs['connection_over_cb']  = self.connectionClosed
        kwargs['has_data_to_send_cb'] = self.connHasDataToSend
        kwargs['payload'] = payload

        self.d = None # deferred

        TcpConnection.__init__(self, **kwargs)
        Client.__init__(self)


    def start(self):
        tcpPkt = self.createSyn()
        self.firstSYN = tcpPkt
        packet = self.agent.buildFrameFromConn(self, tcpPkt)
        self.sendPkt(packet)


    def processPacket(self, packet, *args, **kwargs):
        tcpPkt = self.agent.extract(packet)
        if tcpPkt is None:
            return None
        if not self.matches(packet, *args, **kwargs):
            return None

        for f in self.filters:
            packet = f.packetIn(packet)

        if self.agent.isRst(tcpPkt) and not self.my_first_syn_acked:
            self.doConnectionFailure()
            return

        self.processTcpPkt(packet, tcpPkt)
        self.processTcpData(packet, tcpPkt, *args, **kwargs)
        _tcpPkt = self.getReply(packet, *args, **kwargs)
        if _tcpPkt is None:
            return None

        resp = self.agent.buildStandardTcpResponse(packet, _tcpPkt, payload=_tcpPkt.next, ipId=None if not self.ipId else self.ipId)

        if self.ipId is None:
            ipId = Ipv4Agent.extractId(resp)
            if ipId == 0:
                ipId = randint(0, 2**16-1)
                del randint
            self.ipId = ipId

        self.ipId += 1

        return resp


    def matches(self, packet, *args, **kwargs):
        src     = (self.my_mac, self.my_ip, self.my_port)
        dst     = (self.other_mac, self.other_ip, self.other_port)
        socPair = self.agent.extractConnection(packet)

        if src != socPair[1]:
            return False
        if dst != socPair[0]:
            return False

        return True


    def processTcpPkt(self, packet, tcpPkt):
        ethPkt = packet
        ipPkt  = ethPkt.find('ipv4')

        if tcpPkt.payload_len > 0 and not (ipPkt.iplen==tcpPkt.hdr_len+len(ipPkt.hdr(''))):
            self.add_segment(TcpSegment(tcpPkt.seq, tcpPkt.next))

        if self.agent.isFin(tcpPkt):
            if not self.closed:
                self.fin_received(tcpPkt.seq)

        # remember window and latest ACK
        self.window = max(1460, tcpPkt.win)  # ignore requests to shrink the window below an MTU

        if not self.agent.isAck(tcpPkt):
            return

        if not self.my_first_syn_acked:
            self.my_first_syn_acked = True
            self.my_syn_acked       = True
            self.need_to_send_ack   = True
            self.first_unacked_seq  = tcpPkt.ack
            self.next_seq_needed    = tcpPkt.seq + 1

        if self.agent.isFin(tcpPkt) and self.closed:
            # it means we already sent a fin, ack and we just received a fin, ack
            self.need_to_send_ack = True
            self.last_seq_sent    += 1
            self.next_seq_needed  += 1
            self.set_ack(tcpPkt.ack)

        else:
            if self.my_first_syn_acked and not self.connected:
                self.connected = True
                core.callDelayed(0.01, self.connectionEstablished)
            self.set_ack(tcpPkt.ack)


    def processTcpData(self, packet, tcpPkt, *args, **kwargs):
        if not self.has_ready_data():
            return self

        data = self.get_data()
        self.payloadReceived(packet, data, *args, **kwargs)
        self.segments = []


    def getReply(self, packet, *args, **kwargs):
        if not self.my_first_syn_acked:
            return self.firstSYN

        pkts = self.get_packets_to_send()
        if not pkts:
            return

        return pkts[0]


    def connHasDataToSend(self, conn):
        if self != conn:
            return None

        pkts = self.get_packets_to_send()
        if len(pkts) == 0:
            return None

        tcpPkt = pkts[0]
        pkt    = self.agent.buildFrameFromConn(self, tcpPkt)
        self.sendPkt(pkt)


    def connectionEstablished(self):
        """ to be overriden """
        # when syn, syn_ack, ack is finished


    def connectionLost(self):
        """ to be overriden """


    def doConnectionFailure(self):
        self.dead = True
        self.connectionFailure()


    def connectionFailure(self):
        """ to be overriden """


    def sendPayload(self, payload, *args, **kwargs):
        i = 0
        payloadLenth = len(payload)
        while i < payloadLenth:
            #TODO change 1460 by the real value for this connection
            endOfSegment= min(i+1000, payloadLenth) #

            dataToSend = payload[i:endOfSegment]
            i = endOfSegment

            tcpPkt = self.buildDataTransmissionAck(dataToSend)
            packet = self.agent.buildFrameFromConn(self, tcpPkt)
            self.sendPkt(packet)
            self.last_seq_sent += len(dataToSend)


        self.all_data_sent = True
        tcpPkt = self.buildFin(self.last_seq_sent+1)
        packet = self.agent.buildFrameFromConn(self, tcpPkt)

        self.sendPkt(packet)
        self.my_fin_sent    = True
        self.last_seq_sent += 1
        self.payloadSent(payload, *args, **kwargs)


    def connectionClosed(self, *args, **kwargs):
        core.callDelayed(0.01, self.finished)


class OF_TcpClient(TcpClient):


    def __init__(self, dpid, port, src, dst, payload=''):
        self.dpid = dpid
        self.port = port
        TcpClient.__init__(self, src, dst, payload)


    def matches(self, packet, dpid, port):
        _dpid = getattr(self, 'dpid', None)
        if _dpid is None:
            self.dpid = dpid
        if self.dpid != dpid:
            return False

        _port = getattr(self, 'port', None)
        if _port is None:
            self.port = port
        if self.port != port:
            return False

        return TcpClient.matches(self, packet, dpid, port)


    def sendPkt(self, pkt, *args, **kwargs):
        if not self.sendCb:
            return

        TcpClient.sendPkt(self, pkt, self.dpid, self.port)


