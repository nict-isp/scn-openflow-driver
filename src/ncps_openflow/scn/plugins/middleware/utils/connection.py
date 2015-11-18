# -*- coding: utf-8 -*-
"""
scn.plugins.middleware.utils.connection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from pox.core import core
from protocols.application.tcp import OF_TcpClient, OF_TcpServer
from protocols.application.udp import OF_UdpServer

log = core.getLogger()

class MWServer:
    """Middleware original Server Base.
    """
    agent = None

    def __init__(self, callback):
        self.callback = callback


    def payload_received(self, packet, payload, dpid, port):
        """handler when Server recieved data.
        """
        if not self.callback:
            return

        node = self.get_node(packet, dpid, port)
        if not node:
            return

        self.callback(node, payload)


    def get_node(self, packet, dpid, port):
        """get ScnOpenFlowHost instance.
           ScnOpenFlowHost has attribute named ofp(=ScnOpenFlowPort)
           ScnOpenFlowPort has attribute named ofs(=ScnOpenFlowSwitch)
        """
        switch = core.topology.getOFS(dpid)
        if not switch:
            log.warn('unknown switch [%s]' % dpid)
            return None

        ofp = switch.getOFPort(port)
        if not ofp:
            log.warn('unknown switch port [%s:%s]' % (dpid, port))
            return None

        srcip, srcport = self.agent.extractSrc(packet)
        return ofp.getHostByIp(srcip)


class MWUdpServer(OF_UdpServer, MWServer):
    """Middleware original UDP Server.
    """

    def __init__(self, callback, lport):
        MWServer.__init__(self, callback)
        OF_UdpServer.__init__(self, lport)


    def matches(self, packet, dpid, port):
        log.debug('Packet IN? dpid = %s, port = %s' % (str(dpid), str(port)))
        node = self.get_node(packet, dpid, port)
        log.debug('get_node %s' % str(node))
        if not node:
            log.warn("not node [packet:%s, dpid:%s, port:%s]" % (packet, dpid, port))
            return False

        args = [self, packet, dpid, port]
        return OF_UdpServer.matches(*args)


    def payloadReceived(self, packet, payload, dpid, port):
        log.info('recieve payload dpid=%s, port=%d, %s' % (str(dpid), int(dpid), str(payload)))
        MWServer.payload_received(self, packet, payload, dpid, port)


class MWTcpServer(OF_TcpServer, MWServer):
    """Middleware original TCP Server.
    """

    DELIMITER = '\\r\\n\\r\\n'

    def __init__(self, callback, lport):
        self.buffers = {} # {(dpid, port): buffer, }
        MWServer.__init__(self, callback)
        OF_TcpServer.__init__(self, lport)


    def matches(self, packet, dpid, port):
        log.debug('Packet IN? dpid = %s, port = %s' % (str(dpid), str(port)))
        node = self.get_node(packet, dpid, port)
        if not node:
            return False

        args = [self, packet, dpid, port]
        return OF_TcpServer.matches(*args)


    def payloadReceived(self, packet, payload, dpid, port):
        log.info('recieve payload dpid=%s, port=%d, %s' % (str(dpid), int(dpid), str(payload)))
        key = (dpid, port)
        buf = self.buffers.get(key, '')
        buf = '%s%s' % (buf, payload)
        items = buf.split(self.DELIMITER)
        item_len = len(items)
        if item_len == 0:
            self.buffers[key] = ''
            return
        if item_len == 1:
            self.buffers[key] = buf
            return

        for _payload in items[:-1]:
            MWServer.payload_received(self, packet, _payload, dpid, port)

        self.buffers[key] = items[-1]


class MWTcpClient(OF_TcpClient):
    """Middleware TCP Client
    """

    def __init__(self, dpid, port, src, dst, payload):
        log.debug('MWTcpClient, payload = %s' % repr(payload))
        OF_TcpClient.__init__(self, dpid, port, src, dst, payload=payload)


    def connectionEstablished(self):
        self.sendPayload(self.payload, self.dpid, self.port)


    def payloadSent(self, payload, dpid, port):
        log.debug('MWTcpClient, payloadSent, we can close :%s' %repr(payload))
        log.debug("dpid = %d, port = %d" % (dpid, port))
        core.callDelayed(10, self.close)

