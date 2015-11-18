# -*- coding: utf-8 -*-
"""
scn.plugins.bwFlowBalancing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import logging
import datetime
import time

from pox.core import core
from pox.lib.recoco import Timer
from pox.lib.packet.ipv4 import ipv4

from scn import routing
from scn.routing import RoutingConditions
from scn.routing import ScnLinks
from scn.plugins.flowBw import *

from operator import attrgetter
from math import ceil

NAME = __file__.split('/')[-1].split('.')[0].split('_')[0]

log = core.getLogger()

BWFLOWBALANCING_PERIOD=15

###############################################################################

class BwFlowBalancing(EventMixin):

    _wantComponents = set(['flowBw'])

#_____________________________________________________________________________#

    def __init__(self):
        core.listenToDependencies(self, self._wantComponents)
        self.running = False
        self.looping = False
        self.handling = False
        self.cablesBw = None
        self.srcKey = None
        self.dstKey = None
        self.automaticMode = False
        self.alwaysOptimization = True

        self.start()

#_____________________________________________________________________________#

    def reboot(self, **kwargs):
        self.running = False

#_____________________________________________________________________________#

    def loaded(self):
        log.debug('loaded')
#_____________________________________________________________________________#

    def start(self):
        if self.running:
            return 'Already running.'

        self.running = True
        if not self.looping:
            self.looping = True
            self.loop()
            return 'Started'

        return 'Already looping.'

#_____________________________________________________________________________#

    def stop(self):
        if not self.running:
            return 'Already stopped.'

        self.running = False
        return 'Stopped.'

#_____________________________________________________________________________#

    def loop(self):
        if not self.running:
            self.looping = False
            return

        self.cablesBw = self.getCablesBw()

        if (not self.handling) and (core.routing.optimizeRequested or self.automaticMode):
            self.handling = True
            core.routing.optimizeRequested = False

            start = time.clock()
            log.info("Handling started.")
            # respect conditions algo
            NGRoutes = self.checkConditions()
            log.info("checkConditions finished. (time;{0:.3f}".format(time.clock() - start))

            # best effort algo
            if NGRoutes or self.alwaysOptimization:
                self.optimizeFlows()
                log.info("optimizeFlows finished. (time;{0:.3f}".format(time.clock() - start))

            # result confirmation of best effort algo
            NGRoutes = self.respectBandwidthReservation(NGRoutes)
            if NGRoutes and (not core.routing.optimizeRequested):
                routes = map(lambda route: route.cookie, NGRoutes)
                log.debug("No respects. %s" % routes)
                core.middleware.push_request_optimize_failure(routes)

            log.info("Handling finished. (time;{0:.3f}".format(time.clock() - start))
            self.handling = False

        if not self.running:
            self.looping = False
            return

#_____________________________________________________________________________#

    def checkConditions(self):
        routes = core.routing.routes.values()

        bwReservedRoutes = []

        #We selet only route with a Bandwidth condition
        for route in routes:
            if route.conditions:
                if RoutingConditions.fix in route.conditions.keys():
                    continue

                if RoutingConditions.bandwidth in route.conditions.keys():
                    bwReservedRoutes.append(route)

        if len(bwReservedRoutes) == 0:
            return []

        return self.respectBandwidthReservation(bwReservedRoutes)

#_____________________________________________________________________________#

    def respectBandwidthReservation(self, routes):

        #log.debug('respectBandwidthReservation')
        returnVal = []

        for route in routes:
            log.debug("\n============================================================\n")
            log.debug('respectBandwidthReservation Cookie %d' % (route.cookie))

            if self.isBandwidthRespected(route):
                log.debug('Cookie %d: Reserved Bandwidth is respected' % (route.cookie))
                continue

            returnVal.append(route)

            log.debug('Cookie %d: Reserved Bandwidth not respected, we have to create a new route' % route.cookie)

            # change route and respect bandwidth
            avoidVias = [route.links]

            while True:
                candidate = self.getMinBwVias(route.links.firstSwitch().dpid,
                                              route.links.lastSwitch().dpid,
                                              route.conditions[RoutingConditions.bandwidth],
                                              avoidVias = avoidVias
                                             )
                if not candidate:
                    log.warn('Could not find a better route')
                    break

                # check if changing to candidate route would have a negative
                # impact on other routes conditions
                if self.isNewRouteNuisanceForBandwidthReservation(route, candidate):
                    log.debug('Candidate route is a nuisance, check a new one')
                    avoidRoutes.append(candidate)
                    continue

                # update route
                log.debug('Try to update route')
                self.updateRoute(route, candidate)
                break

        return returnVal

#____________________________________________________________________________#

    def isNewRouteNuisanceForBandwidthReservation(self, route, newRoute):
        currentRouteFlowBW = core.flowBw.flowBws[route.cookie].bw
        for link in newRoute.links:
            theoricalBw = link.getMaxBandwidthTheorical()
            linkBw = self.getSgmtBw(self.cablesBw, (link.dpid1, link.dpid2))

            for cookie in link.cookies:
                r = core.routing.getRoute(cookie)

                if r.conditions is not None and RoutingConditions.bandwidth in r.conditions.keys():
                    reservedBw = r.conditions[RoutingConditions.bandwidth]
                    try:
                        routeFlowBw = core.flowBw.flowBws[r.cookie].bw
                    except KeyError:
                        continue

                    if (theoricalBw - (linkBw - routeFlowBw) + currentRouteFlowBW) < reservedBw:
                        log.debug('SwitchPort %s : not enough bandwidth' % link.ofs2)
                        return True

        return False

#_____________________________________________________________________________#

    # minBw in B/s
    def getMinBwVias(self, srcDpid, dstDpid, minBw, avoidVias=[]):

        ######################################################################################
        ## Dijkstra way to find the possible via
        ######################################################################################
        graph = core.routing.getUsedBwGraph()

        t1 = datetime.datetime.now()
        possibleVia = core.routing.getRoutesDijkstra(srcDpid, dstDpid, graph)
        t2 = datetime.datetime.now()
        dt = t2 - t1
        log.info("[ABL] possibleVia Dijkstra [%s] found in %s" % (possibleVia, str(dt)))

        possiblesVias = []
        candVia = []
        usableVia = True

        for vertex in possibleVia:
            link = core.openflow_discovery.getLinkByDpid(vertex[0],vertex[1])
            linkBwAvaillable = link.getBandwidthAvailable()
            linkBwNonReserved = link.getMaxBandwidthTheorical()

            for cookie in link.cookies:
                route = core.routing.getRoute(cookie)
                if route is not None:
                    if route.conditions is not None and route.conditions[routing.RoutingConditions.bandwidth] is not None:
                        linkBwNonReserved -= route.conditions[routing.RoutingConditions.bandwidth]

            minimumBwAvaillable = min(linkBwAvaillable,linkBwNonReserved)
            if minimumBwAvaillable < minBw:
                log.debug('link %s : not enough bandwidth' % link)
                usableVia = False
                break

            candVia.append(link)

        if candVia != []:
            possiblesVias.append(ScnLinks(candVia))

        ######################################################################################
        ## GetRoutes way to find the possible via
        ######################################################################################
        #possiblesVias = core.routing.getRoutes(srcDpid, dstDpid)

        candidateVia = None

        for via in possiblesVias:
            usableVia = True

            if via in avoidVias: continue

            for link in via.links:
                linkBw = self.getSgmtBw(self.cablesBw, (link.dpid1, link.dpid2))

                if (link.getMaxBandwidthTheorical() - linkBw) < minBw:
                    log.debug('link %s : not enough bandwidth' % link)
                    usableVia = False
                    break

            if not usableVia:
                continue

            candidateVia = via
            break

        return candidateVia

#_____________________________________________________________________________#

    def isBandwidthRespected(self, route):

        log.debug('isBandwidthRespected(%s)' % route.cookie)

        conditions = route.conditions
        if not conditions:
            return True

        reservedBw = conditions.get(RoutingConditions.bandwidth, None)
        if not reservedBw:
            log.debug('no reserved bandwidth')
            return True

        log.debug('reservedBw = %.3f' % reservedBw)

        flowBw = core.flowBw.flowBws.get(route.cookie, None)
        if flowBw is None:
            log.error('no flow bandwidth for cookie %s' % route.cookie)
            return True

        currentFlowBw = flowBw.bw
        log.debug('currentFlowBw  = %.3f' % currentFlowBw)

        if currentFlowBw >= reservedBw:
            return True

        linkList = route.links

        if not linkList or len(linkList)==0:
            log.debug('no switch port link list')
            return True

        for link in linkList:
            linkBw = link.getBandwidthUsed()
            log.debug("linkBw = %.3f" % linkBw)

            if linkBw is None:
                log.debug(str(link))
                log.warning('No switch port link bandwidth %s' % link)
                return False

            maxBwTheorical = link.getMaxBandwidthTheorical()
            log.debug('maxBwTheorical  = %.3f' % maxBwTheorical)

            availableFlowBw = maxBwTheorical - (linkBw - currentFlowBw)
            if availableFlowBw < 0:
                # this can happen if switch is on a virtual machine
                availableFlowBw = 0.

            log.debug('availableFlowBw = %.3f' % availableFlowBw)

            if availableFlowBw < reservedBw:
                s = 'BANDWIDTH NOT RESPECTED :'
                s = '%s\ncookie %s' % (s, str(route.cookie))
                s = '%s\nreserved bandwdith : %.2f' % (s, reservedBw)
                s = '%s\ncurrent flow bandwdith : %.2f' % (s, currentFlowBw)
                s = '%s\nswitch port link' % (s)
                s = '%s (switch %d, %s) <->' % (s, link.ofs1.dpid, link.ofp1.name)
                s = '%s (switch %d, %s)' % (s, link.ofs2.dpid, link.ofp2.name)
                s = '%s\nlink currently used bandwidth %.2f' % (s, linkBw)
                s = '%s\nlink available bandwidth %.2f' % (s, availableFlowBw)
                s = '%s\nlink max bandwidth %.2f' % (s, maxBwTheorical)
                s = '%s\nif available bandwidth is 0, DO NOT PANIC, it sometimes happens on virtual machines.' % s
                log.warn(s)
                return False

        return True

    def optimizeFlows(self):

        bws=[]
        try:
            bws = core.flowBw.flowBws.copy()
        except:
            log.warn("FlowBw unloaded!")
            return

        sortedList = sorted(bws.values(),
                            key=attrgetter('bw'),
                            reverse=True
                           )
        for flowBw in sortedList:

            if flowBw.bw < 10**3: # ignore less than 1KB/s
                continue

            route = core.routing.getRoute(flowBw.cookie)
            if not route:
                log.warning('route with cookie %d not found' % flowBw.cookie)
                continue

            conditions = route.conditions
            if not conditions: continue

            b = conditions.get(RoutingConditions.fix, False)
            if b: continue

            log.debug("============================================================")
            log.debug("optimizedFlow on route %s" % route.cookie)

            routeBw = 0
            for link in route.links:
                routeBw += self.getSgmtBw(self.cablesBw, (link.dpid1, link.dpid2))

            if len(route.links) > 0:
                routeBw = routeBw/len(route.links)
            else:
                routeBw = 0

            selectedRoute = route.links

            srcDpid = ScnLinks(route.links).firstSwitch().dpid
            dstDpid = ScnLinks(route.links).lastSwitch().dpid

            ######################################################################################
            ## Dijkstra way to find the possible via
            ######################################################################################
            graph = core.routing.getUsedBwGraph()

            t1 = datetime.datetime.now()
            possibleVia = core.routing.getRoutesDijkstra(srcDpid, dstDpid, graph)
            t2 = datetime.datetime.now()
            dt = t2 - t1
            log.debug("[ABL] possibleVia Dijkstra [%s] found in %s" % (possibleVia, str(dt)))

            possiblesVias = []
            candidateVia = []
            usableVia = True

            for vertex in possibleVia:
                link = core.openflow_discovery.getLinkByDpid(vertex[0],vertex[1])
                log.debug('link = %s' % str(link))
                candidateVia.append(link)

            if candidateVia != []:
                possiblesVias.append(ScnLinks(candidateVia))

            ######################################################################################
            ## GetRoutes way to find the possible via
            ######################################################################################
            #possiblesVias = core.routing.getRoutes(srcDpid, dstDpid)

            for pv in possiblesVias:

                if not pv == selectedRoute:
                    routeBw = 0
                    for link in selectedRoute:
                        routeBw += self.getSgmtBw(self.cablesBw, (link.dpid1, link.dpid2))

                    if len(selectedRoute)>0:
                        routeBw = routeBw/len(selectedRoute)
                    else:
                        routeBw = 0

                # pr = [((1L, 2), (4, 3)), ((4L, 2), (2, 3)), ((2L, 2), (5, 3))]
                # pr = [((1L, 1), (5, 4))]
                # route.portList = [[(1L, None), (1L, 1)], [(5L, None), (5L, 6)]]

                s="pv :"
                for link in pv:
                        s = "%s (%s<->%s)" % (s, link.dpid1, link.dpid2)

                log.debug("%s" % s)

                s="route.links :"
                for link in selectedRoute:
                        s = "%s (%s<->%s)" % (s, link.dpid1, link.dpid2)

                log.debug("%s" % s)

                if pv == selectedRoute:
                    log.debug('pv == route')
                    continue

                pvBw = 0
                for link in pv:
                    pvBw += self.getSgmtBw(self.cablesBw, (link.dpid1, link.dpid2))

                if len(pv)>0:
                    pvBw = pvBw/len(pv)
                else:
                    pvBw = 0

                if routeBw <= pvBw:
                    continue

                oldM = routeBw
                a    = routeBw - flowBw.bw
                b    = pvBw + flowBw.bw
                newM = max(a, b)
                gain = oldM - newM

                if gain <= 0:
                    continue

                log.debug('')
                log.debug('routeBw        = %15.2f' % (routeBw))
                log.debug('flowBw.bw      = %15.2f' % (flowBw.bw))
                log.debug('pvBw           = %15.2f' % (pvBw))
                log.debug('oldM           = %15.2f' % (oldM))
                log.debug('a              = %15.2f' % (a))
                log.debug('b              = %15.2f' % (b))
                log.debug('newM           = %15.2f' % (newM))
                log.debug('gain           = %15.2f' % (gain))

                if routeBw!= 0:
                    log.debug('gain percent   = %15.2f%%' % (100.*gain/routeBw))

                log.debug('0.05*(routeBw) = %15.2f' % (routeBw * 0.05))

                if gain <= routeBw * 0.05:
                    continue

                log.debug('FOUND A BETTER ROUTE for route with cookie %d' % route.cookie)

                # check if this new route will have a negative impact
                # on route with conditions
                if self.isNewRouteNuisanceForBandwidthReservation(route, pv):
                    log.debug('...BUT! it is a nuisance for another route (because of bandwidth reservation)')
                    continue

                # update route
                self.updateRoute(route, pv)
                selectedRoute = pv

#______________________________________________________________________________#

    def updateRoute(self, oldRoute, newVia):

        # update route
        path = oldRoute.path
        s="newVia :"
        for link in newVia:
            s = "%s (%s<->%s)" % (s, link.dpid1, link.dpid2)

        log.debug("%s" % s)

        kwargs = {}
        kwargs['srcdpid'] = oldRoute.links.firstSwitch().dpid
        kwargs['srcip'] = path.src
        kwargs['dstip'] = path.dst
        kwargs['via'] = newVia
        kwargs['dstdpid'] = oldRoute.links.lastSwitch().dpid
        kwargs['outport'] = oldRoute.lastEntity.port
        kwargs['ipProtocol'] = ipv4.TCP_PROTOCOL
        kwargs['tos'] = path.tos
        kwargs['cookie'] = oldRoute.cookie
        if oldRoute.conditions:
            kwargs[RoutingConditions.MainKey] = oldRoute.conditions

        core.routing.createBiRoute(path.src, path.dst, **kwargs)

        # update cablesBw
        oldRouteFlowBw = core.flowBw.flowBws[oldRoute.cookie]

        # We subtract the right oldRoute bandwidth on the link
        for link in oldRoute.links:
            val = self.getSgmtBw(self.cablesBw, (link.dpid1, link.dpid2))
            val -= oldRouteFlowBw.bw
            self.setSgmtBw(self.cablesBw, (link.dpid1, link.dpid2), val)

        # We add the average oldRoute bandwidth on the link of newVia
        for link in newVia:
            val = self.getSgmtBw(self.cablesBw, (link.dpid1, link.dpid2))
            val += oldRouteFlowBw.bw
            self.setSgmtBw(self.cablesBw, (link.dpid1, link.dpid2), val)


    def getSgmtBw(self, d, (srcdpid, dstdpid)):
        val = 0.
        key = (srcdpid, dstdpid)
        try:
            val = d[key]
        except KeyError: pass
        return val


    def setSgmtBw(self, d, (srcdpid, dstdpid), bw):
        key = (srcdpid, dstdpid)
        try:
            d[key] = bw
        except KeyError: pass


    def getCablesBw(self):
        d = {} # [ (srcdpid, dstdpid): bw, ...]
        links = core.openflow_discovery.getAllLinks()
        for link in links:
            srcdpid = link.dpid1
            dstdpid = link.dpid2
            d[(srcdpid, dstdpid)] = link.getBandwidthUsed()

        return d


    def printCablesBw(self, msg):
        s="%s" % msg
        if self.cablesBw is None: return
        for a,b   in self.cablesBw:
            s="%s\nd[%s:%s]=%s" % (s,a,b, self.cablesBw[(a,b)])
        log.debug("%s" % s)

#==============================================================================#
#                                   Commands                                   #
#==============================================================================#

    def help_startBwFlowBalancing(self):
        msg = 'start flow bandwidth balancing'
        return msg


    def do_startBwFlowBalancing(self, arg):
        return self.start()

#______________________________________________________________________________#
    def help_stopBwFlowBalancing(self):
        msg = 'stop flow bandwidth balancing'
        return msg


    def do_stopBwFlowBalancing(self, arg):
        return self.stop()

#==============================================================================#
#                                   Launcher                                   #
#==============================================================================#
def launch(**kwargs):
    if core.hasComponent(NAME):
        return None

    comp = BwFlowBalancing()
    core.register(NAME, comp)

    # timer set to execute every BWFLOWBALANCING_PERIOD seconds
    period = kwargs.get('BWFLOWBALANCING_PERIOD', BWFLOWBALANCING_PERIOD)
    Timer(period, comp.loop, recurring=True)

    return comp

