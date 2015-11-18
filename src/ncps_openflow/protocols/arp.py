# -*- coding: utf-8 -*-
"""
protocols.arp
~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from protocols import base
from protocols import ethernet
from pox.lib.packet.ethernet import ETHER_BROADCAST
from pox.lib.packet.ethernet import ethernet as Ethernet
from pox.lib.packet.arp import arp as Arp

name = Arp.__name__
log = logging.getLogger('protocols.arp')

OsiLayer = 2


def extractRequest(packet):
    arpPkt = base.extract(packet, Arp)

    return extractTyp(Arp.REQUEST, arpPkt)


def extractResponse(packet):
    arpPkt = base.extract(packet, Arp)
    if arpPkt is None:
        return None

    return extractTyp(Arp.REPLY, arpPkt)


def extractTyp(typ, packet):
    if not isinstance(packet, Arp):
        return None

    if packet.prototype != Arp.PROTO_TYPE_IP:
        return None

    if packet.opcode != typ:
        return None

    return packet


def extract(packet):
    arpPkt = base.extract(packet, Arp)
    if arpPkt is None:
        return None

    return arpPkt


def extractRequestedIp(packet):
    if not isinstance(packet, Arp):
        packet = extractRequest(packet)
        if packet is None:
            return None
    return packet.protodst


def extractPayload(packet):
    return None


def buildArpRequest(srcMac, srcIp, dstIp):
    arpPkt          = Arp()
    arpPkt.hwsrc    = srcMac
    arpPkt.hwlen    = 6
    arpPkt.protolen = 4
    arpPkt.opcode   = Arp.REQUEST
    arpPkt.protosrc = srcIp
    arpPkt.protodst = dstIp
    arpPkt.parsed   = True

    ethPkt        = Ethernet()
    ethPkt.src    = srcMac
    ethPkt.dst    = ETHER_BROADCAST
    ethPkt.type   = Ethernet.ARP_TYPE
    ethPkt.set_payload(arpPkt)
    ethPkt.parsed = True
    return ethPkt


def buildArpResponse(packet, mac):
    if not isinstance(packet, Arp):
        packet = base.extract(packet, Arp)
        if packet is None:
            return None

    resp          = Arp()
    resp.hwdst    = packet.hwsrc
    resp.protodst = packet.protosrc
    resp.hwsrc    = mac
    resp.protosrc = packet.protodst

    resp.hwtype    = Arp.HW_TYPE_ETHERNET
    resp.hwlen     = 6
    resp.prototype = Arp.PROTO_TYPE_IP
    resp.protolen  = 4
    resp.opcode    = Arp.REPLY

    return resp


def buildResponse(req, packet, mac):
    resp = None

    arpPkt = buildArpResponse(packet, mac)
    if arpPkt is None:
        return None

    resp = ethernet.buildResponse(req, arpPkt, src=mac)

    return resp



