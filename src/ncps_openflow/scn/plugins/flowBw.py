# -*- coding: utf-8 -*-
"""
scn.plugins.flowBw
~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from pox.core import core
from pox.lib.packet.packet_utils import ethtype_to_str
from pox.lib.recoco import Timer
from pox.lib.revent.revent import *
from pox.lib.util import dpidToStr
from scn.plugins.stats import FlowStatsEv
from scn.routing import ScnLinks
from pox.openflow import FlowRemoved

NAME = __file__.split('/')[-1].split('.')[0]
wantComponents = ['stats']

log = core.getLogger()


#______________________________________________________________________________#
#                              Additional classes                              #
#______________________________________________________________________________#

class SegmentBw:

    def __init__(self, dpid, pc, bc, t):
        self.dpid = dpid
        self.pc = pc # packet count
        self.bc = bc # byte count
        self.t = t # time
        self.bw = 0.


    def update(self, pc, bc, t, cookie):

        if t == 0 or t == self.t:
            self.bw = 0
        else:
            self.bw = (bc - self.bc) / float(t-self.t)

        self.pc = pc
        self.bc = bc
        self.t = t


    def __str__(self):
        s = '<%d|' % (self.dpid)
        if 10**3 < self.bw and self.bw < 10**6:
            s = '%s%.3f KB/s' % (s, self.bw/1000.)
        elif 10**6 < self.bw and self.bw < 10**9:
            s = '%s%.3f MB/s' % (s, self.bw/1000000.)
        else:
            s = '%s%.3f B/s' % (s, self.bw)

        return s+">"

#______________________________________________________________________________#

class ScnFlow:

    def __init__(self, cookie):
        self.cookie = cookie
        self.pc = 0.
        self.bc = 0.
        self.bw = 0.
        self.segBws = {} # {dpid: SegmentBw()}


    def update(self, dpid, pc, bc, t, cookie, ident):
        try:
            segBw = self.segBws[dpid]
            segBw.update(pc, bc, t, cookie)

        except KeyError:
            segBw = SegmentBw(dpid, pc, bc, t)

        self.segBws[dpid] = segBw
        self.pc += segBw.pc
        self.bc += segBw.bc
        n = float(len(self.segBws.values()))
        if n == 0:
            return

        self.bw = 0.
        for (bw,dpid) in [(x.bw, x.dpid) for x in self.segBws.values()]:
            self.bw += bw

        self.bw = self.bw / n


    def rawUpdate(self):
        try:
            n = float(len(self.segBws.values()))
            if n == 0:
                return
            self.bw = 0.
            for bw in [x.bw for x in self.segBws.values()]:
                self.bw += bw
            self.bw = self.bw / n
        except:
            return


    def __str__(self):
        s = 'FlowBw:'
        s = '%scookie:%d|' % (s, self.cookie)
        if 10**3 < self.bw and self.bw < 10**6:
            s = '%sbw=%.3f KB/s|' % (s, self.bw/1000.)
        elif 10**6 < self.bw and self.bw < 10**9:
            s = '%sbw=%.3f MB/s|' % (s, self.bw/1000000.)
        else:
            s = '%sbw=%.3f B/s|' % (s, self.bw)
        for segBw in self.segBws.values():
            s = '%s => %s' % (s, str(segBw))

        return s


#______________________________________________________________________________#
#                                  Main class                                  #
#______________________________________________________________________________#

class FlowBw(EventMixin) :

    _wantComponents = set(['stats', 'routing'])

    _eventMixin_events = set([
        FlowStatsEv,
        FlowRemoved
    ])


    def __init__(self):
        core.listenToDependencies(self, self._wantComponents)
        self.flowBws ={}
        self.logFlag = 0
        self.logCookie = 0


    def _handle_FlowStatsEv(self, event):
        stats = event.stats
        dpid  = event.dpid
        ident = event.ident

        for stat in  stats:
            cookie =  stat['cookie']

            pc = stat['packet_count']
            bc = stat['byte_count']
            t = stat['duration_sec']

            try:
                flowBw = self.flowBws[cookie]
            except KeyError:
                flowBw = ScnFlow(cookie)

            flowBw.update(dpid, pc, bc, t, cookie, ident)
            self.flowBws[cookie] = flowBw
            if flowBw.bw > 10**6: # 10MB/s
                log.debug("flowBw = %s" % str(flowBw))


    def _handle_routing_RouteChangedEv(self, event):
        oldRoute = event.oldRoute
        newRoute = event.newRoute
        removedDpidList = []
        newRouteLinks = None

        if (isinstance(newRoute.links, ScnLinks)):
            newRouteLinks = newRoute.links
        else:
            newRouteLinks = ScnLinks(newRoute.links)

        for link in oldRoute.links:
            if not newRouteLinks.containSwitch(link.ofs1):
                if link.dpid1 not in removedDpidList:
                    removedDpidList.append(link.dpid1)
            if not newRouteLinks.containSwitch(link.ofs2):
                if link.dpid2 not in removedDpidList:
                    removedDpidList.append(link.dpid2)

        for i in removedDpidList:
            log.debug("delete self.flowBws[%s].segBws[%s]" % (oldRoute.cookie, i))
            try:
                del self.flowBws[oldRoute.cookie].segBws[i]
            except KeyError:
                log.warn("try to delete a nonexisting key (self.flowBws[%s].segBws[%s])" % (oldRoute.cookie, i))


    def _handle_FlowRemoved(self, event):
        stats = event.stats
        log.critical("FlowRemove %s:%s = %s" % (event.dpid, event.ofp, event.ofp.reason))

#_____________________________________________________________________________#
#                         do_/help_ method for CLI                            #
#_____________________________________________________________________________#

    def help_startFlowBWLog(self):
        msg = 'startFlowBWLog cookie_number'
        return msg


    def do_startFlowBWLog(self, args):
        args = args.split(' ')
        if len(args) != 1:
            return self.help_startFlowBWLog()

        core.flowBw.logCookie =  int(args[0])
        core.flowBw.logFlag = 1

        return "FlowBw's log for cookie %s  started" % (core.flowBw.logCookie)


    def help_stopFlowBWLog(self):
        msg = 'stopFlowBWLog'
        return msg


    def do_stopFlowBWLog(self, args):
        core.flowBw.logFlag = 0
        return "FlowBw's log stoped"


#______________________________________________________________________________#
#                                   Launcher                                   #
#______________________________________________________________________________#

def launch(**kwargs):
    if core.hasComponent(NAME):
        return None

    comp = FlowBw()
    core.register(NAME, comp)

    # attach handlers to listners
    core.stats.addListenerByName("FlowStatsEv", comp._handle_FlowStatsEv)
    comp.listenTo(core.routing)

    return comp

