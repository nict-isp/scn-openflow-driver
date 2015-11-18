# -*- coding: utf-8 -*-
"""
scn.scnHostTracker
~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from pox.core import core
from pox.topology.topology import HostJoin
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.arp import arp
from pox.lib.recoco.recoco import Timer
from pox.lib.revent.revent import EventMixin

import pox.openflow.libopenflow_01 as of
import time

from scn.scnOFTopology import ScnOpenFlowHost

log = core.getLogger()

# Times (in seconds) to use for differente timouts:
TIMEOUT_SEC = dict(
  arpAware=60*4,   # Quiet ARP-responding entries are pinged after this
  arpSilent=60*20, # This is for uiet entries not known to answer ARP
  arpReply=4,      # Time to wait for an ARP reply before retrial
  timerInterval=5, # Seconds between timer routine activations
  entryMove=60     # Minimum expected time to move a physical entry
  )
# Good values for testing:
#  --arpAware=15 --arpSilent=45 --arpReply=1 --entryMove=4
# Another parameter that may be used:
# --pingLim=2
STP_TYPE = 57
DEVELOP = True


class Alive (object):
    """ Holds liveliness information for MAC and IP entries
    """
    def __init__ (self, livelinessInterval=TIMEOUT_SEC['arpAware']):
        self.lastTimeSeen = time.time()
        self.interval = livelinessInterval


    def expired (self):
        if DEVELOP:
            #TODO CAUTION!!!  ONLY FOR TEST
            return False
        else:
            return time.time() > self.lastTimeSeen + self.interval


    def refresh (self):
        self.lastTimeSeen = time.time()


class PingCtrl (Alive):
    """ Holds information for handling ARP pings for hosts
    """
    # Number of ARP ping attemps before deciding it failed
    pingLim = 3

    def __init__ (self):
        Alive.__init__(self, TIMEOUT_SEC['arpReply'])
        self.pending = 0


    def sent (self):
        self.refresh()
        self.pending += 1


    def failed (self):
        return self.pending > PingCtrl.pingLim


    def received (self):
        # Clear any pending timeouts related to ARP pings
        self.pending = 0


class IpEntry (Alive):
    """
    This entry keeps track of IP addresses seen from each MAC entry and will
    be kept in the macEntry object's ipAddrs dictionary. At least for now,
    there is no need to refer to the original macEntry as the code is organized.
    """
    def __init__ (self, hasARP):
        if hasARP:
            Alive.__init__(self, TIMEOUT_SEC['arpAware'])
        else:
            Alive.__init__(self, TIMEOUT_SEC['arpSilent'])
        self.hasARP = hasARP
        self.pings = PingCtrl()


    def setHasARP (self):
        """
        set ARP feature.
        """
        if not self.hasARP:
            self.hasARP = True
            self.interval = TIMEOUT_SEC['arpAware']


class MacEntry (Alive):
    """
    Not strictly an ARP entry.
    When it gets moved to Topology, may include other host info, like
    services, and it may replace dpid by a general switch object reference
    We use the port to determine which port to forward traffic out of.
    """
    def __init__ (self, dpid, port, macaddr):
        Alive.__init__(self)
        self.dpid = dpid
        self.port = port
        self.macaddr = macaddr
        self.ipAddrs = {}


    def __str__(self):
        return "%s %s %s" % (str(self.dpid), str(self.port), str(self.macaddr))


    def __eq__ (self, other):
        if type(other) == type(None):
            return type(self) == type(None)
        elif type(other) == tuple:
            return (self.dpid, self.port, self.macaddr) == other
        else:
            return (self.dpid, self.port, self.macaddr)     \
                    == (other.dpid, other.port, other.macaddr)


    def __ne__ (self, other):
        return not self.__eq__(other)


class HostTracker (EventMixin):
    """
    Detect joined SCN Node(Host).
      use packet-in only from Node(not from Switch).
      and save mac,ip to entry propery.
    """
    _eventMixin_events = [
        HostJoin,
    ]

    def __init__ (self):

        EventMixin.__init__(self)
        # The following tables should go to Topology later
        self.entryByMAC = {}
        self._timer = Timer(TIMEOUT_SEC['timerInterval'], self.__check_timeouts__, recurring=True)
        core.openflow.addListenerByName("PacketIn", self._handle_PacketIn, priority=10000)
        log.info("HostTracker ready")


    # The following two functions should go to Topology also
    def getMacEntry(self, macaddr):
        """
        find MacEntry from self property.
        """
        result = None
        if macaddr and macaddr in self.entryByMAC:
            result = self.entryByMAC[macaddr]
        else:
            log.debug("No Entry in self.entryByMAC[%s]|%s" % (macaddr, self.entryByMAC))

        return result


    @classmethod
    def sendPing(cls, macEntry, ipAddr):
        """
        send Ping msg to switch.
        """
        req = arp() # Builds an "ETH/IP any-to-any ARP packet
        req.opcode = arp.REQUEST
        req.hwdst = macEntry.macaddr
        req.protodst = ipAddr
        # src is ETHER_ANY, IP_ANY
        eth = ethernet(type=ethernet.ARP_TYPE, src=req.hwsrc, dst=req.hwdst)
        eth.set_payload(req)

        log.debug("%i %i sending ARP REQ to %s %s",
                macEntry.dpid, macEntry.port, str(req.hwdst), str(req.protodst))

        msg = of.ofp_packet_out(data = eth.pack(),
                               action = of.ofp_action_output(port = macEntry.port))
        if core.openflow.sendToDPID(macEntry.dpid, msg.pack()):
            ipEntry = macEntry.ipAddrs[ipAddr]
            ipEntry.pings.sent()
        else:
            # macEntry is stale, remove it.
            log.debug("%i %i ERROR sending ARP REQ to %s %s", macEntry.dpid, macEntry.port, str(req.hwdst), str(req.protodst))
            del macEntry.ipAddrs[ipAddr]

        return


    @classmethod
    def getSrcIPandARP(cls, packet):
        """
        This auxiliary function returns the source IPv4 address for packets that
        have one (IPv4, ARPv4). Returns None otherwise.
        """
        if isinstance(packet, ipv4):
            return ( packet.srcip, False )

        elif isinstance(packet, arp):

            if packet.hwtype == arp.HW_TYPE_ETHERNET and \
               packet.prototype == arp.PROTO_TYPE_IP and \
               packet.protosrc != 0:
                return ( packet.protosrc, True )

        return ( None, False )


    @classmethod
    def updateIPInfo(cls, pckt_srcip, macEntry, hasARP):
        """ If there is IP info in the incoming packet, update the macEntry
        accordingly. In the past we assumed a 1:1 mapping between MAC and IP
        addresses, but removed that restriction later to accomodate cases
        like virtual interfaces (1:n) and distributed packet rewriting (n:1)
        """
        if pckt_srcip in macEntry.ipAddrs:
            # that entry already has that IP
            ipEntry = macEntry.ipAddrs[pckt_srcip]
            ipEntry.refresh()
        else:
            # new mapping
            ipEntry = IpEntry(hasARP)
            macEntry.ipAddrs[pckt_srcip] = ipEntry
            log.info("Learned %s got *IP* %s", str(macEntry), str(pckt_srcip) )
        if hasARP:
            ipEntry.pings.received()


    def _handle_GoingUpEvent (self, event):
        """
        TODO write!
        """
        log.debug("_handle_GointUpEvent : %s" % str(event))
        self.listenTo(core.openflow)


    def _handle_PacketIn (self, event):
        """
        Populate MAC and IP tables based on incoming packets.
        Handles only packets from ports identified as not switch-only.
        If a MAC was not seen before, insert it in the MAC table;
        otherwise, update table and enry.
        If packet has a source IP, update that info for the macEntry (may require
        removing the info from antoher entry previously with that IP address).
        It does not forward any packets, just extract info from them.
        """
        dpid = event.connection.dpid
        inport = event.port
        packet = event.parse()
        if not packet.parsed:
            log.debug("%i %i ignoring unparsed packet", dpid, inport)
            return

        if packet.type in (ethernet.LLDP_TYPE, STP_TYPE):
            return

        # This should use Topology later
        if core.openflow_discovery.isSwitchOnlyPort(dpid, inport):
            # No host should be right behind a switch-only port
            log.debug("%i %i ignoring packetIn at switch-only port", dpid, inport)
            return

        (macEntry, isLearn) = self.registerMacEntry(dpid, inport, packet)
        (pckt_srcip, hasARP) = HostTracker.getSrcIPandARP(packet.next)
        if pckt_srcip != None:
            HostTracker.updateIPInfo(pckt_srcip, macEntry, hasARP)

        if isLearn:
            self.createJoinedHost(dpid, inport, packet.src, pckt_srcip)


    def registerMacEntry(self, dpid, inport, packet):
        """
        Learn or update dpid/port/MAC info.
        return isLearn.
        """
        newMac = False

        macEntry = self.getMacEntry(packet.src)
        if macEntry == None:
            newMac = True
            # there is no known host by that MAC
            # should we raise a NewHostFound event (at the end)?
            macEntry = MacEntry(dpid, inport, packet.src)
            self.entryByMAC[packet.src] = macEntry

            log.info("Learned %s", str(macEntry))

        elif macEntry != (dpid, inport, packet.src):
            # there is already an entry of host with that MAC, but host has moved
            # should we raise a HostMoved event (at the end)?
            log.info("Learned %s moved to %i %i %s", str(macEntry), dpid, inport, packet.src)
            # if there has not been long since heard from it...
            if time.time() - macEntry.lastTimeSeen < TIMEOUT_SEC['entryMove']:
                log.warning("Possible duplicate: %s at time %i, now (%i %i), time %i",
                            str(macEntry), macEntry.lastTimeSeen, dpid, inport, time.time())
            # should we create a whole new entry, or keep the previous host info?
            # for now, we keep it: IP info, answers pings, etc.
            macEntry.dpid = dpid
            macEntry.inport = inport

        macEntry.refresh()
        return (macEntry, newMac)


    def createJoinedHost(self, dpid, inport, mac, pckt_srcip):
        """
        create joined host instance.
        and raise HostJoin Event.
        """

        ofp = core.topology.getOFP(dpid, inport)
        if ofp is None:
            log.warning("OpenFlowPort has not been registered yet, forcing rediscovery.")
            if mac in self.entryByMAC:
                del self.entryByMAC[mac]
            return

        hst = ScnOpenFlowHost(mac, ofp, ipAddr=pckt_srcip)

        # make topology raise an Event
        core.topology.addEntity(hst)
        # add host to ofp
        ofp.addEntity(hst)
        hst.raiseEvent(HostJoin, hst)


    def __check_timeouts__(self):
        for macEntry in self.entryByMAC.values():
            entryPinged = False
            for ip_addr, ipEntry in macEntry.ipAddrs.items():
                if ipEntry.expired():
                    if ipEntry.pings.failed():
                        del macEntry.ipAddrs[ip_addr]
                        log.info("* Entry %s: IP address %s expired", str(macEntry), str(ip_addr) )
                    else:
                        HostTracker.sendPing(macEntry, ip_addr)
                        ipEntry.pings.sent()
                        entryPinged = True

            if macEntry.expired() and not entryPinged:
                log.info("Entry %s expired", str(macEntry))
                # sanity check: there should be no IP addresses left
                if len(macEntry.ipAddrs) > 0:
                    # TODO Bug? can't use ip_addr. writing mistake ip?
                    for ip in macEntry.ipAddrs.keys():
                        log.warning("Entry %s expired but still had IP address %s", str(macEntry), str(ip_addr) )
                        del macEntry.ipAddrs[ip_addr]

                del self.entryByMAC[macEntry.macaddr]


def launch (**kw):
    """
      create and register HostTracker instance.
    """
    name = "scnHostTracker"

    if core.hasComponent(name):
        return core.scnHostTracker

    for key, val in kw.iteritems():
        if key in TIMEOUT_SEC:
            TIMEOUT_SEC[key] = int(val)
            log.warn("Changing timer parameter: %s = %s", key, val)
        elif key == 'pingLim':
            PingCtrl.pingLim = int(val)
            log.warn("Changing ping limit to %s", val)
        else:
            log.warn("Unknown option: %s(=%s)", key, val)

    core.register(name, HostTracker())

