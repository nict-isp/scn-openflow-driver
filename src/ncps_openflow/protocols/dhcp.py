# -*- coding: utf-8 -*-
"""
protocols.dhcp
~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging
import struct
from array import array

from protocols import base
from protocols import ethernet
from protocols import ipv4
from protocols import udp
from pox.lib.packet.udp import udp as Udp
from pox.lib.packet.ipv4 import ipv4 as Ipv4
from pox.lib.packet.dhcp import dhcp as Dhcp
from pox.lib.addresses import IPAddr

log = logging.getLogger('protocols.dhcp')
name = Dhcp.__name__
OsiLayer = 7


def extractMsgType(packet):
    msgType = None
    try:
        msgType = packet.options[Dhcp.MSG_TYPE_OPT]
        msgType = struct.unpack('B',msgType)[0]
    except:
        pass

    return msgType


def isRequest(packet):
    return extractRequest(packet) != None


def extractRequestedIp(packet):
    ip = None
    try:
        arr = packet.parsedOptions[Dhcp.REQUEST_IP_OPT]
        ip  = struct.unpack('!I', arr)
        if isinstance(ip, tuple):
            ip = ip[0]
    except:
        pass

    return ip


def extractHostName(packet):
    host = None
    try:
        arr  = dhcpPkt.parsedOptions[Dhcp.HOST_NAME_OPT]
        host = arr.tostring()
    except:
        pass

    return host


def extractClientMac(packet):
    return packet.chaddr


def extractClientIp(packet):
    return packet.ciaddr


def extractRequest(packet):
    dhcpPkt = base.extract(packet, Dhcp)
    if dhcpPkt is None:
        return None

    return extract(dhcpPkt, Dhcp.BOOTREQUEST)


def extractReply(packet):
    dhcpPkt = base.extract(packet, Dhcp)
    if dhcpPkt is None:
        return None

    return extract(dhcpPkt, Dhcp.BOOTREPLY)


def extract(packet, typ=None):
    if not typ:
        return extractRequest(packet)

    if not isinstance(packet, Dhcp):
        return None

    if packet.op != typ:
        return None

    return packet


def buildOfferMsg(req, cip, rip, sip, lease, netmask, bcast, router):
    log.debug('buildOfferMsg')
    resp = buildStandardReply(req, Dhcp.OFFER_MSG, cip, rip, sip, lease, netmask, bcast, router)
    return resp


def buildAckMsg(req, cip, rip, sip, lease, netmask, bcast, router):
    log.debug('buildAckMsg')
    resp = buildStandardReply(req, Dhcp.ACK_MSG, cip, rip, sip, lease, netmask, bcast, router)
    return resp


def buildStandardReply(req, msgType, cip, rip, sip, lease, netmask, bcast, router):
    log.debug('buildStandardReply')

    resp = Dhcp()
    resp.htype    = req.htype
    resp.hlen     = req.hlen
    resp.op       = Dhcp.BOOTREPLY
    resp.hops     = 0
    resp.xid      = req.xid
    resp.yiaddr   = cip
    resp.ciaddr   = 0
    resp.siaddr   = 0
    resp.giaddr   = sip.toUnsigned()
    resp.chaddr   = req.chaddr
    resp.magic    = Dhcp.MAGIC
    resp.options  = array('B')
    parsedOptions = {}

    arr = struct.pack('!B', msgType)
    parsedOptions[Dhcp.MSG_TYPE_OPT] = arr

    arr = rip.toRaw()
    parsedOptions[Dhcp.SERVER_ID_OPT] = arr

    arr = sip.toRaw()
    parsedOptions[Dhcp.SERVER_ID_OPT] = arr

    arr = struct.pack('!I', lease)
    parsedOptions[Dhcp.REQUEST_LEASE_OPT] = arr

    arr = netmask.toRaw()
    parsedOptions[Dhcp.SUBNET_MASK_OPT] = arr

    arr = struct.pack('!I', bcast)
    parsedOptions[Dhcp.BCAST_ADDR_OPT] = arr

    arr = router.toRaw()
    parsedOptions[Dhcp.GATEWAY_OPT] = arr

    resp.options = parsedOptions

    udpLen = Udp.MIN_LEN
    dhcpHdrLen = len(resp.hdr(''))
    padLen = 308 - udpLen - dhcpHdrLen - 1
    arr = array('B', padLen*[0])

    return resp


def buildOptionsArray(d):
    arr = array('B')
    for k,v in d.iteritems():
        l = len(v)
        hdr = array('B', [k, l])
        arr += hdr
        arr += v

    return arr


def buildResponse(req, packet, serverMac, serverIp, **kwargs):
    resp = None

    typ  = extractMsgType(packet)
    if typ == Dhcp.DISCOVER_MSG:
        dhcpPkt = buildOfferMsg(packet, **kwargs)
    elif typ == Dhcp.REQUEST_MSG:
        dhcpPkt = buildAckMsg(packet, **kwargs)
    else:
        return None

    udpPkt = udp.buildUdpResponse(req, dhcpPkt)

    ipKwargs = {}
    ipKwargs['srcip'] = serverIp
    if (isinstance(dhcpPkt.yiaddr, (int, long))):
        ipKwargs['dstip'] = IPAddr(dhcpPkt.yiaddr)
    else:
        ipKwargs['dstip'] = dhcpPkt.yiaddr

    ipKwargs['protocol'] = Ipv4.UDP_PROTOCOL
    ipPkt = ipv4.buildIpResponse(req, udpPkt, **ipKwargs)
    udpPkt.csum = udp.checksum(udpPkt)

    resp = ethernet.buildResponse(req, ipPkt, src=serverMac)

    return resp


