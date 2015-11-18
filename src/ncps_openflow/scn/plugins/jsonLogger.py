# -*- coding: UTF-8 -*-
"""
scn.plugins.jsonLogger
~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import json
import time

from pox.core import core
from pox.lib.recoco import Timer
from pox.lib.addresses import IPAddr
import pox.openflow.libopenflow_01 as of

from middleware.utils.redisFeature import RedisFeature
from scn.routing import MacPath, IpPath

log = core.getLogger()

NAME='jsonLogger'
wantComponents = ['middleware', 'flowBw']
ACTIVESAVELOG = 0
SAVELOGFOLDER = "/home/openflow/"

TOPOLOGY_OUTPUT_KEYWORD = "topology"
TOPOLOGY_OUTPUT_PERIOD = 60
BANDWIDTH_OUTPUT_KEYWORD = "bandwidth"
BANDWIDTH_OUTPUT_PERIOD = 60
NODE_LOCATION_OUTPUT_KEYWORD = "nodelocation"
NODE_LOCATION_OUTPUT_PERIOD = 10
PATH_OUTPUT_KEYWORD = "path"
PATH_OUTPUT_PERIOD = 10
TRAFFIC_OUTPUT_KEYWORD = "traffic"
TRAFFIC_OUTPUT_PERIOD = 30
COMMAND_OUTPUT_KEYWORD = "command"
COMMAND_OUTPUT_PERIOD = 5


class JsonLogger(RedisFeature):

    _wantComponents = ['middleware', 'flowBw']

    def __init__ (self):
        RedisFeature.__init__(self)
        self.macAddrs = {}


    def __printStarted(self, name, key):
        log.info("{0} started. (key:{1})".format(name, key))
        return time.clock()


    def __printFinished(self, name, key, start):
        log.info("{0} finished. (time:{2:.3f})".format(name, key, time.clock() - start))


    def push_getTopologyOutput(self, key):
        start = self.__printStarted("push_getTopologyOutput", key)
        self.__push__(key, self.do_getTopologyOutput())
        self.__printFinished("push_getTopologyOutput", key, start)


    def do_getTopologyOutput(self, arg=None):
        # Switch
        s = ''
        s_list = []
        for switch in core.topology.getSwitchs():
            s_info = {}
            s_info['id'] = str(switch.dpid) # ID
            s_info['ip'] = str(switch.ipaddr) # IP
            s_info['mac'] = "" #str(None) # MAC

            #SwitchPort
            sp_list = []
            for sp in switch.getPorts():

                if sp.number ==  of.OFPP_LOCAL:
                    continue
                sp_unit = {}
                sp_unit['port'] = str(sp.number) # Port
                sp_unit['ip'] = str(sp.ipAddr) # IP
                sp_unit['mac'] = str(sp.hwAddr) # MAC
                sp_list.append(sp_unit)

                s_info['switchport'] = sp_list

            s_unit = {}
            s_unit['switch'] = s_info
            s_list.append(s_unit)

        return s_list


    def push_getBandwidthOutput(self, key):
        start = self.__printStarted("push_getBandwidthOutput", key)
        self.__publish__(key, self.do_getBandwidthOutput())
        self.__printFinished("push_getBandwidthOutput", key, start)


    def do_getBandwidthOutput(self, arg=None):
        kwList = []
        links = core.openflow_discovery.getAllLinks()
        for link in links:
            kw = {}
            kw['src_switch_id'] = '%d' % link.dpid1
            kw['src_switch_port'] = '%d' % link.port1
            kw['dst_switch_id'] = '%d' % link.dpid2
            kw['dst_switch_port'] = '%d' % link.port2
            kw['bandwidth'] = str(link.getBandwidthUsed())
            kwList.append(kw)

        return kwList


    def push_getJsonCommand(self, key):
        start = self.__printStarted("push_getJsonCommand", key)
        self.__publish__(key, self.do_getJsonCommand())
        del core.middleware.cmds[:]
        self.__printFinished("push_getJsonCommand", key, start)


    def help_getJsonCommand(self):
        msg = 'getJsonCommand\nex: getJsonCommand'
        return msg


    def do_getJsonCommand(self, args=None):
        allList = []
        kv = {}
        kv['service_key'] = "dummy"
        bufList = []
        for cmd in core.middleware.cmds:
            cmdKv = {}
            cmdKv['timestamp'] = cmd.timestamp
            cmdKv['command'] = cmd.buf
            bufList.append(cmdKv)

        kv['commands'] = bufList
        allList.append(kv)

        return allList


    def push_getJsonAllNodeLocation(self, key):
        start = self.__printStarted("push_getJsonAllNodeLocation", key)
        self.__publish__(key, self.do_getJsonAllNodeLocation())
        self.__printFinished("push_getJsonAllNodeLocation", key, start)


    def help_getJsonAllNodeLocation(self):
        msg = 'getJsonAllNodeLocation\nex:\n\tgetJsonAllNodeLocation'
        return msg


    def do_getJsonAllNodeLocation(self, arg=None):
        allNodes = []
        for sw in core.topology.getSwitchs():
            for sp in sw.getPorts():
                for node in sp.getHosts():
                    if not node.ipAddr:
                        continue
                    kv = {}

                    #msg = 'Node with ip %s ' % ip
                    kv['node_ip'] = str(node.ipAddr)
                    kv['node_mac'] = str(node.macAddr)
                    kv['node_alive'] = core.middleware.isNodeAlive(node.ipAddr)

                    #msg = '%s is connected to switch [id=%d,ip=%s],' % (msg, sw.id, ip_to_str(sw.ip))
                    if sp.ipAddr:
                        kv['vGW_IP'] = str(sp.ipAddr)
                    else:
                        kv['vGW_IP'] = ''
                    #msg = '%s port [%d, %s]' % (msg, sp.port, str(sp.name))
                    kv['sw_id'] = str(sw.dpid)
                    kv['sw_portName'] = sp.name
                    if sp.name and len(sp.name) > 3:
                        kv['sw_port'] = sp.number
                    else:
                        kv['sw_port'] = ''

                    allNodes.append(kv)

        return allNodes


    def push_getJsonAllPath(self, key):
        start = self.__printStarted("push_getJsonAllPath", key)
        self.__publish__(key, self.do_getJsonAllPath())
        self.__printFinished("push_getJsonAllPath", key, start)


    def help_getJsonAllPath(self):
        msg = 'getJsonAllPath -> prints all services path'
        return msg


    def do_getJsonAllPath(self, arg=None):
        allSrvPath = []

        for route in core.routing.getRoutes2():
            try:
                path = route.path
                if path.src == None:
                    continue    #Control Path

                kv = {}
                kv['path_id'] = route.cookie
                kv['srcService_key'] = "dummy"
                kv['srcService_name'] = "dummy"
                kv['dstService_key'] = "dummy"
                kv['dstService_name'] = "dummy"

                if isinstance(path, MacPath):
                    kv['srcNode_Mac'] = str(path.src)
                    kv['dstNode_Mac'] = str(path.dst)

                if isinstance(path, IpPath):
                    if path.tos is None or path.tos == 0:
                        continue    #Control Path

                    if path.src not in self.macAddrs:
                        self.macAddrs[path.src] = str(core.topology.getHost(path.src).macAddr)
                    if path.dst not in self.macAddrs:
                        self.macAddrs[path.dst] = str(core.topology.getHost(path.dst).macAddr)

                    kv['srcNode_Mac'] = self.macAddrs[path.src]
                    kv['dstNode_Mac'] = self.macAddrs[path.dst]

                spList = []
                for link in route.links:
                    ofs = link.ofs1
                    ofp = link.ofp1
                    _kv = {}
                    _kv['id'] = ofs.dpid

                    _kv['sw_portName'] = ofp.name
                    if ofp.name and len(ofp.name) > 3:
                        _kv['sw_port'] = ofp.number
                    else:
                        _kv['sw_port'] = ''

                    spList.append(_kv)

                lastSwitch = route.links[-1].ofs2
                lastPort = lastSwitch.getOFPort(route.lastEntity.port)
                _kv = {}
                _kv['id'] = lastSwitch.dpid

                _kv['sw_portName'] = lastPort.name
                if lastPort.name and len(lastPort.name) > 3:
                    _kv['sw_port'] = lastPort.number
                else:
                    _kv['sw_port'] = ''

                spList.append(_kv)

                kv['switch'] = spList
                allSrvPath.append(kv)

            except:
                log.warn("invalid route {0}, path {1}".format(route, route.path))

        return allSrvPath

        msg = json.dumps(allSrvPath, sort_keys=True, indent=1)
        res = self.strToLine(msg)
        if self.activeSaveLog == "1":
             self.writeSaveLog('JsonAllPath.log', res)

        return res


    def push_getJsonAllTraffic(self, key):
        start = self.__printStarted("push_getJsonAllTraffic", key)
        self.__publish__(key, self.do_getJsonAllTraffic())
        self.__printFinished("push_getJsonAllTraffic", key, start)


    def help_getJsonAllTraffic(self):
        msg = 'getJsonAllTraffic -> prints all services traffic'
        return msg


    def do_getJsonAllTraffic(self, arg=None):
        trafficList = []

        for route in core.routing.getRoutes2():
            kv = {}
            kv['path_id'] = route.cookie
            kv['srcService_key'] = "dummy"
            kv['srcService_name'] = "dummy"
            kv['dstService_key'] = "dummy"
            kv['dstService_name'] = "dummy"

            flowBw = core.flowBw.flowBws.get(route.cookie)
            if flowBw:
                kv['traffic'] = 8 * flowBw.bw/1000. # kbps
            else:
                kv['traffic'] = 0

            trafficList.append(kv)

        return trafficList


def launch(**kwargs):
    if core.hasComponent(NAME):
        return None

    comp = JsonLogger()
    core.register(NAME, comp)

    # timers set to execute every period seconds
    period = kwargs.get('TOPOLOGY_OUTPUT_PERIOD', TOPOLOGY_OUTPUT_PERIOD)
    keyword = kwargs.get('TOPOLOGY_OUTPUT_KEYWORD', TOPOLOGY_OUTPUT_KEYWORD)
    if period > 0:
        Timer(period, comp.push_getTopologyOutput, recurring=True, args=[keyword])

    period = kwargs.get('BANDWIDTH_OUTPUT_PERIOD', BANDWIDTH_OUTPUT_PERIOD)
    keyword = kwargs.get('BANDWIDTH_OUTPUT_KEYWORD', BANDWIDTH_OUTPUT_KEYWORD)
    if period > 0:
        Timer(period, comp.push_getBandwidthOutput, recurring=True, args=[keyword])

    period = kwargs.get('NODE_LOCATION_OUTPUT_PERIOD', NODE_LOCATION_OUTPUT_PERIOD)
    keyword = kwargs.get('NODE_LOCATION_OUTPUT_KEYWORD', NODE_LOCATION_OUTPUT_KEYWORD)
    if period > 0:
        Timer(period, comp.push_getJsonAllNodeLocation, recurring=True, args=[keyword])

    period = kwargs.get('PATH_OUTPUT_PERIOD', PATH_OUTPUT_PERIOD)
    keyword = kwargs.get('PATH_OUTPUT_KEYWORD', PATH_OUTPUT_KEYWORD)
    if period > 0:
        Timer(period, comp.push_getJsonAllPath, recurring=True, args=[keyword])

    period = kwargs.get('TRAFFIC_OUTPUT_PERIOD', TRAFFIC_OUTPUT_PERIOD)
    keyword = kwargs.get('TRAFFIC_OUTPUT_KEYWORD', TRAFFIC_OUTPUT_KEYWORD)
    if period > 0:
        Timer(period, comp.push_getJsonAllTraffic, recurring=True, args=[keyword])

    period = kwargs.get('COMMAND_OUTPUT_PERIOD', COMMAND_OUTPUT_PERIOD)
    keyword = kwargs.get('COMMAND_OUTPUT_KEYWORD', COMMAND_OUTPUT_KEYWORD)
    if period > 0:
        Timer(period, comp.push_getJsonCommand, recurring=True, args=[keyword])
    return comp

