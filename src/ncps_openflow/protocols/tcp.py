# -*- coding: utf-8 -*-
"""
protocols.tcp
~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging
import random
import time
from array import array
from twisted.internet import reactor

from protocols import base
from protocols import ethernet
from protocols import ipv4

from pox.lib.packet.ethernet import ethernet as Ethernet
from pox.lib.packet.ipv4 import ipv4 as Ipv4
from pox.lib.packet.tcp import tcp as Tcp


log = logging.getLogger('protocols.tcp')
name = Tcp.__name__
OsiLayer = 4


def extract(packet):
    tcpPkt = base.extract(packet, Tcp)
    return tcpPkt


def extractMember(packet, mb):
    if not isinstance(packet, Tcp):
        packet = extract(packet)
        if packet is None:
            return None

    return getattr(packet, mb, None)


def isTcpType(packet, tcpType):
    if not isinstance(packet, Tcp):
        packet = extract(packet)
        if packet is None:
            return None

    return packet.flags & tcpType == tcpType


def extractSrcPort(packet):
    return extractMember(packet, 'srcport')


def extractDstPort(packet):
    return extractMember(packet, 'dstport')


def extractSrc(packet):
    ip = ipv4.extractSrcIp(packet)
    port = extractSrcPort(packet)
    return (ip, port)


def extractDst(packet):
    ip = ipv4.extractDstIp(packet)
    port = extractDstPort(packet)
    return (ip, port)


def extractSeq(packet):
    return extractMember(packet, 'seq')


def extractAck(packet):
    return extractMember(packet, 'ack')


def extractWin(packet):
    return extractMember(packet, 'win')


def extractConnection(packet):
    _src = extractSrc(packet)
    _dst = extractDst(packet)
    src = packet.src, _src[0], _src[1]
    dst = packet.dst, _dst[0], _dst[1]
    return (src, dst)


def getFlagsAsAString(tcpPkt):
    s = ''
    if isRst(tcpPkt):
        s = 'RST, '
    if isSyn(tcpPkt):
        s = 'SYN, '
    if isPush(tcpPkt):
        s = 'PUSH, '
    if isFin(tcpPkt):
        s = 'FIN, '
    if isAck(tcpPkt):
        s += 'ACK, '
    if len(s) > 2:
        return s[:-2]
    else:
        return s


def isRst(packet):
    return isTcpType(packet, Tcp.RST_flag)


def isSyn(packet):
    return isTcpType(packet, Tcp.SYN_flag)


def isAck(packet):
    return isTcpType(packet, Tcp.ACK_flag)


def isPush(packet):
    return isTcpType(packet, Tcp.PUSH_flag)


def isFin(packet):
    return isTcpType(packet, Tcp.FIN_flag)


def buildTcpPkt(srcport, dstport, **kwargs):
    tcpPkt = Tcp()
    tcpPkt.srcport = srcport
    tcpPkt.dstport = dstport

    seq = kwargs.get('seq')
    tcpPkt.seq = seq if seq is not None else 0
    ack = kwargs.get('ack')
    tcpPkt.ack = ack if ack is not None else 0
    win = kwargs.get('window')
    tcpPkt.win = win if win is not None else 14600 #5096
    data = kwargs.get('data')
    tcpPkt.next = data if data is not None else ''

    is_fin = kwargs.get('is_fin')
    if is_fin: tcpPkt.FIN = True

    is_rst = kwargs.get('is_rst')
    if is_rst: tcpPkt.RST = True

    is_syn = kwargs.get('is_syn')
    if is_syn: tcpPkt.SYN = True

    is_push = kwargs.get('is_push')
    if is_push: tcpPkt.PSH = True

    is_ack = kwargs.get('is_ack')
    if is_ack is True or is_ack is None:
        tcpPkt.ACK = True

    return tcpPkt


def buildStandardTcpResponse(req, tcpPkt, payload='', ipId=None):
    tcpPkt.next = payload
    offres = 20*4 # header length = 20
    tcpPkt.off =  offres >> 4
    tcpPkt.res = offres & 0x0f
    tcpPkt.parsed = True
    hdr = tcpPkt.hdr(payload, calc_checksum=False)
    tcpPkt.arr = hdr
    tcpPkt.tcplen = len(hdr)

    kwargs = {}
    if ipId is None and isSyn(tcpPkt) and isAck(tcpPkt):
        kwargs['id'] = 0

    kwargs['protocol'] = Ipv4.TCP_PROTOCOL
    ipPkt = ipv4.buildIpResponse(req, tcpPkt, **kwargs)
    if ipId is not None:
        ipPkt.id = ipId

    ipPkt.iplen = len(hdr) + tcpPkt.tcplen
    tcpPkt.csum = tcpPkt.checksum()
    resp = ethernet.buildResponse(req, ipPkt)

    return resp


def buildTcpResponse(req, packet, **kwargs):
    # TODO
    reqTcp = req.find(name)
    if reqTcp is None:
        return None


def buildFrameFromConn(conn, tcpPkt):
    arr = getattr(tcpPkt, 'arr', None)
    if arr is None:
        tcpPkt.arr = array('B', tcpPkt.hdr(tcpPkt.payload, calc_checksum=False))
        tcpPkt.arr.fromstring(tcpPkt.payload)
        tcpPkt.tcplen = len(tcpPkt.arr)

    offres = len(tcpPkt.hdr(tcpPkt.payload, calc_checksum=False)) * 4
    tcpPkt.off = offres >> 4
    tcpPkt.res = offres & 0x0f
    ipPkt = Ipv4()
    ipPkt.flags = Ipv4.DF_FLAG
    ipPkt.srcip = conn.my_ip
    ipPkt.dstip = conn.other_ip
    ipPkt.protocol = Ipv4.TCP_PROTOCOL

    log.info('tcp packet = %s' % str(tcpPkt))
    log.info('srcip = %s' % str(ipPkt.srcip))
    log.info('dstip = %s, unsigned = %x' % (str(ipPkt.dstip), ipPkt.dstip.toUnsigned()))

    if not (isSyn(tcpPkt) and isAck(tcpPkt)):
        ipPkt.id = conn.ipId if conn.ipId is not None else random.randint(0, 2**16-1)
        conn.ipId = ipPkt.id + 1
    else:
        ipPkt.id = 0
        conn.ipId = random.randint(0, 2**16-1)

    tcpPkt.payload_len = len(tcpPkt.next)
    tcpPkt.prev = ipPkt

    ipPkt.iplen = len(ipPkt.hdr(tcpPkt))+ tcpPkt.tcplen

    tcpPkt.csum = tcpPkt.checksum()
    ipPkt.set_payload(tcpPkt)
    ethPkt = Ethernet()
    ethPkt.src = conn.my_mac
    ethPkt.dst = conn.other_mac
    ethPkt.type = Ethernet.IP_TYPE
    ethPkt.set_payload(ipPkt)

    return ethPkt


def buildResponse(req, packet, payload=''):
    resp = None
    if payload is None: payload = ''
    tcpPkt = buildTcpResponse(req, packet, payload=payload)
    ipPkt = ipv4.buildResponse(req, tcpPkt, protocol=Ipv4.TCP_PROTOCOL)
    resp = ethernet.buildResponse(req, ipPkt)
    return resp


# send RST, ACK
def buildDefaultResponse(packet):
    tcpPkt = extract(packet)
    if not tcpPkt:
        return
    if not isSyn(tcpPkt):
        return

    tcpPkt.flags = Tcp.RST | Tcp.ACK
    tcpPkt.ack = tcpPkt.seq + 1
    tcpPkt.seq = 0
    tcpPkt.win = 0
    _srcport = tcpPkt.srcport
    _dstport = tcpPkt.dstport
    tcpPkt.srcport = _dstport
    tcpPkt.dstport = _srcport
    tcpPkt.options = []

    return buildStandardTcpResponse(packet, tcpPkt)


def socPairInt(socPair):
    srcMac = socPair[0][0].toInt()
    dstMac = socPair[1][0].toInt()

    return (
            (
             srcMac,
             socPair[0][1],
             socPair[0][2]
            ),
            (
             dstMac,
             socPair[1][1],
             socPair[1][2]
            )
           )


class TcpSegment:
    """Describes a contiguous chunk of data in a TCP stream."""
    def __init__(self, seq, data):
        self.seq = seq               # sequence # of the first byte in this segment
        self.data = data             # data in this segment
        self.next = seq + len(data)  # first sequence # of the next data byte
        if not data:
            raise Exception('segments must contain at least 1B of data')


    def combine(self, s2):
        """Combine this segment with a s2 which comes no earlier than this
        segment starts.  If they do not overlap or meet, False is returned."""
        assert self.__cmp__(s2) <= 0 , "segement 2 must not start earlier"

        if self.next < s2.seq:
            return False # no overlap: s2 is later than us

        if self.next >= s2.next:
            return True # self completely subsumes s2

        # combine the two segments
        offset   = self.next - s2.seq
        new_data = self.data + s2.data[offset:] # union of the two

        self.data = new_data
        self.next = s2.next

        return True


    def __cmp__(self, x):
        return cmp(self.seq, x.seq)



class TcpConnection:


    """Manages the state of one half of a TCP connection."""
    # this will return a connection for a server
    @staticmethod
    def createFromPacket(packet, **kwargs):
        my_mac = packet.dst
        kwargs['my_mac'] = my_mac
        my_ip, my_port = extractDst(packet)
        kwargs['my_ip'] = my_ip
        kwargs['my_port'] = my_port

        other_mac = packet.src
        kwargs['other_mac'] = other_mac
        other_ip, other_port = extractSrc(packet)
        kwargs['other_ip'] = other_ip
        kwargs['other_port'] = other_port

        seq = extractSeq(packet)
        kwargs['seq'] = seq
        conn = TcpConnection(**kwargs)
        for key, value in kwargs.items():
            setattr(conn, key, value)

        return conn


    def __init__(self, *args, **kwargs):

        # SERVER
        # socket pair

        self.my_mac = kwargs.get('my_mac')
        self.my_ip = kwargs.get('my_ip')
        self.my_port = kwargs.get('my_port')
        self.other_mac = kwargs.get('other_mac')
        self.other_ip = kwargs.get('other_ip')
        self.other_port = kwargs.get('other_port')
        self.payload = kwargs.get('payload')
        # ID configuration
        self.ipId = None
        # TCP configuration
        self.rtt = 0.5
        self.mtu = 1500
        self.max_data = 2048
        self.max_wait_time_sec = 20
        self.last_activity = time.time()
        # TODO
        # should keep this delayed call
        # as a member and cancel it when dead...
        reactor.callLater(self.max_wait_time_sec, self.__check_wait_time)

        connection_over_cb = kwargs.get('connection_over_cb')
        if not connection_over_cb:
            connection_over_cb = lambda x: None

        self.connection_over_callback = lambda : connection_over_cb(self)
        has_data_to_send_cb = kwargs.get('has_data_to_send_cb')
        if not has_data_to_send_cb:
            has_data_to_send_cb = lambda x: None


        def f():
            has_data_to_send_cb(self)

        self.has_data_to_send_callback = f

        # info about this side of the TCP connection
        self.segments = []

        syn_seq = kwargs.get('seq')

        # client
        if syn_seq is None:
            syn_seq = random.randint(0, 2**32-1)
            self.win = 1460
            self.my_first_syn_acked = False
            self.next_seq_needed = 0

        if self.my_port is None:
            self.my_port = random.randint(40000, 60000)

        # server
        else:
            self.window = 0
            self.next_seq_needed = syn_seq + 1

        self.data_to_send = ''
        self.need_to_send_ack = False
        self.need_last_ack = False
        self.need_to_send_data = True # need to send a SYN
        self.received_fin = False
        self.ack_and_dead = False
        self.closed = False
        self.dead = False
        self.connected = False
        # information about outgoing data and relevant ACKs
        self.num_data_bytes_acked = 0
        self.first_unacked_seq = random.randint(0, 0x8FFFFFFF)
        self.last_seq_sent = self.first_unacked_seq
        self.my_syn_acked = False
        self.all_data_sent = True
        self.my_fin_sent = False
        self.my_fin_acked = False
        self.next_resend = 0
        self.reset_resend_timer()


    def get_socket_pair(self):
        """Returns the socket pair describing this connection (other then self)."""
        return ((self.my_mac,
                 self.my_ip,
                 self.my_port),
                (self.other_mac,
                 self.other_ip,
                 self.other_port)
               )


    def get_data(self):
        """Returns the data received so far (up to the first gap, if any)."""
        if self.segments:
            return self.segments[0].data
        else:
            return ''


    def add_segment(self, segment):
        """Merges segment into the bytes already received.  Raises socket.error
        if this segment indicates that the data block will exceed the maximum
        allowed."""
        if len(self.segments) > 0 and segment.next-self.segments[0].seq>self.max_data:
            raise socket.error('maximum data limit exceeded')

        self.__add_segment(segment)
        if len(self.segments) > 0 and self.segments[0].next > self.next_seq_needed:
            self.__note_activity()
            self.next_seq_needed = self.segments[0].next
            self.__need_to_send_now() # ACK the new data


    def add_data_to_send(self, data):
        """Adds data to be sent to the other side of the connection.  Raises
        socket.error if the socket is closed."""
        if not self.closed:
            self.data_to_send += data
            self.all_data_sent = False
            self.__need_to_send_now(True) # send the data
        else:
            raise socket.error('cannot send data on a closed socket')


    def fin_received(self, seq):
        """Indicates that a FIN has been received from the other side."""
        self.received_fin = True
        self.next_seq_needed = seq + 1
        self.__need_to_send_now() # ACK the FIN


    def has_data_to_send(self):
        """Returns True if there is an unACK'ed data waiting to be sent."""
        return self.num_unacked_data_bytes() > 0


    def has_ready_data(self):
        """Returns True if data has been received and there are no gaps in it."""
        return len(self.segments) == 1


    def num_unacked_data_bytes(self):
        """Returns the number of outgoing data bytes which have not been ACK'ed."""
        return len(self.data_to_send) - self.num_data_bytes_acked


    def reset_resend_timer(self):
        """Resets the retransmission timer."""
        #log.debug('reset_resend_timer')
        self.next_resend = time.time() + 2*self.rtt
        reactor.callLater(2*self.rtt, self.has_data_to_send_callback)


    def set_ack(self, ack):
        """Handles receipt of an ACK."""
        if ack-1 > self.last_seq_sent:
            log.warn("truncating an ACK for bytes we haven't sent: ack=%d last_seq_sent=%d" % (ack, self.last_seq_sent))
            ack = self.last_seq_sent + 1 # assume they meant to ack all bytes we have sent

        diff = ack - self.first_unacked_seq
        if diff <= 0:
            return

        self.__note_activity()
        self.reset_resend_timer()
        if not self.my_syn_acked:
            diff = diff - 1
            self.my_syn_acked = True

        if diff > self.num_unacked_data_bytes():
            if self.my_fin_sent:
                self.my_fin_acked = True

            if self.ack_and_dead:
                self.dead = True
                self.connection_over_callback()

            diff = self.num_unacked_data_bytes()

        self.num_data_bytes_acked += diff
        self.first_unacked_seq = ack

        if diff > 0 and not self.all_data_sent and self.has_data_to_send():
            self.__need_to_send_now(True)


    # server
    def get_packets_to_send(self):
        """Returns a list of packets which should be sent now."""
        ret = []

        if self.dead:
            if self.my_fin_acked and self.need_last_ack:
                self.need_last_ack = False
                tcpPkt = self.buildAck()
                ret.append(tcpPkt)
            return ret

        retransmit = self.__is_a_retransmission()
        if retransmit is None:
            return ret

        # do we have something to send?
        if not self.my_syn_acked:
            tcpPkt = self.buildSyn()
            ret.append(tcpPkt)

        sz = self.num_unacked_data_bytes()
        base_offset = self.first_unacked_seq + (0 if self.my_syn_acked else 1)
        if sz > 0:
            pass

        # send a FIN if we're closed, our FIN hasn't been ACKed, and we've sent
        # all the data we were asked to already (or there isn't any)
        if self.closed and not self.my_fin_acked and (self.all_data_sent or sz<=0):
            self.need_last_ack = True
            if not self.my_fin_sent or retransmit:
                if ret:
                    lastPkt = ret[-1]
                    lastPkt.flags |= Tcp.FIN
                    ret[-1] = lastPkt
                else:
                    tcpPkt = self.buildFin(base_offset + sz)
                    ret.append(tcpPkt)

            if not self.my_fin_sent:
                self.my_fin_sent = True
                self.last_seq_sent += 1

        if not ret and self.need_to_send_ack:
            tcpPkt = self.buildAck()
            ret.append(tcpPkt)


            # reply FIN ACK to FIN ACK
            if self.received_fin and not self.my_fin_acked:
                self.my_fin_sent = True
                lastPkt = ret[-1]
                lastPkt.FIN = True

                ret[-1] = lastPkt
                self.last_seq_sent += 1
                self.ack_and_dead = True

        if ret:
            self.reset_resend_timer()
            self.need_to_send_ack = False

        return ret


    # requests
    def createSyn(self):
        return buildTcpPkt(self.my_port,
                           self.other_port,
                           seq=self.first_unacked_seq,
                           ack=self.__get_ack_num(),
                           is_syn=True,
                           is_ack=False
                          )


    def createPushAck(self, payload):
        return buildTcpPkt(self.my_port,
                           self.other_port,
                           seq=self.last_seq_sent + 1,
                           ack=self.__get_ack_num(),
                           is_push=True,
                           data=payload
                          )


    def buildDataTransmissionAck(self, payload):
        return buildTcpPkt(self.my_port,
                           self.other_port,
                           seq=self.last_seq_sent + 1,
                           ack=self.__get_ack_num(),
                           is_push=False,
                           is_syn=False,
                           is_fin=False,
                           is_ack=True,
                           data=payload
                          )


    # responses (except Fin maybe)
    def buildSyn(self):
        return buildTcpPkt(self.my_port,
                           self.other_port,
                           seq=self.first_unacked_seq,
                           ack=self.__get_ack_num(),
                           is_syn=True
                          )


    def buildAck(self):
        return buildTcpPkt(self.my_port,
                           self.other_port,
                           seq=self.first_unacked_seq,
                           ack=self.__get_ack_num(),
                          )


    def buildFin(self, seq):
        return buildTcpPkt(
                self.my_port,
                self.other_port,
                seq=seq,
                ack=self.__get_ack_num(),
                data='',
                is_fin=True)


    def close(self):
        """Closes this end of the connection.  Will cause a FIN to be sent if
        the connection was not already closed.  The connection will be call
        its connection over callback TCPConnection.WAIT_TIME_SEC later."""
        if not self.closed:
            self.closed = True
            self.__need_to_send_now() # send the FIN


    def __get_ack_num(self):
        """Returns the sequence number we should use for the ACK field on
        outgoing packets."""
        return self.next_seq_needed


    def __add_segment(self, segment):
        """Merges segment into the bytes already received.  Raises socket.error
        if this segment indicates that the data block will exceed the maximum
        allowed."""
        combined_index = None
        for i in range(len(self.segments)):
            if self.segments[i].combine(segment):
                combined_index = i
                break

        if not combined_index:
            self.segments.append(segment)
            return

        i = combined_index
        new_segment = self.segments[i]
        while i < len(self.segments)-1:
            if new_segment.combine(self.segments[i+1]):
                self.segments.pop(i+1)
            else:
                break


    def __check_wait_time(self):
        """Checks to see if this connection has been idle for longer than
        allowed.  If so, it is marked as dead and the connection_over_callback
        is called."""
        if time.time() - self.last_activity > self.max_wait_time_sec:
            self.connection_over_callback()
            self.dead = True
        else:
            reactor.callLater(self.max_wait_time_sec, self.__check_wait_time)


    def __need_to_send_now(self, data_not_ack=False):
        """The next call to get_packets_to_send will ensure an ACK is sent as
        well as any unacknowledged data."""
        if data_not_ack:
            self.need_to_send_data = True
        else:
            self.need_to_send_ack = True
        if self.has_data_to_send_callback:
            self.has_data_to_send_callback()


    def __note_activity(self):
        """Marks the current time as the last active time."""
        self.last_activity = time.time()


    def __is_a_retransmission(self):
        """is it time to send data?"""
        retransmit = False
        now = time.time()
        if now < self.next_resend:
            if not self.need_to_send_ack and not self.need_to_send_data:
                return None
        else:
            retransmit = True

        return retransmit

