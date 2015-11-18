# -*- coding: utf-8 -*-
"""
protocols.setPacketSize
~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()


class PacketSize:


    def __init__(self, packetSize):
        self.packetSize = packetSize


    def handle_Conn_Up(self, event):
        event.connection.send(of.ofp_set_config(miss_send_len=self.packetSize))


def launch(packetSize = 2000):
    if core.hasComponent('setPacketSize'):
        return None

    o = PacketSize(packetSize)
    core.openflow.addListenerByName("ConnectionUp", o.handle_Conn_Up)
    core.register('setPacketSize', o)

    return o

