# -*- coding: utf-8 -*-
"""
protocols.ethernet
~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from protocols import base
from pox.lib.packet.ethernet import ethernet as Ethernet
from pox.lib.packet.ethernet import ETHER_ANY

log = logging.getLogger('protocols.ethernet')
name = Ethernet.__name__
OsiLayer = 2


def extract(packet):
    pkt = base.extract(packet, Ethernet)
    return pkt


def extractPayload(packet):
    if not isinstance(packet, Ethernet):
        packet = extract(packet)
        if packet is None:
            return None

    return packet.next


def buildRequest(src=ETHER_ANY, dst=ETHER_ANY, typ=Ethernet.IP_TYPE, payload=''):
    packet        = Ethernet()
    packet.src    = src
    packet.dst    = dst
    packet.type   = typ
    packet.next   = payload
    # TODO build packet.arr
    packet.parsed = True

    return packet


def buildResponse(req, packet, **kwargs):
    resp      = Ethernet()
    resp.src  = req.dst
    resp.dst  = req.src
    resp.type = req.type
    resp.set_payload(packet)

    if len(kwargs) != 0:
        for key in kwargs.keys():
            if key not in resp.__dict__.keys():
                continue

            setattr(resp, key, kwargs[key])

    resp.parsed = True

    return resp


