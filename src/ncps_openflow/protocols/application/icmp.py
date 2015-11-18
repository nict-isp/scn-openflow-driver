# -*- coding: utf-8 -*-
"""
protocols.application.icmp
~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""


import logging

from protocols.application.application import Server
from protocols.application.application import Client
from protocols import icmp as IcmpAgent
from pox.lib.packet.icmp import icmp

log = logging.getLogger('protocols.application.icmp')


class IcmpServer(Server):

    protocol = icmp
    agent    = IcmpAgent


    def __init__(self):
        Server.__init__(self)


    def getReply(self, packet, *args, **kwargs):
        icmpPkt = self.agent.extractRequest(packet)
        if icmpPkt is None:
            return None

        b = self.isReachable(packet, icmpPkt, *args, **kwargs)
        if b:
            resp = self.agent.buildEcho(packet, icmpPkt)
        else:
            resp = self.agent.buildUnreach(packet, icmpPkt)

        return resp


    def isReachable(self, packet, icmpPkt, *args, **kwargs):
        raise NotImplementedError("should be implemented.")


class OF_IcmpServer(IcmpServer):


    def __init__(self):
        IcmpServer.__init__(self)


    def isReachable(self, packet, icmpPkt, dpid, port):
        raise NotImplementedError("should be implemented.")



class IcmpClient(Client):

    protocol = icmp
    # TODO call finished when finished

