# -*- coding: utf-8 -*-
"""
scn.scnTopology
~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging

from pox.core import core
from pox.openflow.topology import OpenFlowSwitch
from pox.topology import topology
from scnOFTopology import ScnOpenFlowSwitch

log = core.getLogger()


class ScnTopology(topology.Topology):

    def getSwitchs(self):
        t = OpenFlowSwitch
        return self.getEntitiesOfType(t=t)


    def getOFS(self, dpid):
        entity = self.getEntityByID(dpid)
        if not entity:
            return

        if not isinstance(entity, ScnOpenFlowSwitch):
            log.warn("Entity with id [%d] found but it's not a swith..." % dpid)
            return

        return entity


    def getOFP(self, dpid, inport):
        ofs = self.getOFS(dpid)
        if not ofs:
            return None

        return ofs.getOFPort(inport)


    def getHost(self, o):
        assert isinstance(o, EthAddr) or isinstance(o, IPAddr)
        switchs = self.getSwitchs()
        for ofs in switchs:
            h = ofs.getHost(o)
            if h:
                return h


    def getPossibleLinks(self, sw1, sw2):
        if isinstance(sw1, (int, long)):
            dpid = sw1
            sw1 = self.getOFS(dpid)
            if not sw1:
                log.warn("Unknown switch %d" % dpid)
                return

        if isinstance(sw2, (int, long)):
            dpid = sw2
            sw2 = self.getOFS(dpid)
            if not sw2:
                log.warn("Unknown switch %d" % dpid)
                return

        if sw1 == sw2:
            log.debug("Same switch")
            return


def launch():

    core.registerNew(ScnTopology)

    from scn.scnOFTopology import launch
    launch()

