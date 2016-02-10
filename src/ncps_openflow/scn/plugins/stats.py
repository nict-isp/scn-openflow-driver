# -*- coding: utf-8 -*-
"""
scn.plugins.stats
~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""
import pox.openflow.libopenflow_01 as of

from pox.core import core
from pox.lib.packet.packet_utils import ethtype_to_str
from pox.lib.recoco import Timer
from pox.lib.revent.revent import Event, EventMixin
from pox.lib.util import dpidToStr

NAME = __file__.split('/')[-1].split('.')[0]

log = core.getLogger()

MONITOR_FLOW_PERIOD = 10
UNIT_OF_VALUE = "bit"
IDENT = 0

#==============================================================================#
#                             Internal function                                #
#==============================================================================#

def _unfix_null (v):
    return v


def _unfix_port (v):
    return of.ofp_port_map.get(v, v)


def _unfix_ip (v):
    v = v()
    if v[1] == 0:
        return str(v[0])

    return "%s/%i" % v


def _unfix_str (v):
    return str(v)


def _unfix_ethertype (v):
    if v <= 0x05dc:
        return v

    #NOTE: This may just result in a hex string.  In that case, we might
    #      want to just use a number.
    return ethtype_to_str(v)


_unfix_map = {k:_unfix_null for k in of.ofp_match_data.keys()}
_unfix_map['in_port'] = _unfix_port
_unfix_map['dl_src'] = _unfix_str
_unfix_map['dl_dst'] = _unfix_str
_unfix_map['dl_type'] = _unfix_ethertype
_unfix_map['get_nw_src'] = _unfix_ip
_unfix_map['get_nw_dst'] = _unfix_ip

#==============================================================================#
#                        General method used by Stats                          #
#==============================================================================#

def _timer_func ():
    """ handler for timer function that sends the requests to all the
        switches connected to the controller.
    """
    log.debug("start check stat")

    for connection in core.openflow._connections.values():

        #FlowStatsReceived
        connection.send(of.ofp_stats_request(
                body = of.ofp_flow_stats_request(),
                type = of.ofp_stats_types_rev_map.get("OFPST_FLOW")
            ))

        #AggregateFlowStatsReceived
        connection.send(of.ofp_stats_request(
                body = of.ofp_aggregate_stats_request(),
                type = of.ofp_stats_types_rev_map.get("OFPST_AGGREGATE")
            ))

        #TableStatsReceived
        # I don't know which methode to call (it's not of.ofp_flow_stats())
        #connection.send(of.ofp_stats_request(body=of.ofp_table_stats()))

        #PortStatsReceived
        connection.send(of.ofp_stats_request(
                body = of.ofp_port_stats_request(port_no=of.OFPP_NONE),
                type = of.ofp_stats_types_rev_map.get("OFPST_PORT")
            ))

        #QueueStatsReceived
        body = of.ofp_queue_stats_request(port_no = of.OFPP_NONE, queue_id = of.OFPQ_ALL)
        connection.send(of.ofp_stats_request(
                body = body,
                type = of.ofp_stats_types_rev_map.get("OFPST_QUEUE")
            ))

        #FlowRemoved
        # I don't know which methode to call (it's not of.ofp_flow_stats())
        #connection.send(of.ofp_stats_request(body=of.ofp_flow_removed()))


def flow_stats_to_list (flowstats):
    """
    Takes a list of flow stats
    """
    stats = []
    for stat in flowstats:
        s = {}
        stats.append(s)
        for k, v in fields_of(stat).iteritems():
            if k == 'length':
                continue
            if k.startswith('pad'):
                continue
            if k == 'match':
                v = match_to_dict(v)
            elif k == 'actions':
                v = [action_to_dict(a) for a in v]
            s[k] = v

    return stats


def fields_of (obj, primitives_only=False, primitives_and_composites_only=False, allow_caps=False):
    """
    Returns key/value pairs of things that seem like public fields of an object.
    """
    ret = {}
    for k in dir(obj):
        if k.startswith('_'):
            continue

        v = getattr(obj, k)
        if hasattr(v, '__call__'):
            continue

        if not allow_caps and k.upper() == k:
            continue

        if primitives_only:
            if not isinstance(v, _scalar_types):
                continue
        elif primitives_and_composites_only:
            if not isinstance(v, (int, long, basestring, float, bool, set, dict, list)):
                continue

        ret[k] = v

    return ret


def action_to_dict(action):
    """
    create action feature dict instance.
    """
    d = {}
    d['type'] = of.ofp_action_type_map.get(action.type, action.type)
    for k, v in fields_of(action).iteritems():
        if k in ['type','length']:
            continue

        if k == "port":
            v = of.ofp_port_map.get(v, v)
        d[k] = v

    return d


def match_to_dict (match):
    """
    create match feature dict instance.
    """
    d = {}
    #TODO: Use symbolic names
    for k, func in _unfix_map.iteritems():
        v = getattr(match, k)
        if v is None:
            continue

        v = func(v)
        d[k] = v

    return d


#==============================================================================#
#                              Additional classes                              #
#==============================================================================#
class StatsEv(Event):
    EVENT_NAME = 'StatsEv(no use)'

    def __init__(self, dpid, stats, unit):
        Event.__init__(self)
        self.dpid = dpid
        self.stats = stats
        self.unit = unit


    def __repr__(self):
        return "<%s|%s>" % (str(self.dpid), str(self.stats))


class FlowStatsEv(StatsEv):

    EVENT_NAME = 'FlowStatsEv'

    def __init__(self, dpid, stats, unit):
        StatsEv.__init__(self, dpid, stats, unit)
        global IDENT
        IDENT = IDENT + 1
        self.ident = IDENT


class PortStatsEv(StatsEv):

    EVENT_NAME = 'PortStatsEv'

    def __init__(self, dpid, stats, unit):
        StatsEv.__init__(self, dpid, stats, unit)


class AggregateFlowStatsEv(StatsEv):

    EVENT_NAME = 'AggregateFlowStatsEv'

    def __init__(self, dpid, stats, unit):
        StatsEv.__init__(self, dpid, stats, unit)


class QueueStatsEv(StatsEv):

    EVENT_NAME = 'QueueStatsEv'

    def __init__(self, dpid, stats, unit):
        StatsEv.__init__(self, dpid, stats, unit)


class FlowRemovedEv(StatsEv):

    EVENT_NAME = 'FlowRemovedEv'

    def __init__(self, dpid, stats, unit):
        StatsEv.__init__(self, dpid, stats, unit)


class TableStatsEv(StatsEv):

    EVENT_NAME = 'TableStatsEv'

    def __init__(self, dpid, stats, unit):
        StatsEv.__init__(self, dpid, stats, unit)


#==============================================================================#
#                                  Main class                                  #
#==============================================================================#

class Stats(EventMixin) :

    _wantComponents    = set(['topology'])
    _eventMixin_events = set([
        PortStatsEv,
        FlowStatsEv,
        AggregateFlowStatsEv,
        QueueStatsEv,
        FlowRemovedEv,
        TableStatsEv
    ])

    def __init__ (self, unit):
        EventMixin.__init__(self)
        core.listenToDependencies(self, self._wantComponents)

        self.unit = unit

#______________________________________________________________________________#
#                                   Handle                                     #
#______________________________________________________________________________#
    def raiseEvent(self, event, dpid, stats, unit):
        """
        @override
        """
        log.debug("%s from %s: \n%s\n", event, dpidToStr(dpid), stats)
        EventMixin.raiseEvent(self, event, dpid, stats, unit)


    def _handle_FlowStatsReceived(self, event):
        log.debug("handle flowstats recieved")
        stats = flow_stats_to_list(event.stats)
        dpid = event.connection.dpid
        self.raiseEvent(FlowStatsEv, dpid, stats, self.unit)


    def _handle_AggregateFlowStatsReceived (self, event):
        log.debug("handle aggregate flowstats recieved")
        stats = event.stats
        dpid = event.connection.dpid
        self.raiseEvent(AggregateFlowStatsEv, dpid, stats, self.unit)


    def _handle_TableStatsReceived (self, event):
        log.debug("handle table stats recieved")
        stats = flow_stats_to_list(event.stats)
        dpid = event.connection.dpid
        self.raiseEvent(TableStatsEv, dpid, stats, self.unit)


    def _handle_PortStatsReceived (self, event):
        log.debug("handle port stats recieved")
        stats = flow_stats_to_list(event.stats)
        dpid = event.connection.dpid
        self.raiseEvent(PortStatsEv, dpid, stats, self.unit)


    def _handle_QueueStatsReceived (self, event):
        log.debug("handle queue stats recieved")
        stats = flow_stats_to_list(event.stats)
        dpid = event.connection.dpid
        self.raiseEvent(QueueStatsEv, dpid, stats, self.unit)


    def _handle_FlowRemoved (self, event):
        log.debug("handle flow removed recieved")
        stats = flow_stats_to_list(event.stats)
        dpid = event.connection.dpid
        self.raiseEvent(FlowRemovedEv, dpid, stats, self.unit)


#==============================================================================#
#                                   Launcher                                   #
#==============================================================================#

def launch(**kwargs):
    """
    launch and register Stats instance
    """
    # register the component
    if core.hasComponent(NAME):
        return None

    unit = kwargs.get('UNIT_OF_VALUE', UNIT_OF_VALUE)
    comp = Stats(unit)
    core.register(NAME, comp)

    # attach handlers to listners
    core.openflow.addListenerByName("FlowStatsReceived", comp._handle_FlowStatsReceived)
    core.openflow.addListenerByName("AggregateFlowStatsReceived", comp._handle_AggregateFlowStatsReceived)
    core.openflow.addListenerByName("TableStatsReceived", comp._handle_TableStatsReceived)
    core.openflow.addListenerByName("PortStatsReceived", comp._handle_PortStatsReceived)
    core.openflow.addListenerByName("QueueStatsReceived", comp._handle_QueueStatsReceived)
    core.openflow.addListenerByName("FlowRemoved", comp._handle_FlowRemoved)

    # timer set to execute every MONITOR_FLOW_PERIOD seconds
    period = kwargs.get('MONITOR_FLOW_PERIOD', MONITOR_FLOW_PERIOD)
    Timer(period, _timer_func, recurring=True)

    return comp

