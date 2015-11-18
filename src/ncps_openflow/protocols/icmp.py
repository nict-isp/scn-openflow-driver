# -*- coding: utf-8 -*-
"""
protocols.icmp
~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging
import struct

from protocols import base
from protocols import ethernet
from protocols import ipv4

from pox.lib.packet.packet_base import packet_base as Packet_base
from pox.lib.packet.icmp import icmp as Icmp
from pox.lib.packet.icmp import TYPE_DEST_UNREACH
from pox.lib.packet.icmp import TYPE_ECHO_REQUEST
from pox.lib.packet.icmp import TYPE_ECHO_REPLY
from pox.lib.packet.icmp import echo as Echo
from pox.lib.packet.ipv4 import ipv4 as Ipv4
from pox.lib.packet.packet_utils import checksum as computeChecksum


log = logging.getLogger('protocols.icmp')
name = Icmp.__name__
OsiLayer = 3


def extractRequest(packet):
    icmpPkt = base.extract(packet, Icmp)
    return extract(icmpPkt, TYPE_ECHO_REQUEST)


def extractResponse(packet):
    icmpPkt = base.extract(packet, Icmp)
    if icmpPkt is None:
        return None

    return extract(icmpPkt, TYPE_ECHO_REPLY)


def extract(packet, typ=None):
    if not typ:
        return extractRequest(packet)

    if not isinstance(packet, Icmp):
        return None

    if packet.type != typ:
        return None

    return packet


def extractPayload(_):
    return None


def extractRequestedIp(packet):
    return ipv4.extractDstIp(packet)


def _buildEcho(req):
    if not isinstance(req, Icmp):
        req = base.extract(req, Icmp)
        if req is None:
            return None

    resp = Icmp()
    resp.type = TYPE_ECHO_REPLY
    resp.code = req.code
    resp.set_payload(req.next)
    resp.csum = 0
    resp.csum = computeChecksum(resp.pack(), 0)

    return resp


def _buildUnreach(req):
    # TODO
    return


def buildEcho(req, packet):
    return buildResponse(req, packet, Echo)


class DummyHdr(Packet_base):


    def __init__(self, arr, prev=None, next=None):
        self.arr = arr
        self.next = next


    def hdr(self):
        return str(self.arr)
        #return self.next.hdr()


def checksumBak(packet):
    if not isinstance(packet, Icmp):
        packet = extract(packet)
        if packet is None:
            return 0

    packet.csum = 0
    icmpHdr = packet.hdr()

    if packet.next is None:
        nextHdr = ''
    elif isinstance(packet.next, str):
        nextHdr = packet.next
    elif isinstance(packet.next, DummyHdr):
        nextHdr = packet.next.hdr()
    else:
        nextHdr = packet.next.hdr()

    s = '%s%s' % (icmpHdr, nextHdr)

    icmpPkt = Icmp(arr=s, prev=packet.prev)
    icmpPkt.next = nextHdr

    return _checksum(icmpPkt)


def checksum(pkt):
    icmpPkt = base.extract(pkt, Icmp)
    if not icmpPkt:
        return 0

    s = icmpPkt.hdr()
    h = icmpPkt.next

    while h is not None:
        m = getattr(h, 'hdr', None)
        if m is None:
            s = '%s%s' % (s, str(h))
            break
        s = '%s%s' % (s, h.hdr())
        m = getattr(h, 'next', None)
        if m is None: break
        h = m

    return computeChecksum(s, 0)


def buildUnreachResp(req, packet, unreachCode):
    icmpPkt = Icmp()
    icmpPkt.type   = TYPE_DEST_UNREACH
    icmpPkt.code   = unreachCode
    icmpPkt.set_payload(packet)
    icmpPkt.parsed = True

    ipPkt = ipv4.buildIpResponse(req, icmpPkt, protocol=Ipv4.ICMP_PROTOCOL, tos=0xc0)

    dummy = DummyHdr('\x00\x00\x00\x00')
    icmpPkt.set_payload(dummy)
    dummy.set_payload(packet)

    ipLen = 0
    a = ipPkt
    while a is not None:
        m = getattr(a, 'hdr', None)
        if m:
            n = len(a.hdr())
        else:
            n = len(a)
        ipLen += n
        a = getattr(a, 'next', None)

    ipPkt.iplen = ipLen

    icmpPkt.prev = ipPkt
    ethPkt = ethernet.buildResponse(req, ipPkt)
    icmpPkt.csum = 0
    icmpPkt.csum = checksum(icmpPkt)

    return ethPkt


def buildResponse(req, packet, typ):
    resp = None
    if typ == Echo:
        icmpPkt = _buildEcho(packet)
    else:
        return None

    if icmpPkt is None:
        return None

    ipPkt = ipv4.buildIpResponse(req, icmpPkt, protocol=Ipv4.ICMP_PROTOCOL)
    resp  = ethernet.buildResponse(req, ipPkt)

    return resp


