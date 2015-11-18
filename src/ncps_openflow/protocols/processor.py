# -*- coding: utf-8 -*-
"""
protocols.processor
~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *

from protocols import base
from protocols import ethernet
from protocols import arp
from protocols import icmp
from protocols import ipv4
from protocols import tcp
from protocols import udp
from protocols import dhcp

log = core.getLogger()

_osiLayers = {
     7: [dhcp],
     6: [],
     5: [],
     4: [tcp, udp],
     3: [icmp, ipv4],
     2: [arp, ethernet],
     1: [],
             }


def getOsiLayer(protocol):
    for layer, protList in _osiLayers.items():
        if protocol in protList:
            return layer
    # Unknown protocol
    return 0



class Processor(EventMixin):

    osiLayers = {}


    def __init__(self):
        log.debug("Processor")
        self.listenTo(core.openflow)

        # {dpid: connection, ...}
        self.switchs = {}

        # { protocol : [client1, client2, ...], ... }
        self.clients = {}
        # { protocol : [server1, server2, ...], ... }
        self.servers = {}


    # a switch connected
    def _handle_ConnectionUp(self, event):
        self.switchs[event.dpid] = event.connection


    # a switch disconnected
    def _handle_ConnectionDown(self, event):
        del self.switchs[event.dpid]


    def _handle_PacketIn (self, event):
        packet = event.parsed # This is the parsed packet data.
        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return

        self.process(event)


    def test(self):
        arp = packet.find('arp')
        if not arp: return
        packet.src = '\x01\x02\x03\x04\x05\x06'
        self.sendPacket(packet, dpid, port)


    def sendPacket(self, packet, dpid, port):
        msg = of.ofp_packet_out()
        try:
            msg.data = packet
        except :
            log.debug("sendPacket, dpid %s, port %s, %s" % (str(dpid), str(port), str(packet)))

        # Add an action to send to the specified port
        action = of.ofp_action_output(port = port)
        msg.actions.append(action)

        # Send message to switch
        sw = None
        sw = self.switchs.get(dpid)
        if not sw:
            log.warn("No switch with dpid %d was registered" % dpid)
            return

        sw.send(msg)


    def addClient(self, client):
        """ client connection handler を追加する """
        client.finishedCb = self.delClient
        client.sendCb = self.sendPacket
        self._addApplication(self.clients, client)


    def delClient(self, client):
        """ client connection handler を削除する """
        self._delApplication(self.clients, client)


    def addServer(self, server, needSend=False):
        """ serverを追加する """
        if needSend:
            server.sendCb = self.sendPacket

        server.finishedCb = self.delServer
        self._addApplication(self.servers, server)


    def delServer(self, server):
        """ serverを削除する """
        self._delApplication(self.servers, server)


    def _addApplication(self, d, app):
        """ アプリを追加する。
            d: dictionnary (self.servers or self.clients)
            app: client or server
            app.protocol: nox.lib.packetの下にあるclassであるはず """
        try:
            appList = d[app.protocol]
        except KeyError:
            appList = []
            d[app.protocol] = appList

        if app not in appList:
            appList.append(app)

        self._addProtocolLayer(app.agent)


    def _delApplication(self, d, app):
        """ アプリを削除する """
        try:
            appList = d[app.protocol]
        except KeyError:
            return

        try:
            appList.remove(app)
            if len(appList) == 0:
                del d[app.protocol]
        except ValueError:
            return
        except:
            pass

        self._delProtocolLayer(app.agent)


    def _addProtocolLayer(self, protocol):
        layer = getOsiLayer(protocol)
        if layer in self.osiLayers.keys():
            l = self.osiLayers[layer]
            if protocol in l: return
            l.append(protocol)
            return

        l = []
        l.append(protocol)
        self.osiLayers[layer] = l


    def _delProtocolLayer(self, protocol):
        serverL = None
        for k,v in self.servers.items():
            if k.__name__ != protocol.name: continue
            serverL = v
            break

        clientL = None
        for k,v in self.clients.items():
            if k.__name__ != protocol.name: continue
            clientL = v
            break

        sLen = 0 if serverL is None else len(serverL)
        cLen = 0 if clientL is None else len(clientL)
        if sLen != 0 or cLen != 0:
            return

        layer = getOsiLayer(protocol)

        try:
            del self.osiLayers[layer]
        except:
            pass


    def process(self, event):
        packet = event.parsed
        dpid = event.dpid
        port = event.port

        try:
            if not packet.parsed:
                log.error("unknown packet")
                return None
        except:
            log.error("unknown object")
            return None

        # [7, 6, 5, 4, 3, 2, 1, 0]
        for layer in xrange(7,0-1,-1):
            protList = []
            try:
                protList = self.osiLayers[layer]
            except:
                pass

            for prot in protList:
                parsed, resp = self.tryProtocol(dpid, port, packet, prot)

                if not parsed:
                    continue

                if resp is None:
                    continue

                self.sendPacket(resp, dpid, port)

        return


    def tryProtocol(self, dpid, port, packet, prot):
        parsed = False
        resp   = None

        parsed, pkt = base.parse(packet, prot.name)
        if not parsed:
            return (parsed, resp)

        try:
            clientList = self.clients[pkt.__class__]
        except:
            clientList = None

        if clientList is not None:
            for client in clientList:
                try:
                    resp = client.processPacket(packet, dpid, port)
                    if resp:
                        return (parsed, resp)
                except Exception as inst:
                    log.exception(inst)

        try:
            serverList = self.servers[pkt.__class__]
        except:
            serverList = None

        if serverList is not None:
            for server in serverList:
                try:
                    resp = server.processPacket(packet, dpid, port)
                    if resp:
                        return (parsed, resp)
                except Exception as inst:
                    log.exception(inst)

        return (parsed, resp)


def launch():

    from log.level import launch
    launch(DEBUG=True)

    from samples.pretty_log import launch
    launch()

    from setPacketSize import launch
    launch()

    p = Processor()
    core.register('protocols', p)

