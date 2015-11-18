# -*- coding: utf-8 -*-
"""
protocols.udp
~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from protocols import base
from protocols import ethernet
from protocols import ipv4
from protocols import icmp

from pox.lib.packet.ethernet import ethernet as Ethernet
from pox.lib.packet.icmp import CODE_UNREACH_PORT
from pox.lib.packet.ipv4 import ipv4 as Ipv4
from pox.lib.packet.udp import udp as Udp

log = logging.getLogger('protocols.udp')
name = Udp.__name__
OsiLayer = 4


def extract(packet):
    udpPkt = base.extract(packet, Udp)
    return udpPkt


def extractSrcPort(packet):
    if not isinstance(packet, Udp):
        packet = extract(packet)
        if packet is None:
            return None

    return packet.srcport


def extractDstPort(packet):
    if not isinstance(packet, Udp):
        packet = extract(packet)
        if packet is None:
            return None

    return packet.dstport


def extractSrc(packet):
    ip = ipv4.extractSrcIp(packet)
    port = extractSrcPort(packet)
    return (ip, port)


def extractDst(packet):
    ip = ipv4.extractDstIp(packet)
    port = extractDstPort(packet)
    return (ip, port)


def extractPayload(packet):
    if not isinstance(packet, Udp):
        packet = extract(packet)
        if packet is None:
            return None

    if packet.payload == '':
        try:
            start = packet.hdr_len
            length = packet.len - packet.hdr_len
            return packet.arr[start:length].tostring()
        except:
            log.error('Unable to get udp payload')
            return
    else:
        start = 0
        length = packet.payload_len
        return packet.payload


def checksum(packet):
    if not isinstance(packet, Udp):
        packet = extract(packet)
        if packet is None:
            return 0

    if packet.__dict__.has_key('arr'):
        return packet.checksum()

    udpHdr = packet.hdr(packet.payload)

    if packet.next is None:
        nextHdr = ''
    elif isinstance(packet.next, str):
        nextHdr = packet.next
    else:
        nextHdr = packet.next.hdr('')

    s = '%s%s' % (udpHdr, nextHdr)

    udpPkt = Udp(raw=s, prev=packet.prev)
    udpPkt.next = nextHdr

    return udpPkt.checksum()


def buildUdpResponse(req, packet, **kwargs):
    reqUdp = req.find(name)
    if reqUdp is None:
        return None

    resp = Udp()
    resp.srcport = reqUdp.dstport
    resp.dstport = reqUdp.srcport

    if isinstance(packet, str):
        resp.len += len(packet)
    else:
        resp.len += len(packet.hdr(packet.payload))

    resp.set_payload(packet)

    return resp


def buildResponse(req, packet, payload=''):
    resp = None
    if payload is None:
        payload = ''

    udpPkt = buildUdpResponse(req, packet, payload=payload)
    ipPkt  = ipv4.buildResponse(req, udpPkt, protocol=Ipv4.UDP_PROTOCOL)
    resp   = ethernet.buildResponse(req, ipPkt)

    return resp


def buildRequest(src, dst, payload='', ipId=0):
    udpPkt = Udp()
    udpPkt.srcport = src[2]
    udpPkt.dstport = dst[2]
    if isinstance(payload, str):
        udpPkt.len += len(payload)
    else:
        udpPkt.len += len(payload.hdr())
    udpPkt.set_payload(payload)
    udpPkt.parsed = True

    ipPkt = Ipv4()
    ipPkt.flags = Ipv4.DF_FLAG
    ipPkt.srcip = src[1]
    ipPkt.dstip = dst[1]
    ipPkt.id = ipId
    ipPkt.protocol = Ipv4.UDP_PROTOCOL
    ipPkt.set_payload(udpPkt)
    ipPkt.iplen += udpPkt.len
    ipPkt.parsed = True

    udpPkt.csum = checksum(udpPkt)

    ethPkt = Ethernet()
    ethPkt.src = src[0]
    ethPkt.dst = dst[0]
    ethPkt.type = Ethernet.IP_TYPE
    ethPkt.set_payload(ipPkt)
    ethPkt.parsed = True

    return ethPkt


# send icmp dest unreach
def buildDefaultResponse(packet):
    if not extract(packet):
        return

    ipPkt = ipv4.extract(packet)
    if not ipPkt:
        return

    udpPkt = extract(ipPkt)
    if not udpPkt:
        return

    if not udpPkt.next and udpPkt.payload_len > 0:
        udpPkt.next = udpPkt.payload.tostring()

    return icmp.buildUnreachResp(packet, ipPkt, CODE_UNREACH_PORT)

