# -*- coding: utf-8 -*-
"""
protocols.ipv4
~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from protocols import base
from pox.lib.packet.ipv4 import ipv4 as Ipv4

log = logging.getLogger('protocols.ipv4')
name = Ipv4.__name__
OsiLayer = 3


def extract(packet):
    ipPkt = base.extract(packet, Ipv4)
    if ipPkt is None:
        return None

    return ipPkt


def extractId(packet):
    if not isinstance(packet, Ipv4):
        packet = extract(packet)
        if packet is None:
            return None

    return packet.id


def extractSrcIp(packet):
    if not isinstance(packet, Ipv4):
        packet = extract(packet)
        if packet is None:
            return None

    return packet.srcip


def extractDstIp(packet):
    if not isinstance(packet, Ipv4):
        packet = extract(packet)
        if packet is None:
            return None

    return packet.dstip


def buildIpResponse(req, packet, **kwargs):
    reqIp = req.find(name)
    if reqIp is None:
        return None

    resp = Ipv4()
    resp.iplen = reqIp.iplen
    resp.frag  = 0
    resp.srcip = reqIp.dstip
    resp.dstip = reqIp.srcip
    resp.id    = resp.id % 65535

    if len(kwargs) != 0 :
        for key in kwargs.keys():
            if key not in resp.__dict__.keys():
                continue

            setattr(resp, key, kwargs[key])

    resp.set_payload(packet)
    resp.parsed = True

    return resp

