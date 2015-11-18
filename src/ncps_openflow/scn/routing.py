# -*- coding: utf-8 -*-
"""
scn.routing
~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from collections import defaultdict

from pox.core import core
from pox.openflow.flow_table import TableEntry
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *

from pox.lib.addresses import *
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4

from scn.scnOFTopology import ScnOpenFlowHost
from scn.scnOFTopology import ScnOpenFlowPort
from scn.scnOFTopology import ScnOpenFlowSwitch
from scn.scnOFTopology import ScnLink

import datetime
from math import ceil

log = core.getLogger()

NAME         ='routing'
SRCMAC       = 'srcmac'
DSTMAC       = 'dstmac'
SRCDPID      = 'srcdpid'
DSTDPID      = 'dstdpid'
SRCIP        = 'srcip'
DSTIP        = 'dstip'
INPORT       = 'inport'
OUTPORT      = 'outport'
SRCPORT      = 'srcport'
DSTPORT      = 'dstport'
GATEWAY      = 'gateway'
VIA          = 'via'
PROTOCOL     = 'protocol'
IPPROTOCOL   = 'ipProtocol'
TOS          = 'tos'
IDLE_TIMEOUT = 'idle_timeout'
HARD_TIMEOUT = 'hard_timeout'
FORCE_ROUTE  = False


class Path:

    @classmethod
    def create(cls, src, dst, **kwargs):
        if isinstance(dst, EthAddr):
            return MacPath(src, dst, **kwargs)

        if isinstance(dst, (int, long, IPAddr)):
            return IpPath(src, dst, **kwargs)

        if isinstance(dst, (ScnOpenFlowHost)):
            return IpPath(src.ipAddr, dst.ipAddr, **kwargs)

        return None


class MacPath(Path):

    def __init__(self, src, dst, **kwargs):
        self.src = src
        self.dst = dst

    def __hash__(self):
        return hash((self.src, self.dst))

    def __eq__(self, other):
        return (self.src, self.dst) == (other.src, other.dst)

    def __str__(self):
        return "Path:\n[{0}] -> [{1}]\n".format(self.src, self.dst)


class IpPath(Path):

    def __init__(self, src, dst, tos=0, **kwargs):
        self.src = src
        self.dst = dst
        self.tos = tos


    def isOpposite(self, other):
        return (self.src, self.dst, self.tos, \
               ) \
               == \
               (other.dst, other.src, other.tos, \
               )


    def __eq__(self, other):
        return (self.src, self.dst, self.tos, \
               ) \
               == \
               (other.src, other.dst, other.tos, \
               )


    def __hash__(self):
        return hash(
                    (
                     self.src, self.dst, self.tos,
                    )
                   )

    def __str__(self):
        return "Path:\n[{0}] -> [{1}], tos={2}\n".format(self.src, self.dst, self.tos)


class RoutingConditions:

    MainKey   = 'conditions'
    bandwidth = 0x01 # integer
    fix       = 0x02 # boolean


class ScnLinks:

    # should know its bandwidth
    def __init__(self, links=[]):

        # [ ScnLink, ...]
        self.links = links


    def append(self, link):
        assert isinstance(link, Link)
        self.links.append(link)


    def clone(self):
        links = list(self.links)
        return ScnLinks(links)


    def hops(self):
        switchs = []
        for link in self.links:
             if not link.ofs1 in switchs:
                 switchs.append(link.ofs1)
             if not link.ofs2 in switchs:
                 switchs.append(link.ofs2)

        return len(switchs)


    def containSwitch(self, sw):
        for link in self.links:
            if link.ofs1 == sw:
                return True
            if link.ofs2 == sw:
                return True


    def firstSwitch(self):
        if not self.links:
            return
        link = self.links[0]
        if not link:
            return

        return link.ofs1


    def lastSwitch(self):
        if not self.links:
            return
        link = self.links[-1]
        if not link:
            return

        return link.ofs2


    def getGlobalBandwidth(self):
        bw = 0
        for link in self.links:
            bw += link.getBandwidthUsed()
        if len(self.links) > 0:
            bw = bw / len(self.links)

        return bw


    def getMinimalBandwidthAvaillable(self):
        minimalBandwidthAvaillable = self.links[0].getBandwidthAvailable()
        for link in self.links:
            if link.getBandwidthAvailable() < minimalBandwidthAvaillable:
                minimalBandwidthAvaillable = link.getBandwidthAvailable()

        return minimalBandwidthAvaillable


    def __getitem__(self, i):
        return self.links[i]


    def __len__(self):
        return len(self.links)


    def __eq__(self, other):
        if len(self.links)!=len(other):
            return False

        for i in xrange(len(self.links)):
            if self.links[i]!=other[i]:
                return False

        return True


    def __hash__(self):

        liste = []
        for link in self.links:
            liste.append((link.dpid1, link.dpid2))
        return hash(tuple(liste))


    def __str__(self):
        s = '['
        for link in self.links:
            s = '%s%d:%d->%d:%d|' % (s, link.ofs1.dpid,link.ofp1.number,link.ofs2.dpid,link.ofp2.number)

        s = '%s]' % s

        bwAvaillable = self.getGlobalBandwidth()
        if 10**3 < bwAvaillable and bwAvaillable < 10**6:
           s = '%s <Global Bandwidth=%.3f Kbits/s' % (s, (bwAvaillable/1000.))
        elif 10**6 < bwAvaillable and bwAvaillable < 10**9:
           s = '%s <Global Bandwidth=%.3f Mbits/s' % (s, (bwAvaillable/1000000.))
        else:
           s = '%s <Global Bandwidth=%.3f bits/s' % (s, bwAvaillable)

        bwAvaillable = self.getMinimalBandwidthAvaillable()
        if 10**3 < bwAvaillable and bwAvaillable < 10**6:
           s = '%s |Minimal Bandwidth Availlable=%.3f Kbits/s>' % (s, (bwAvaillable/1000.))
        elif 10**6 < bwAvaillable and bwAvaillable < 10**9:
           s = '%s |Minimal Bandwidth Availlable=%.3f Mbits/s>' % (s, (bwAvaillable/1000000.))
        else:
           s = '%s |Minimal Bandwidth Availlable=%.3f bits/s>' % (s, bwAvaillable)

        return s


    def __iter__(self):
        for link in self.links:
            yield link


class Hops:

    def __init__(self, ofs1, ofs2):
        self.ofs1 = ofs1
        self.ofs2 = ofs2
        self.ways = [] # [ ScnLinks, ...]


    def __eq__(self, other):
        if self.ofs1.dpid == other.ofs1.dpid \
             and \
            self.ofs2.dpid == other.ofs2.dpid \
           :
            return True


    def __hash__(self):
        return hash(self.ofs1.dpid, self.ofs2.dpid)


    def getVia(self, condition=None):
        if not condition:
            return self.getShortest()


    def getShortest(self):
        try:
            return self.ways[0]
        except Exception as inst:
            log.exception(inst)


class ScnRoute:

    def __init__(self):
        # XXX Problem :
        #     javascript's JSON.parse can NOT parse large integers
        #     well...it can but it will be trucated i.e. false
        # TODO
        # Check if cookie already exists...if it exists, get a new random number
        self.cookie = -1
        self.path = None

        # RoutingConditions
        self.conditions = None

        # ScnLinks
        self.links = None

        self.firstEntity = None # host, ofprt, switch
        self.lastEntity = None # host, ofprt, switch

        # { ofs: TableEntry, ...}
        self.entries = {}


    def __str__(self):
        s = '<cookie:%s ' % (self.cookie)
        s = '%s|path:%s' % (s, self.path)
        s = '%s|links:%s' % (s, self.links)
        s = '%s|conditions:%s' % (s, self.conditions)

        return s


    def isSameLinks(self, newVia):
        if len(newVia) != len(self.links):
            return False

        for i in range(0,len(newVia)):
            newViaTuple = (newVia[i].ofs1.dpid, newVia[i].ofp1.number, newVia[i].ofs2.dpid, newVia[i].ofp2.number)
            if not self.links[i].compare(newViaTuple):
                return False

        return True


class RouteChangedEv(Event):

    def __init__(self, oldRoute, newRoute):
        Event.__init__(self)
        self.oldRoute = oldRoute
        self.newRoute = newRoute


class RouteDeletedEv(Event):

    def __init__(self, route):
        Event.__init__(self)
        self.route = route


class Routing(EventMixin):

    _eventMixin_events = [
        RouteChangedEv,
        RouteDeletedEv,
    ]

    def __init__(self, forceRoute=False):

        # { cookie: ScnRoute, ...}
        self.routes = {}
        # { cookie: cookie, ...}
        self.route_pair = {}
        # { ipaddr: { dpid: cookie, ...}, ...}
        self.mesh = {}

        # {(dpid1, dpid2): hops, ...}
        self.hops = {}
        self.forceRoute = forceRoute

        core.openflow_discovery.addListenerByName("LinkEvent", self._handle_LinkEvent)

        self.maxCookie = 2**16-1
        self.previousCookie = 0
        self.optimizeRequested = False


    def reserveCookie(self):
        cookies = self.routes.keys()
        for i in xrange(self.previousCookie + 1, self.previousCookie + self.maxCookie):
            newCookie = i % (self.maxCookie + 1)
            if not newCookie:
                continue

            if newCookie not in cookies:
                self.routes[newCookie] = None
                self.previousCookie = newCookie
                return newCookie


    def releaseCookie(self, cookie):
        try:
            del self.routes[cookie]
        except Exception as inst:
            log.exception(inst)


    def checkHops(self, ofs1, ofs2):
        t1 = datetime.datetime.now()
        log.debug("checkHops started (%s-%s)" % (ofs1.dpid, ofs2.dpid))

        dpidSrc=ofs1.dpid
        dpidDst=ofs2.dpid
        switchs = list(core.topology.getSwitchs())
        count =0

        for i in xrange(0, len(switchs)):
            ofs1 = switchs[i]
            for j in xrange(i+1, len(switchs)):
                ofs2 = switchs[j]
                key1 = (ofs1.dpid, ofs2.dpid)
                key2 = (ofs2.dpid, ofs1.dpid)

                try:
                    hops1 = self.hops[key1]
                except KeyError:
                    hops1 = Hops(ofs1, ofs2)
                    self.hops[key1] = hops1

                try:
                    hops2 = self.hops[key2]
                except KeyError:
                    hops2 = Hops(ofs2, ofs1)
                    self.hops[key1] = hops2

                hops1.ways = self.getRoutes(ofs1.dpid, ofs2.dpid)
                self.hops[key1] = hops1

                hops2.ways = self.getRoutes(ofs2.dpid, ofs1.dpid)
                self.hops[key2] = hops2

                count+=len(hops1.ways)+len(hops2.ways)

        t2 = datetime.datetime.now()
        dt = t2 - t1
        log.debug("checkHops finished (%s-%s) for %s switchs in %s [%s entries in hops]" % (dpidSrc, dpidDst, len(switchs), str(dt), count))


    def _handle_LinkEvent(self, event):
        if event.added:
            log.debug("TODO: do something if link added?")
            return

        if event.removed:
            log.debug("TODO: do something if link dead: update routes ")
            pass
        else:
            log.debug("TODO: do something if link dead: update routes ")
            link =  event.link # link= (dpid1","port1","dpid2","port2")
            routeToBeChanged = []
            for route in self.routes.values():
                if link in route.links:
                    routeToBeChanged.append(route)

            if len(routeToBeChanged) > 0:
                for route in routeToBeChanged:
                    path = route.path
                    kwargs = {}
                    kwargs['srcdpid'] = route.links.firstSwitch().dpid
                    kwargs['srcip'] = path.src
                    kwargs['dstip'] = path.dst
                    kwargs['dstdpid'] = route.links.lastSwitch().dpid
                    kwargs['outport'] = route.lastEntity.port
                    kwargs['ipProtocol'] = ipv4.TCP_PROTOCOL
                    kwargs['tos'] = path.tos
                    if route.conditions:
                        kwargs[RoutingConditions.MainKey] = route.conditions

                    self._removeFlows(route)
                    self.createRoute(path.src, path.dst, **kwargs)
                    self._installFlows(route)


    def getRoutes2(self, via=None):
        if via is None:
            return self.routes.values()

        if isinstance(via, ScnLinks):
            routes = []
            for c, r in self.routes.iteritems():
                if r.links == via:
                    routes.append(r)

            return routes


    def getRoute(self, key):
        if isinstance(key, (int, long)):
            return self.routes.get(key, None)

        if isinstance(key, Path):
            for c, r in self.routes.iteritems():
                if r.path == key:
                    return r


    def delPath(self, path):
        for r in self.routes.values():
            if r.path == path:
                self.delRoute(r)

        log.warn('Path %s has been deleted\n' % path)
        return


    def routeExists(self, route):
        r = self.routes.get(route.cookie, None)
        return r


    def addRoute(self, route):
        oldRoute = self.routeExists(route)
        if oldRoute:
            route.cookie = oldRoute.cookie
        else:
            route.cookie = self.reserveCookie()

        for ofs, tabEntry in route.entries.iteritems():
            tabEntry.cookie = route.cookie

        if oldRoute:
            log.info('\nUPDATE ROUTE with cookie %d\n' % oldRoute.cookie)

            #Ask for optimisation on the next loop of bwFlowBalancing
            if (oldRoute.conditions and  route.conditions and oldRoute.conditions[RoutingConditions.bandwidth]!=route.conditions[RoutingConditions.bandwidth]):
                self.optimizeRequested = True

            self.updateRoute(oldRoute, route)
            self.routes[route.cookie] = route
            return

        log.info('\nADD ROUTE with cookie %d\n' % route.cookie)
        for link in route.links:
            link.cookies.append(route.cookie)

        self.routes[route.cookie] = route
        self._installFlows(route)


    def _installFlows(self, route):
        for ofs, tabEntry in route.entries.iteritems():
            ofs.flow_table.install(tabEntry)


    def updateRoute(self, old, new):
        identical = True

        # rules that we have to delete are inside oldRoute
        # and not in newRoute
        for ofs, oldTabEntry in old.entries.iteritems():
            newTabEntry = new.entries.get(ofs, None)
            if not newTabEntry:
                log.debug("%s :[not newTabEntry] delete TabEntry {%s}" % (ofs, oldTabEntry.__class__))
                ofs.flow_table.remove_strict(oldTabEntry)
                identical = False
                continue

            newFlowMod = newTabEntry.to_flow_mod()

            if oldTabEntry.is_matched_by(newFlowMod.match):
                if oldTabEntry.actions != newTabEntry.actions:
                    identical = False
                    log.debug("%s :[actions differs] delete TabEntry {%s}" % (ofs, oldTabEntry.__class__))
                    ofs.flow_table.remove_strict(oldTabEntry)
                continue

            identical = False
            log.debug("%s :[matchs differs] delete TabEntry {%s}" % (ofs, oldTabEntry.__class__))
            ofs.flow_table.remove_strict(oldTabEntry)

        if identical:
            log.debug("route with same rules already exists. Nothing to do here")
            return

        # add or update flow rule
        self._installFlows(new)

        #update Cookie in route.links
        for link in old.links:
            try:
                link.cookies.remove(old.cookie)
            except KeyError:
                log.warn("Try to remove a nonexisting key")
                pass
            except ValueError:
                log.warn("Try to remove a nonexisting key")
                pass

        for link in new.links:
            if new.cookie not in link.cookies:
                    link.cookies.append(new.cookie)

        log.debug("TODO: send event ?")
        log.debug("FlowTableModification should have been launched")

        # send RouteChangedEv
        ev = RouteChangedEv(old, new)
        core.routing.raiseEvent(ev)


    def delRoute(self, Route):
        for link in Route.links:
            link.cookies.remove(Route.cookie)
        self._removeFlows(Route)
        del self.routes[Route.cookie]
        log.debug("TODO: raiseEvent RouteDeletedEv")
        log.warn('Route with cookie %d has been deleted\n' % Route.cookie)


    def _removeFlows(self, route):
        for ofs, tabEntry in route.entries.iteritems():
            ofs.flow_table.remove_strict(tabEntry)


    def getRoutesDijkstra(self, src, dst, graph):
        D = {} # Final distances dict
        P = {} # Predecessor dict

        # Fill the dicts with default values
        for node in graph.keys():
            D[node] = 10**15 # Vertices are unreachable
            P[node] = "" # Vertices have no predecessors

        D[src] = 0 # The start vertex needs no move

        unseen_nodes = graph.keys() # All nodes are unseen

        foundDst = False
        foundSrc = False

        if src in graph.keys():
            foundSrc = True

        while len(unseen_nodes) > 0:
            # Select the node with the lowest value in D (final distance)
            shortest = None
            node = ''
            for temp_node in unseen_nodes:
                if shortest == None:
                    shortest = D[temp_node]
                    node = temp_node
                elif D[temp_node] < shortest:
                    shortest = D[temp_node]
                    node = temp_node

            # Remove the selected node from unseen_nodes
            unseen_nodes.remove(node)

            # For each child (ie: connected vertex) of the current node
            for child_node, child_value in graph[node].items():
                if child_node == dst:
                    foundDst = True
                if D[child_node] > D[node] + child_value:
                    D[child_node] = D[node] + child_value
                    # To go to child_node, you have to go through node
                    P[child_node] = node

        # Set a clean path
        path = []

        #if src and dst are not in the graph we return an empty path
        if not foundSrc and not foundDst:
            return path

        # We begin from the end
        node = dst
        # While we are not arrived at the beginning
        while not (node == src):
            if path.count(node) == 0:
                path.insert(0, (P[node],node, graph[P[node]][node])) # Insert the predecessor of the current node
                node = P[node] # The current node becomes its predecessor
            else:
                break

        return path


    def getRoutes(self, src, dst):
        if isinstance(src, (int, long)):
            dpid = src
            src = core.topology.getOFS(dpid)
            if not src:
                log.error("Unknown switch with dpid %s" % str(dpid))
                return

        if isinstance(dst, (int, long)):
            dpid = dst
            dst = core.topology.getOFS(dpid)
            if not dst:
                log.error("Unknown switch with dpid %s" % str(dpid))
                return

        n = len(core.topology.getSwitchs())
        allLinks = ScnLinks(core.openflow_discovery.getAllLinks())

        return self._getRoutes(src, dst, allLinks, n)


    def _getRoutes(self, src, dst, allLinks, n):

        def f(src, dst, route=ScnLinks(), res=[]):
            if route.hops() > 1:
                if route.lastSwitch() == dst:
                    return res
                if route.hops() == (n*2):
                    return res

            links = [link for link in allLinks if link.ofs1 == src]
            links = ScnLinks(links)
            for link in links:
                _route = route.clone()
                _route.append(link)
                if _route.hops() >= n*2:
                    return res

                if _route.lastSwitch() == dst:
                    res.append(_route)
                    continue

                #if we have allready pass by this switch forget this route
                if route.containSwitch(link.ofs2):
                    continue

                if len(_route) > 3:
                    continue
                f(_route.lastSwitch(), dst, route=_route, res=res)

            return res

        routes = sorted(f(src, dst), key=len)
        return routes


    def _invert(self, src, dst, key1, key2):
        value1 = src.get(key1)
        if value1:
            if dst[key1] == value1:
                del dst[key1]
            dst[key2] = value1

        value2 = src.get(key2)
        if value2:
            if dst[key2] == value2:
                del dst[key2]
            dst[key1] = value2


    def _invertRouteDict(self, **kwargs):
        if kwargs is None: return None
        if len(kwargs) == 0: return None

        res = kwargs.copy()
        self._invert(kwargs, res, SRCMAC, DSTMAC)
        self._invert(kwargs, res, SRCDPID, DSTDPID)
        self._invert(kwargs, res, SRCIP, DSTIP)
        self._invert(kwargs, res, INPORT, OUTPORT)
        self._invert(kwargs, res, SRCPORT, DSTPORT)

        gw = kwargs.get(GATEWAY)
        if gw:
            res[SRCDPID] = gw[0]
            res[INPORT] = gw[1]
            del res[GATEWAY]

        via = kwargs.get(VIA)
        if via:
            if len(via) > 0:
                reverseVia = []
                for link in via:
                    _srcOfp = link.ofp2
                    _dstOfp = link.ofp1

                    reverseLink = core.openflow_discovery.getLink(_srcOfp, _dstOfp)
                    if reverseLink is not None:
                        reverseVia.append(reverseLink)
                    else:
                        log.error("link not found ")
                        del kwargs[VIA]
                        continue

                res[VIA] = reverseVia.reverse()
            else:
                del kwargs[VIA]

        return res


    def createBiRoute(self, src, dst, *args, **kwargs):
        routeA = self.createRoute(src, dst, *args, **kwargs)
        if not routeA:
            log.error('Unable to create Route\nsrc:{0}\ndst{1}\nargs:{2}'\
                    .format(src, dst, kwargs))
            return None, None

        invertedKwargs = self._invertRouteDict(**kwargs)
        conditions = invertedKwargs.get(RoutingConditions.MainKey)
        if conditions:
            del invertedKwargs[RoutingConditions.MainKey]

        pathB = Path.create(dst, src, **invertedKwargs)
        routeB = self.createRoute(dst, src, *args, **invertedKwargs)
        if not routeB:
            log.error('Unable to create Route\nsrc:{1}\ndst{0}\nargs:{2}\ninvertargs:{3}'\
                    .format(src, dst, kwargs, invertedKwargs))
            return None, None

        cookie = kwargs.get('cookie')
        if cookie:
            routeA.cookie = cookie
            routeB.cookie = self.route_pair[cookie]

        self.addRoute(routeA)
        self.addRoute(routeB)
        self.route_pair[routeA.cookie] = routeB.cookie

        return routeA, routeB


    def createMesh(self, dst):
        host = core.topology.getHost(dst)
        dpid = host.ofp.ofs.dpid

        graph = self.getUsedBwGraph(self.forceRoute)
        log.debug("[ABL] -->  graph: %s" % graph)

        mesh = self.mesh.get(dst)
        if mesh is None:
            self.mesh[dst] = {}
            self._createMesh(dst, graph)

        for ip, mesh in self.mesh.iteritems():
            # check the flow to the adjacent switch
            if dpid not in mesh.keys():
                self._createMesh(ip, graph)


    def _createMesh(self, dst, graph, *args, **kwargs):
        protocol = kwargs.get(PROTOCOL)
        if protocol is None:
            protocol = ethernet.IP_TYPE

        dstinfo = self._resolveInfo(dst,
                kwargs.get(DSTMAC),
                kwargs.get(DSTIP),
                kwargs.get(DSTDPID),
                kwargs.get(OUTPORT),
                protocol,
                "dst")
        if  dstinfo is None:
            return None

        dst, dstmac, dstip, dstdpid, outport = dstinfo

        outputinfo = self._resolveOutputInfo(dstdpid, outport, protocol, **kwargs)
        if outputinfo is None:
            return None

        outport, dstdpid, ipProtocol, srcport, dstport, tos = outputinfo

        msg = self.createMessage(protocol, None, dstip, ipProtocol)
        msg.idle_timeout = kwargs.get(IDLE_TIMEOUT, of.OFP_FLOW_PERMANENT)
        msg.hard_timeout = kwargs.get(HARD_TIMEOUT, of.OFP_FLOW_PERMANENT)
        msg.actions = [
                       of.ofp_action_dl_addr.set_dst(dstmac),
                       of.ofp_action_output(port=outport, max_len=0)
                      ]

        mesh = self.mesh[dst]

        # Flow to the node from the adjacent switch
        if dstdpid not in mesh.keys():
            # send message to switch
            ofs = core.topology.getOFS(dstdpid)
            tabEntry = TableEntry.from_flow_mod(msg)
            ofs.flow_table.install(tabEntry)
            mesh[dstdpid] = 0

        msg.match.nw_tos = 0

        # Flow to the adjacent switch from other switches
        for sw in core.topology.getSwitchs():
            if dstdpid == sw.dpid:
                continue
            if sw.dpid in mesh.keys():
                continue

            via = self.getVia(sw.dpid, dstdpid, None, graph)
            route = ScnRoute()
            route.links = via
            route.path = Path.create(None, dst, **kwargs)

            for link in via:
                msg.actions = [of.ofp_action_output(port=link.ofp1.number, max_len=0)]

                # send message to switch
                ofs = link.ofs1
                tabEntry = TableEntry.from_flow_mod(msg)
                route.entries[ofs] = tabEntry

            # rewrite dst mac if last switch != first switch
            msg.actions = [
                           of.ofp_action_dl_addr.set_dst(dstmac),
                           of.ofp_action_output(port=outport, max_len=0)
                          ]

            # send message to switch
            ofs = core.topology.getOFS(dstdpid)
            tabEntry = TableEntry.from_flow_mod(msg)

            # use for jsonLogger
            route.lastEntity = tabEntry.actions[1]
            log.debug('a route should have been created')

            self.addRoute(route)
            mesh[sw.dpid] = route.cookie


    def _resolveInfo(self, addr, mac, ip, dpid, port, protocol, kind=""):
            if addr is None:
                return (None, None, None, None, None)

            if (isinstance(addr, (int, long))):
                addr = IPAddr(addr)
                log.debug('{0}ip = {1}'.format(kind, addr))

            if isinstance(addr, str):
                addr = IPAddr(addr)

            if isinstance(addr, EthAddr):
                return self._resolveInfoFromEthAddr(addr, mac, ip, dpid, port, protocol, kind)

            elif isinstance(addr, IPAddr):
                return self._resolveInfoFromIPAddr(addr, mac, ip, dpid, port, protocol, kind)

            elif isinstance(addr, Node):
                return self._resolveInfoFromNode(addr, mac, ip, dpid, port, protocol, kind)

            else:
                if dpid is None:
                    log.warn('[0}dpid is None'.format(kind))
                    return None
                if protocol == ethernet.IP_TYPE:
                    if ip is None:
                        log.warn('[0}ip is None'.format(kind))
                        return None
                elif mac is None:
                    log.warn('[0}mac is None'.format(kind))
                    return None

                return (addr, mac, ip, dpid, port)


    def _resolveInfoFromEthAddr(self, addr, mac, ip, dpid, port, protocol, kind=""):
        if mac is not None:
            if mac != addr:
                log.warn('{0}mac != {0}, what\'s going on???'.format(kind))
                return None
        else: mac = addr

        macInt = mac_to_int(mac)
        sw, sp, n = self.component.topology.getSwSpNFromMac(macInt)

        if sw is not None:
            if dpid is not None and dpid != sw.id:
                log.warn('{0}dpid is not None and {0}dpid != sw.id, what\'s going on???'.format(kind))
                return None
            else: dpid = sw.id

        if sp is not None:
            if port is not None and port != sp.port:
                log.warn('{0}port is not None and {0}port != sp.port, what\'s going on???'.format(kind))
                return None
            else: port = sp.port

        if protocol == ethernet.IP_TYPE:
            if n is not None:
                if ip is not None and ip != n.ip:
                    log.warn('{0}ip is not None and {0}ip != n.ip, what\'s going on???'.format(kind))
                    return None
                else: ip = n.ip

        return (addr, mac, ip, dpid, port)


    def _resolveInfoFromIPAddr(self, addr, mac, ip, dpid, port, protocol, kind=""):
        if protocol == ethernet.IP_TYPE:
            if ip is not None:
                if ip != addr:
                    log.warn('ip != {0}, what\'s going on???'.format(kind))
                    return None
            else: ip = addr

        h = core.topology.getHost(ip)
        if h is None:
            log.warn('Unkown host for {0}ip {1}'.format(kind, ip))
        ofp = h.ofp
        ofs = ofp.ofs

        if h.ipAddr != addr:
            log.warn('h.ipAddr != {0}, what\'s going on???'.format(kind))
            return None
        if mac is not None and mac != h.macAddr:
            log.warn('{0}mac is not None and {0}mac != h.mac, what\'s going on???'.format(kind))
            return None
        mac = h.macAddr

        if dpid is not None:
            if ofs is not None and dpid != ofs.dpid:
                log.warn('ofs is not None and {0]dpid != ofs.dpid, what\'s going on???'.format(kind))
                return None
            #else: weird...
        elif ofs is not None: dpid = ofs.dpid

        if port is not None:
            if ofp is not None and port != ofp.number:
                log.warn('ofp is not None and {0}port != ofp.number, what\'s going on???'.format(kind))
                return None
            #else: weird...
        elif ofp is not None: port = ofp.number

        return (addr, mac, ip, dpid, port)


    def _resolveInfoFromNode(self, addr, mac, ip, dpid, port, protocol, kind=""):
        sw, sp, n = self.component.topology.getSwSpNFromIp(addr.ip)

        if n != addr:
            log.warn('n != {0}, what\'s going on???'.format(kind))
            return None

        if dpid is not None:
            if sw is not None and dpid != sw.id:
                log.warn('sw is not None and {0}dpid != sw.id, what\'s going on???'.format(kind))
                return None
        elif sw is not None:
            dpid = sw.id

        if mac is not None:
            if addr.mac != mac:
                log.warn('{0}.mac != {0}mac, what\'s going on???'.format(kind))
                return None
        else:
            mac = addr.mac

        if protocol == ethernet.IP_TYPE:
            if ip is not None:
                if ip != addr.ip:
                    log.warn('{0}ip != {0}.ip, what\'s going on???'.format(kind))
                    return None
            else: ip = addr.ip

        if port is not None:
            if port != addr.switchPort.port:
                log.warn('{0}port != {0}.switchPort.port, what\'s going on???'.format(kind))
                return None
        else:
            port = addr.switchPort.port

        return (addr, mac, ip, dpid, port)


    def _resolveOutputInfo(self, _dstdpid, _outport, _protocol, **kwargs):
        tos = None
        srcport = None
        dstport = None
        ipProtocol = 0
        if _protocol == ethernet.IP_TYPE:
            ipProtocol = kwargs.get(IPPROTOCOL)
            if ipProtocol is None: ipProtocol = 0
            if ipProtocol in [ipv4.TCP_PROTOCOL, ipv4.UDP_PROTOCOL]:
                srcport = kwargs.get(SRCPORT, None)
                dstport = kwargs.get(DSTPORT, None)

            # TODO : something else
            # tos is used to set services path
            # but with http, a different tos might come back...
            if ipProtocol == ipv4.TCP_PROTOCOL and not srcport and not dstport:
                tos = kwargs.get(TOS)
                if tos is None: tos = 0

        gw = kwargs.get(GATEWAY)
        if gw and not isinstance(gw, ScnOpenFlowPort):
            log.warn("gateway is not a scnOpenFlowPort: %s" % gw)

        if _dstdpid is None:
            if _outport is None:
                log.debug('outport is None')
                if gw is None:
                    log.warn('gw is None')
                    return None

                _dstdpid = gw.ofs.dpid #gw[0]
                _outport = gw.number #gw[1]

            else:
                log.debug('outport is not None')
                if gw is None:
                    log.warn('gw is None')
                    return None

                else:
                    if _outport != gw.number:
                        log.warn('outport != gw.number, what\'s going on???')
                        return None

                    _dstdpid = gw.ofs.dpid

        elif _outport is None:
            log.debug('outport is None')
            if gw is None:
                log.warn('gw is None')
                return None

            if _dstdpid != gw.ofs.dpid:
                log.warn('dstdpid != gw.ofs.dpid, what\'s going on???')
                return None

            _outport = gw.number

        elif gw is not None:
            log.debug('gw is not None')
            if _dstdpid != gw.ofs.dpid:
                log.warn('dstdpid != gw.ofs.dpid, what\'s going on???')
                return None

            if _outport != gw.number:
                log.warn('outport != gw.number, what\'s going on???')
                return None

        return (_outport, _dstdpid, ipProtocol, srcport, dstport, tos)


    def createRoute(self, src, dst, *args, **kwargs):
        """
            src = EthAddr or str or IPAddr or Host
            dst = EthAddr or str or IPAddr or Host
            srcdpid = switch id (integer) or Switch
            inport = switch port (integer) or SwitchPort

            #via = [(dpid, port), (dpid), (dpid), (dpid, port), ...]
            via = ScnLinks

            #gateway = (dpid, port)
            gateway = SwitchPort

            tos = ip tos (integer)
            protocol = ethernet.IP_TYPE etc...
            ipProtocol = ipv4.TCP_PROTOCOL or ipv4.UDP_PROTOCOL etc...

            kwargs = etc...
        """
        protocol = kwargs.get(PROTOCOL)
        if protocol is None: protocol = ethernet.IP_TYPE

        srcinfo = self._resolveInfo(src,
                kwargs.get(SRCMAC),
                kwargs.get(SRCIP),
                kwargs.get(SRCDPID),
                kwargs.get(INPORT),
                protocol,
                "src")
        dstinfo = self._resolveInfo(dst,
                kwargs.get(DSTMAC),
                kwargs.get(DSTIP),
                kwargs.get(DSTDPID),
                kwargs.get(OUTPORT),
                protocol,
                "dst")

        if srcinfo is None or dstinfo is None:
            return None

        src, srcmac, srcip, srcdpid, inport = srcinfo
        dst, dstmac, dstip, dstdpid, outport = dstinfo

        outputinfo = self._resolveOutputInfo(dstdpid, outport, protocol, **kwargs)
        if outputinfo is None:
            return None

        outport, dstdpid, ipProtocol, srcport, dstport, tos = outputinfo

        via = kwargs.get(VIA)
        conditions = kwargs.get(RoutingConditions.MainKey)

        if srcdpid == dstdpid:
            via = self.getLocalVia(srcdpid, srcip, dstdpid, dstip)

        if via is None or self.forceRoute:
            minBw = None
            if conditions is not None:
                minBw = conditions.get(RoutingConditions.bandwidth)
            via = self.getVia(srcdpid, dstdpid, minBw)

        log.debug("via (scnLinks) => \n%s" % str(via))

        route = ScnRoute()
        route.links = ScnLinks(via)
        route.conditions = conditions
        route.path = Path.create(src, dst, **kwargs)

        # DO NOT REWRITE MAC ADDRESSES BETWEEN THE SWITCHES
        # ONLY THE LAST SWITCH WILL CHANGE THE DESTINATION MAC

        msg = self.createMessage(protocol, srcip, dstip, ipProtocol, srcport, dstport, tos)
        msg.idle_timeout = kwargs.get(IDLE_TIMEOUT, of.OFP_FLOW_PERMANENT)
        msg.hard_timeout = kwargs.get(HARD_TIMEOUT, of.OFP_FLOW_PERMANENT)

        for link in via:
            msg.actions = [of.ofp_action_output(port=link.ofp1.number, max_len=0)]

            # send message to switch
            ofs = link.ofs1
            tabEntry = TableEntry.from_flow_mod(msg)
            route.entries[ofs] = tabEntry

        # rewrite dst mac if last switch != first switch
        msg.actions = [
                       of.ofp_action_dl_addr.set_dst(dstmac),
                       of.ofp_action_output(port=outport, max_len=0)
                      ]

        # send message to switch
        ofs = core.topology.getOFS(dstdpid)
        tabEntry = TableEntry.from_flow_mod(msg)

        route.lastEntity = tabEntry.actions[1]
        log.debug('a route should have been created')

        return route


    def createMessage(self, protocol=None, srcip=None, dstip=None, ipProtocol=0, srcport=None, dstport=None, tos = None):
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match()

        #flow[core.IN_PORT] = inport # it would be better to have it but it's not a necessity
        if protocol == ethernet.IP_TYPE and srcip is not None:
            msg.match.nw_src = srcip
        if protocol == ethernet.IP_TYPE and dstip is not None:
            msg.match.nw_dst = dstip
        msg.match.dl_type = protocol

        if ipProtocol != 0:
            msg.match.nw_proto = ipProtocol

        if tos != None:
            msg.match.nw_tos = tos

        if srcport:
            msg.match.tp_src = srcport

        if dstport:
            msg.match.tp_dst = dstport

        log.info(msg.match.show())
        return msg


    def getUsedBwGraph(self, forceRoute=False):
        ######################################################################################
        ## Dijkstra way to find the possible via
        ######################################################################################
        graph ={}
        for link in core.openflow_discovery.getAllLinks():
            dstLst = {}
            try:
                dstLst = graph[link.ofs1.dpid]
            except KeyError:
                pass

            linkBwReserved = 0
            maximumBwNonFree = 0
            usedBw = 0
            reverseLink = core.openflow_discovery.getLink(link.ofp2, link.ofp1)
            for cookie in link.cookies:
                _route = self.getRoute(cookie)
                if _route is not None:
                      if _route.conditions is not None and _route.conditions[RoutingConditions.bandwidth] is not None:
                        linkBwReserved = _route.conditions[RoutingConditions.bandwidth]
                try:
                    if core.flowBw.flowBws[cookie] is not None:
                        if core.flowBw.flowBws[cookie].segBws[reverseLink.ofs2.dpid]:
                            usedBw = ceil(core.flowBw.flowBws[cookie].segBws[link.ofs2.dpid].bw)

                except KeyError:
                    usedBw = 0
                maximumBwNonFree += max(linkBwReserved,usedBw)
                log.debug("[ABL] %s->%s : %s ~ %s/%s => %s" % (link.ofs1.dpid, link.ofs2.dpid, cookie, linkBwReserved, usedBw, maximumBwNonFree))

            if reverseLink is not None:
                for cookie in reverseLink.cookies:
                    _route = self.getRoute(cookie)
                    if _route is not None:
                        if _route.conditions is not None and _route.conditions[RoutingConditions.bandwidth] is not None:
                            linkBwReserved = _route.conditions[RoutingConditions.bandwidth]
                        try:
                            if core.flowBw.flowBws[cookie] is not None:
                                if core.flowBw.flowBws[cookie].segBws[reverseLink.ofs2.dpid]:
                                    usedBw = ceil(core.flowBw.flowBws[cookie].segBws[link.ofs2.dpid].bw)
                        except KeyError:
                            usedBw = 0
                    maximumBwNonFree += max(linkBwReserved,usedBw)
                    log.debug("[ABL] %s->%s : %s ~ %s/%s => %s" % (link.ofs1.dpid, link.ofs2.dpid, cookie, linkBwReserved, usedBw, maximumBwNonFree))

            if forceRoute:
                    maximumBwNonFree=1

            dstLst[link.ofs2.dpid] = maximumBwNonFree
            graph[link.ofs1.dpid] = dstLst

        return graph


    def getVia(self, srcdpid, dstdpid, minBw=None, graph=None):
        if graph is None:
            graph = self.getUsedBwGraph(self.forceRoute)
            log.debug("[ABL] -->  graph: %s" % graph)

        t1 = datetime.datetime.now()
        possibleVia = self.getRoutesDijkstra(srcdpid, dstdpid, graph)
        t2 = datetime.datetime.now()
        dt = t2 - t1
        log.debug("[ABL] --> possibleVia Dijkstra [%s] found in %s in [%s]" % (possibleVia, str(dt), graph))

        via = []
        for vertex in possibleVia:
            link = core.openflow_discovery.getLinkByDpid(vertex[0],vertex[1])
            via.append(link)

            if minBw is not None and vertex[2] < minBw:
                log.debug('link %s : not enough bandwidth' % link)
                self.optimizeRequested = True

        return via


    def getLocalVia(self, srcdpid, srcip, dstdpid, dstip):
        log.debug("srcdpid == dstdpid")
        srcPort = -1
        dstPort = -1

        for port in core.topology.getOFS(srcdpid).getPorts():
            host = port.getHost(srcip)
            if host is not None:
                srcPort = port.number
                break

        for port in core.topology.getOFS(dstdpid).getPorts():
            host = port.getHost(dstip)
            if host is not None:
                dstPort = port.number
                break

        if srcPort == -1 or dstPort == -1:
            log.error("No route found for %s -> %s" % (srcip, dstip))
            return None

        srcOfp = core.topology.getOFP(srcdpid, srcPort)
        dstOfp = core.topology.getOFP(dstdpid, dstPort)
        link = ScnLink(srcOfp, dstOfp)

        return [link]

#_____________________________________________________________________________#
#                         do_/help_ method for CLI                            #
#_____________________________________________________________________________#

    def help_getAllTabEntries(self):
        msg = 'getAllEntries'
        return msg


    def do_getAllTabEntries(self, args):
        args = args.split(' ')
        #TODO put a test to check that the cookie is number or not

        retour = "========================================\n"
        for route in core.routing.routes.values():
            if not route :
                break

            retour = "%sTabEntries for cookie %s\n" % (retour,route.cookie)
            for ofs, tabEntry in route.entries.iteritems():
                retour = "%s\t%s:%s\n" % (retour, ofs.dpid, tabEntry)
            retour = "%s---------------------------------------\n" % retour

        return retour

#_____________________________________________________________________________#

def launch(**kw):

    if core.hasComponent(NAME):
        return None
    forceRoute = False
    try:
       forceRoute = core.parser.getValue('ROUTING', 'FORCE_ROUTE')
       if forceRoute is None:
           forceRoute = False
    except:
       pass

    comp = Routing(forceRoute)
    core.register(NAME, comp)
    return comp


