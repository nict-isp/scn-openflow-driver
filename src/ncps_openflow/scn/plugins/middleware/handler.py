# -*- coding: utf-8 -*-
"""
scn.plugins.middleware.handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from pox.core import core
from pox.lib.revent import EventMixin

from events import (CmdReq, CmdResp,
        InitializeReq, InitializeResp, CreateBiPathReq, CreateBiPathResp,
        DeleteBiPathReq, DeleteBiPathResp, UpdatePathReq, UpdatePathResp,
        OptimizeReq, OptimizeResp, PushReq, HeartBeatReq, DumpReq, DumpResp)
from path import Path, ConditionDescription, PathDescription, PathList
from routeCreator import DijkstraRouteCreator, RoundRobinCreator
from utils.widgets import GwPeer, Peer, ScnClientNode, NodeList
from utils.redisFeature import RedisFeature
from scn.scnOFTopology import ScnLinkUpdatedEv

from datetime import datetime
import traceback

# for Backward compatibility
from scn import routing
from scn.routing import ScnLinks
from pox.lib.addresses import IPAddr
from pox.lib.packet.ipv4 import ipv4
from math import ceil

# for Debug
from scn.plugins.flowBw import *
from scn.scnOFTopology import ScnOpenFlowTopology

NAME = 'middleware'
HAERTBEAT_ACTIVATE = True
HAERTBEAT_INTERVAL_EXPECT = 10

log = core.getLogger()

def raise_event(func):
    """for decorating handler method
    """
    def wrapper(self, req, *args, **kwargs):
        """event raise after func called
         consider multiple event raise. => resp is list or scalar
        """
        if req.NAME != 'HEART_BEAT_REQUEST':
            self.cmds.append(req)

        resp = None
        try:
            resp = func(self, req, *args, **kwargs)

        except Exception as e:
            log.error(traceback.format_exc())
            resp = CmdResp(
                    req.req_id,
                    error = 'ERR_INTERNAL',
                    dst_peer = req.listen_peer
                )

        if resp is None:
            pass
        elif not isinstance(resp, list):
            self.raiseEvent(resp)
        else:
            for _resp in resp:
                self.raiseEvent(_resp)

    return wrapper


class Handler(EventMixin, RedisFeature):
    """Process path control requset from SCN
       implement event handler
    """
    _eventMixin_events = set([
        CmdReq,  # for nop cmd
        CmdResp, # for nop cmd
        InitializeReq,
        InitializeResp,
        CreateBiPathReq,
        CreateBiPathResp,
        DeleteBiPathReq,
        DeleteBiPathResp,
        UpdatePathReq,
        UpdatePathResp,
        OptimizeReq,
        OptimizeResp,
        ScnLinkUpdatedEv,
        PushReq,
        HeartBeatReq,
        DumpReq,  # for debug
        DumpResp, # for debug
    ])

    def __init__(self, heartbeatActivate, heartbeatInterval):
        EventMixin.__init__(self)
        RedisFeature.__init__(self)

        self._path_info = {}
        self._node_list = NodeList()

        self.heartbeatActivate = heartbeatActivate
        self.heartbeatInterval = heartbeatInterval

        self.max_id = 2**16-1
        self.prev_id = 0

        self.cmds = []

        core.openflow_discovery.addListenerByName('LinkEvent', self._handle_LinkEvent)

#----------------------------------------------------------------------------#
#                            Handler                                         #
#----------------------------------------------------------------------------#

    @raise_event
    def _handle_InitializeReq(self, req, src_gw):
        """request handler for InitializeReq Cmd
        """
        log.info("InitializeReq = [%s] NODE = [%s]" % (req, src_gw))
        gw_peer = GwPeer(src_gw.ofp.ipAddr)
        error = None

        scn_id = None
        for i in xrange(self.prev_id + 1, self.prev_id + self.max_id):
            tmp_id = i % (self.max_id + 1)
            if not tmp_id:
                continue

            if not self._node_list.get_by('scn_id', tmp_id):
                self.prev_id = scn_id = tmp_id
                break

        if scn_id:
            node = ScnClientNode(
                scn_id,
                req.listen_peer.ipaddr,
                req.listen_peer.port,
                req.listen_peer.protocol
            )
            self._node_list.append(node)

        else:
            error = 'ERR_CANNOT_GET_SCNID'

        core.routing.createMesh(req.listen_peer.ipaddr)
        svs_srv_ip = core.parser.getValue('SERVICE_SERVER', 'SERVICE_SERVER_IP')

        return InitializeResp(
                req.req_id,
                gw_peer,
                scn_id,
                svs_srv_ip,
                error = error,
                dst_peer = req.listen_peer
            )

    @raise_event
    def _handle_CreateBiPathReq(self, req, src_gw):
        """request handler for CreateBiPathReq Cmd
        """
        log.info("CreateBiPathReq = [%s] NODE = [%s]" % (req, src_gw))
        error = None

        srcIp = IPAddr(str(req.src.get('ipaddr')))
        dstIp = IPAddr(str(req.dst.get('ipaddr')))
        tos   = req.app_id.get('tos')
        minBw = req.send_conditions.get('bandwidth')
        #recv_conditions is scalability for future.

        node = self.__getNode__(req.listen_peer)
        path_id = self.__doInnerCreatePath__(srcIp, dstIp, tos, node, minBw)
        if not path_id:
            error = 'ERR_CANNOT_GET_PATHID'

        req.listen_peer.protocol = Peer.TCP
        return CreateBiPathResp(
                req.req_id,
                path_id,
                error = error,
                dst_peer = req.listen_peer
            )

    @raise_event
    def _handle_UpdatePathReq(self, req, src_gw):
        """request handler for UpdatePathReqReq Cmd
        """
        log.info("UpdatePathReq = [%s] NODE = [%s]" % (req, src_gw))
        error = None

        minBw = req.conditions.get('bandwidth')

        try:
            srcIp, dstIp, flag, _  = self._path_info[req.path_id]
            send, recv = self.__getPaths__(srcIp, dstIp, flag)
            log.debug('update path %s <=> %s' % (str(send), str(recv)))
            route = core.routing.getRoute(send)
            route.conditions = self.__getConditions__(minBw)

        except KeyError:
            error = 'ERR_INVALID_PATHID'

        core.routing.optimizeRequested = True

        req.listen_peer.protocol = Peer.TCP
        return UpdatePathResp(
                req.req_id,
                error = error,
                dst_peer = req.listen_peer
            )

    @raise_event
    def _handle_DeleteBiPathReq(self, req, src_gw):
        """request handler for DeleteBiPathReq Cmd
        """
        log.info("DeleteBiPathReq = [%s] NODE = [%s]" % (req, src_gw))
        error = None

        try:
            srcIp, dstIp, flag, _ = self._path_info.pop(req.path_id)
            send, recv = self.__getPaths__(srcIp, dstIp, flag)
            log.debug('delete path %s <=> %s' % (str(send), str(recv)))
            core.routing.delPath(send)
            core.routing.delPath(recv)

        except KeyError:
            error = 'ERR_INVALID_PATHID'

        req.listen_peer.protocol = Peer.TCP
        return DeleteBiPathResp(
                req.req_id,
                error = error,
                dst_peer = req.listen_peer
            )

    @raise_event
    def _handle_HeartBeatReq(self, req, src_gw):
        """request handler for OptimizeReq Cmd
        """
        log.debug("HeartBeatReq = [%s] NODE = [%s]" % (req, src_gw))
        ipaddr = IPAddr(str(req.listen_peer.ipaddr))
        node = self.__getNode__(ipaddr)
        if node is not None:
            node.heartbeat = datetime.now()
        return None

    @raise_event
    def _handle_OptimizeReq(self, req, src_gw):
        """request handler for OptimizeReq Cmd
        """
        log.info("OptimizeReq = [%s] NODE = [%s]" % (req, src_gw))
        error = None

        core.routing.optimizeRequested = True

        req.listen_peer.protocol = Peer.TCP
        return OptimizeResp(
                req.req_id,
                error = error,
                dst_peer = req.listen_peer
            )

    @raise_event
    def _handle_DumpReq(self, req, src_gw):
        """request handler for OptimizeReq Cmd
        """
        log.info("DumpReq = [%s] NODE = [%s]" % (req, src_gw))
        error = None

        req.listen_peer.protocol = Peer.TCP
        return DumpResp(
                req.req_id,
                str(core.openflow_topology.topology),
                [str(r) for r in core.routing.getRoutes2()],
                error = error,
                dst_peer = req.listen_peer
            )

    def _handle_LinkEvent(self, event):
        """event handler for Link add or remove
            event[core.openflow_discovery.LinkEvent] -- link event
        """
        link = event.link.to_json()
        _id = str(event.link.get_id())
        if event.added:
            event.link.addListener(ScnLinkUpdatedEv, self._handle_ScnLinkUpdateEvent)
            #self.__push__(_id, link)
            #self.__publish__(_id + ':ADD', link)
        elif event.removed:
            event.link.removeListener(self._handle_ScnLinkUpdateEvent)
            #self.__publish__(_id + ':REMOVE', link)

    def _handle_ScnLinkUpdateEvent(self, event):
        """event handler for ScnLinkUpdateEvent
            call when ScnLink state updated
            event[scn.discovery.ScnLinkUpdateEv] -- link update event
        """
        if event.link.getBandwidthUsed() > 0:
            log.info(event.link)
            link = event.link.to_json()
            _id = str(event.link.get_id())
            #self.__push__(_id, link)
            #self.__publish__(_id + ':UPDATE', link)
            #self.push_request(event.EVENT_NAME, event.link)

    def push_request_optimize_failure(self, cookies):
        """push request to SCN nodes, when optimization failure
            cookies[List[int]] -- cookie of bad routes
        """
        pushes = {}
        for path, info in self._path_info.items():
            send, recv = path.split('_bi_')
            _, _, _, peer = info

            if int(send) in cookies:
                routes = pushes.get(peer, [])
                routes.append(path)
                pushes[peer] = routes
            elif int(recv) in cookies:
                routes = pushes.get(peer, [])
                routes.append(path)
                pushes[peer] = routes
            else:
                log.warn("%s notin %s" % (path, cookies))

        for peer, paths in pushes.items():
            routes = list(set(paths))
            self.push_request('OPTIMIZE_FAILURE', {"routes":routes}, peer)

    def push_request(self, name, payload, nodes = None):
        """push request to SCN nodes.
            name[str] -- some name (like id)
            payload[Class/dict] -- send payload. it's must have to_json or be dict.

        """
        if not nodes:
            nodes = self._node_list
        if not isinstance(nodes, list):
            nodes = [nodes]

        for node in nodes:
            log.debug("push_request to %s" % node)
            self.raiseEvent(PushReq(name, payload, dst_peer = node))

#----------------------------------------------------------------------------#
#                             Other methods                                  #
#----------------------------------------------------------------------------#
    @classmethod
    def __getConditions__(cls, minBw):
        conditions = {}
        conditions[routing.RoutingConditions.bandwidth] = minBw
        # TODO
        # conditions[Conditions.fix] = ???
        return conditions

    def __getPaths__(self, srcIp, dstIp, flag):
        return routing.Path.create(srcIp, dstIp, tos=flag), \
                routing.Path.create(dstIp, srcIp, tos=flag)

    def __doInnerCreatePath__(self, srcIp, dstIp, tos, peer, minBw):
        kwargs = {}
        kwargs['srcip'] = srcIp
        kwargs['dstip'] = dstIp
        kwargs[routing.IPPROTOCOL] = ipv4.TCP_PROTOCOL
        kwargs['tos'] = tos
        kwargs[routing.RoutingConditions.MainKey] = self.__getConditions__(minBw)

        log.debug(str(kwargs))

        routeA, routeB = core.routing.createBiRoute(srcIp, dstIp, **kwargs)
        if not routeA or not routeB:
            # XXX it would be better to send back an error
            # Done ?!?
            return None

        cookie = '{0}_bi_{1}'.format(routeA.cookie, routeB.cookie)
        log.debug('ROUTE CREATED: {0}'.format(cookie))

        self._path_info[cookie] = [srcIp, dstIp, tos, peer]
        return cookie

    def isNodeAlive(self, ipaddr):
        node = self.__getNode__(ipaddr)
        return node is not None and self.__isAlive__(node, datetime.now())

    def __isAlive__(self, node, now):
        return not self.heartbeatActivate \
                or self.heartbeatInterval > (now - node.heartbeat).seconds

    def __getNode__(self, ipaddr):
        return self._node_list.get_by('ipaddr', ipaddr)


###############################################################################
def launch(**kwargs):
    """middleware launch
       accessable core.middleware.*
       **kwargs is need for option args.
       see __init__.py also.
    """
    log.debug(kwargs)
    if core.hasComponent(NAME):
        return None

    heartbeatActivate = kwargs.get('HAERTBEAT_ACTIVATE', HAERTBEAT_ACTIVATE)
    heartbeatInterval = kwargs.get('HAERTBEAT_INTERVAL_EXPECT', HAERTBEAT_INTERVAL_EXPECT)

    comp = Handler(heartbeatActivate, heartbeatInterval)
    return comp

