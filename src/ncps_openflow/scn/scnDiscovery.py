# -*- coding: utf-8 -*-
"""
scn.scnDiscovery
~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import struct
import time
import pox

from pox.lib.revent               import *
from pox.lib.recoco               import Timer
from pox.lib.packet.ethernet      import LLDP_MULTICAST, NDP_MULTICAST
from pox.lib.packet.ethernet      import ethernet
from pox.lib.packet.lldp          import lldp, chassis_id, port_id, end_tlv
from pox.lib.packet.lldp          import ttl, system_description, basic_tlv
import pox.openflow.libopenflow_01 as of
from pox.lib.util                 import dpidToStr
from pox.core import core
from pox.openflow.discovery import Discovery, LinkEvent, LLDPSender, LINK_TIMEOUT

from collections import namedtuple
from scn.scnOFTopology import ScnLink

LLDP_TTL                               = 120
pox.openflow.discovery.LLDP_SEND_CYCLE = 1.0
TIMEOUT_CHECK_PERIOD                   = 5.0
DOMAIN_NAME_TLV      = 123
OFC_NAME_TLV         = 124
GATEWAY_IP_TLV       = 125
GATEWAY_HW_ADDR_TLV  = 126

log = core.getLogger()


class InterDomainGateway:

  def __init__ (self):
    self.domainName = None
    self.ofcName    = None
    self.ipAddr     = None
    self.hwAddr     = None


  def load_config (self):
    from scn.parser import TOPOLOGY

    self.domainName = core.parser.getValue(TOPOLOGY, 'DOMAINNAME')
    if not self.domainName:
        self.domainName = None
        log.warning('No domain name key in topology section')

    log.debug('domainName = %s' % self.domainName)

    self.ofcName = core.parser.getValue(TOPOLOGY, 'OFCNAME')
    if not self.ofcName:
        self.ofcName = None
        log.warning('No OFC name key in topology section')

    log.debug('ofcName = %s' % self.ofcName)

    gateway = core.parser.getValue(TOPOLOGY, 'INTERDOMAINGW')
    if not gateway:
        gateway = None
        log.warning('No inter domain gateway key in topology section')

    log.debug('interDomainGateway = %s' % gateway)

    self.ipAddr = core.parser.getValue(gateway, 'IP')
    if not self.ipAddr:
        self.ipAddr = None
        log.warning('No inter domain gateway IP key in %s section' % gateway)

    log.debug('Gateway IP = %s' % self.ipAddr)

    self.hwAddr = core.parser.getValue(gateway, 'HWADDR')
    if not self.hwAddr:
        self.hwAddr = None
        log.warning('No inter domain gateway HWADDR key in %s section' % gateway)

    log.debug('Gateway HW address = %s' % self.hwAddr)


  def setGateway (self, domainName, ofcName, ipAddr, hwAddr):
      self.domainName = domainName
      self.ofcName    = ofcName
      self.ipAddr     = ipAddr
      self.hwAddr     = hwAddr


class ScnLLDPSender (LLDPSender):
  """
  Cycles through a list of packets, sending them such that it completes the
  entire list every LLDP_SEND_CYCLE.
  """

  SendItem = namedtuple("ScnLLDPSender",
                      ('dpid','portNum','packet'))

  #NOTE: This class keeps the packets to send in a flat list, which makes
  #      adding/removing them on switch join/leave or (especially) port
  #      status changes relatively expensive. This could easily be improved.

  def __init__ (self, gateway):
      self._packets = []
      self._timer   = None
      self._gateway = gateway


  def addSwitch (self, dpid, ports):
    """ Ports are (portNum, portAddr) """
    self._packets = [p for p in self._packets if p.dpid != dpid]

    for portNum, portAddr in ports:
      if portNum > of.OFPP_MAX:
        # Ignore local
        continue
      self._packets.append(ScnLLDPSender.SendItem(dpid, portNum,
       self.create_discovery_packet(dpid, portNum, portAddr, self._gateway)))

    self._setTimer()


  def addPort (self, dpid, portNum, portAddr):
    if portNum > of.OFPP_MAX: return
    self.delPort(dpid, portNum)
    self._packets.append(ScnLLDPSender.SendItem(dpid, portNum,
     self.create_discovery_packet(dpid, portNum, portAddr, self._gateway)))
    self._setTimer()


  def create_discovery_packet (self, dpid, portNum, portAddr, gateway):
    """ Create LLDP packet """

    discovery_packet = lldp()

    cid = chassis_id()
    # Maybe this should be a MAC.  But a MAC of what?  Local port, maybe?
    cid.fill(cid.SUB_LOCAL, bytes('dpid:' + hex(long(dpid))[2:-1]))
    discovery_packet.add_tlv(cid)

    pid = port_id()
    pid.fill(pid.SUB_PORT, str(portNum))
    discovery_packet.add_tlv(pid)

    ttlv = ttl()
    ttlv.fill(LLDP_TTL)
    discovery_packet.add_tlv(ttlv)

    sysdesc = system_description()
    sysdesc.fill(bytes('dpid:' + hex(long(dpid))[2:-1]))
    discovery_packet.add_tlv(sysdesc)
    discovery_packet = self.addInterdomainInfo(discovery_packet, gateway)
    discovery_packet.add_tlv(end_tlv())

    eth = ethernet()
    eth.src = portAddr
    eth.dst = NDP_MULTICAST
    eth.set_payload(discovery_packet)
    eth.type = ethernet.LLDP_TYPE

    po = of.ofp_packet_out(action = of.ofp_action_output(port=portNum),
                           data = eth.pack())
    return po.pack()


  def addInterdomainInfo(self, packet, gateway):
    discovery_packet = packet

    # Domain Name
    if gateway.domainName != None:
      domainName_tlv          = basic_tlv()
      domainName_tlv.tlv_type = DOMAIN_NAME_TLV
      domainName_tlv.fill(bytes(gateway.domainName))
      discovery_packet.add_tlv(domainName_tlv)

    # OFC Name
    if gateway.ofcName != None:
      ofcName_tlv          = basic_tlv()
      ofcName_tlv.tlv_type = OFC_NAME_TLV
      ofcName_tlv.fill(bytes(gateway.ofcName))
      discovery_packet.add_tlv(ofcName_tlv)

    # Gateway IP
    if gateway.ipAddr != None:
      ipAddr_tlv          = basic_tlv()
      ipAddr_tlv.tlv_type = GATEWAY_IP_TLV
      ipAddr_tlv.fill(bytes(gateway.ipAddr))
      discovery_packet.add_tlv(ipAddr_tlv)

    # Gateway HW address
    if gateway.hwAddr != None:
      hwAddr_tlv          = basic_tlv()
      hwAddr_tlv.tlv_type = GATEWAY_HW_ADDR_TLV
      hwAddr_tlv.fill(bytes(gateway.hwAddr))
      discovery_packet.add_tlv(hwAddr_tlv)

    return discovery_packet


class ScnDiscovery(Discovery):

    @classmethod
    def __equal_dpid(cls, ofp, dpid):
        return ofp.ofs.dpid == dpid


    def __init__ (self, install_flow = True, explicit_drop = True):
        self.explicit_drop = explicit_drop
        self.install_flow = install_flow

        self._dps = set()
        self.adjacency = {} # From Link to time.time() stamp

        self._gateway = InterDomainGateway()
        self._gateway.load_config()

        self._sender = ScnLLDPSender( self._gateway)
        Timer(TIMEOUT_CHECK_PERIOD, self._expireLinks, recurring=True)

        if core.hasComponent("openflow"):
            self.listenTo(core.openflow)
        else:
            # We'll wait for openflow to come up
            self.listenTo(core)


    def getAllLinks(self):
        return self.adjacency.keys()


    def getLink(self, src_ofp, dst_ofp):
        for link in self.getAllLinks():
            if link.src_ofp == src_ofp and link.dst_ofp == dst_ofp:
                return link


    def getLinkByDpid(self, src_dpid, dst_dpid):
        for link in self.getAllLinks():
            if (self.__equal_dpid(link.src_ofp, src_dpid) and
                self.__equal_dpid(link.dst_ofp, dst_dpid)):
                return link


    def _handle_PacketIn (self, event):
        """@override"""
        packet = event.parsed
        if packet.type != ethernet.LLDP_TYPE: return
        if packet.dst != NDP_MULTICAST: return

        if not packet.next:
            log.error("lldp packet could not be parsed")
            return

        assert isinstance(packet.next, lldp)

        if self.explicit_drop:
            if event.ofp.buffer_id != -1:
                log.debug("Dropping LLDP packet %i", event.ofp.buffer_id)
                msg = of.ofp_packet_out()
                msg.buffer_id = event.ofp.buffer_id
                msg.in_port = event.port
                event.connection.send(msg)

        lldph = packet.next
        if  len(lldph.tlvs) < 3 or \
          (lldph.tlvs[0].tlv_type != lldp.CHASSIS_ID_TLV) or\
          (lldph.tlvs[1].tlv_type != lldp.PORT_ID_TLV) or\
          (lldph.tlvs[2].tlv_type != lldp.TTL_TLV):
          log.error("lldp_input_handler invalid lldp packet")
          return

        def lookInSysDesc():
            r = None
            for t in lldph.tlvs[3:]:
                if t.tlv_type == lldp.SYSTEM_DESC_TLV:
                    # This is our favored way...
                    for line in t.next.split('\n'):
                        if line.startswith('dpid:'):
                            try:
                                return int(line[5:], 16)
                            except:
                                pass
                    if len(t.next) == 8:
                        # Maybe it's a FlowVisor LLDP...
                        try:
                            return struct.unpack("!Q", t.next)[0]
                        except:
                            pass
                    return None

        originatorDPID = lookInSysDesc()

        if originatorDPID == None:
            # We'll look in the CHASSIS ID
            if lldph.tlvs[0].subtype == chassis_id.SUB_LOCAL:
                if lldph.tlvs[0].id.startswith('dpid:'):
                    # This is how NOX does it at the time of writing
                    try:
                        originatorDPID = int(lldph.tlvs[0].id.tostring()[5:], 16)
                    except:
                        pass
            if originatorDPID == None:
                if lldph.tlvs[0].subtype == chassis_id.SUB_MAC:
                    # Last ditch effort -- we'll hope the DPID was small enough
                    # to fit into an ethernet address
                    if len(lldph.tlvs[0].id) == 6:
                        try:
                            s = lldph.tlvs[0].id
                            originatorDPID = struct.unpack("!Q",'\x00\x00' + s)[0]
                        except:
                            pass

        if originatorDPID == None:
            log.warning("Couldn't find a DPID in the LLDP packet")
            return

        # if chassid is from a switch we're not connected to, ignore
        if originatorDPID not in self._dps:
            log.info('Received LLDP packet from unconnected switch [%s]' % originatorDPID)
            return

        # grab port ID from port tlv
        if lldph.tlvs[1].subtype != port_id.SUB_PORT:
            log.warning("Thought we found a DPID, but packet didn't have a port")
            return # not one of ours
        originatorPort = None
        if lldph.tlvs[1].id.isdigit():
            # We expect it to be a decimal value
            originatorPort = int(lldph.tlvs[1].id)
        elif len(lldph.tlvs[1].id) == 2:
            # Maybe it's a 16 bit port number...
            try:
                originatorPort  =  struct.unpack("!H", lldph.tlvs[1].id)[0]
            except:
                pass

        if originatorPort is None:
            log.warning("Thought we found a DPID, but port number didn't " + "make sense")
            return

        if (event.dpid, event.port) == (originatorDPID, originatorPort):
            log.warn('Loop detected; received our own LLDP event [(%s:%s)-(%s:%s)]' % (event.dpid, event.port, originatorDPID, originatorPort))
            return

        port = namedtuple("PortTuple",('dpid','port'))
        self.setLink([port(event.dpid, event.port), port(originatorDPID, originatorPort)])

        return EventHalt # Probably nobody else needs this event


    def setLink(self, switchs):
        src_ofp  = core.topology.getOFP(switchs[0].dpid, switchs[0].port)
        dst_ofp = core.topology.getOFP(switchs[1].dpid, switchs[1].port)
        if src_ofp and dst_ofp:
            link = self.getLink(src_ofp, dst_ofp)
            if not link:
                # add
                link = ScnLink(src_ofp, dst_ofp)
                log.info('link detected: %s' % link)
                self.raiseEventNoErrors(LinkEvent, True, link) # TODO where is remove handler?

            self.adjacency[link] = time.time()


    def lookInOriginatorGateway(self, lldph):

        def lookInDomainName():
            for t in lldph.tlvs[3:]:
                if t.tlv_type == DOMAIN_NAME_TLV:
                    return t.next
            return None

        domainName = lookInDomainName()
        log.debug('LLDP originatorDomainName= %s' % domainName)


        def lookInOFCName():
            for t in lldph.tlvs[3:]:
                if t.tlv_type == OFC_NAME_TLV:
                    return t.next
            return None

        ofcName = lookInOFCName()
        log.debug('LLDP originatorOfcName= %s' % ofcName)


        def lookInIPAddr():
            for t in lldph.tlvs[3:]:
                if t.tlv_type == GATEWAY_IP_TLV:
                    return t.next
            return None

        ipAddr = lookInIPAddr()
        log.debug('LLDP originatorGatewayIP= %s' % ipAddr)


        def lookInHWAddr():
            for t in lldph.tlvs[3:]:
                if t.tlv_type == GATEWAY_HW_ADDR_TLV:
                    return t.next
            return None

        hwAddr = lookInHWAddr()
        log.debug('LLDP originatorGatewayHWAddr= %s' % hwAddr)

        gateway = InterDomainGateway()
        gateway.setGateway(domainName, ofcName, ipAddr, hwAddr)

        return gateway


def launch (explicit_drop = False, install_flow = True):
    explicit_drop = str(explicit_drop).lower() == "true"
    install_flow = str(install_flow).lower() == "true"
    core.registerNew(ScnDiscovery, explicit_drop=explicit_drop, install_flow=install_flow)

