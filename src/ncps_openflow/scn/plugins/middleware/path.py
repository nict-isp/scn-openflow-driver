# -*- coding: utf-8 -*-
"""
scn.plugins.middleware.path
~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import traceback
import re
import time
import json

from pox.core import core
from pox.lib.revent import Event, EventMixin
from utils.widgets import Peer
from utils.redisFeature import RedisFeature

log = core.getLogger()

UNITS = ["P", "G", "M", "K"]

MAX_COOKIE = 0x7fFFffFF
__next_cookie__ = 1 # use as global


class ReadOnly:
    """ReadOnly Feature
        set attribute is permitted when __init__.
    """
    def __init__(self):
        pass

    def __setattr__(self, name, value):
        trace = traceback.extract_stack()
        func = trace[-2][2] # function name called __setattr__
        if func == "__init__":
            self.__dict__[name] = value
        else:
            raise AttributeError("%s is read only: value = %s" % (name, value))

    def __str__(self):
        return "%s:<%s>" % (
                self.__class__.__name__,
                ", ".join(["%s=%s" % (k, v) for k, v in self.__dict__.iteritems()])
            )

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        for k, v in self.__dict__.iteritems():
            if not other.__dict__.get(k) == v:
                return False
        return True


class PathChangedEv(Event):
    """event which notify path chaned.
    """
    def __init__(self):
        Event.__init__(self)
        self.timestamp = time.time()


class Path(EventMixin):
    """Path Object.
        path is route from src node to dst node.
        it has some links which consits of two ofs.
    """
    links = None
    _eventMixin_events = set([
        PathChangedEv,
    ])

    def __init__(self, path_desc, cond_desc):
        EventMixin.__init__(self)
        self.last_update = time.time()
        self.links = []
        self.path_id = None
        assert isinstance(path_desc, PathDescription)
        assert isinstance(cond_desc, ConditionDescription)
        self.path_description = path_desc
        self.condition_description = cond_desc
        self.cookie = self.__generate_cookie__()

    @classmethod
    def __generate_cookie__(cls):
        global __next_cookie__
        cookie = __next_cookie__
        __next_cookie__ += 1
        __next_cookie__ = (__next_cookie__) % (MAX_COOKIE + 1)
        return cookie

    def __str__(self):
        return "%s:[id=%s][cookie=%s][path=%s][cond=%s][links=%s]" % (
                self.__class__.__name__,
                str(self.path_id),
                str(self.cookie),
                str(self.path_description),
                str(self.condition_description),
                ", ".join([str(link) for link in self.links])
            )

    def update_links(self, links = None):
        """update links
            links[List<ScnLink>] -- links created by routeCreator.
            calling with no arguments --> remove links.
        """
        self.links = links or []
        self.last_update = time.time()

        if len(self.links):
            self.apply_flow_entries()
        else:
            self.remove_flow_entries()

    def remove_links(self):
        """shorthand update_links()
        """
        self.update_links()

    def apply_flow_entries(self):
        """apply flow entry to links(ofs).
        """
        src = self.path_description.src
        dst = self.path_description.dst
        app_id = self.path_description.app_id
        for link in self.links:
            is_last = True if (link is self.links[-1]) else False
            link.apply_flow_entry(self.cookie, src, dst, app_id, is_last)

        self.raiseEventNoErrors(PathChangedEv, changed = self)

    def remove_flow_entries(self):
        """remove flow entry to links(ofs).
        """
        src = self.path_description.src
        dst = self.path_description.dst
        app_id = self.path_description.app_id
        for link in self.links:
            link.remove_flow_entry(self.cookie, src, dst, app_id)

        self.raiseEventNoErrors(PathChangedEv, changed = self)

    def get_src_ip(self):
        """get src node ip address.
        """
        return self.path_description.src.ipaddr

    def get_dst_ip(self):
        """get dst node ip address.
        """
        return self.path_description.dst.ipaddr

    def get_strategy(self):
        """get routing strategy.
        """
        return self.condition_description.strategy

    def to_json(self):
        """return string formatted by json.
            only Peer object use to_json method.
        """
        return json.dumps({
            "id"     : self.path_id,
            "cookie" : self.cookie,
            "path_description" : {
                "src" : self.path_description.src.to_json(),
                "dst" : self.path_description.dst.to_json(),
                "app_id" : self.path_description.app_id.__dict__
            },
            "condition_description" : {
                "bandwidth" : self.condition_description.bandwidth.__dict__,
                "strategy"  : self.condition_description.strategy.__dict__,
                "priority"  : self.condition_description.priority
            },
            "links" : [link.get_id() for link in self.links]
        })


class ConditionDescription(ReadOnly):
    """Path Conditions

        bandwidth[BandWidth] -- is like 200Mbps, 0.2GBPS, 200000Kbps
        strategy[Strategy]   -- is dict which has "logic" and "timing"
        priority[int]        -- is priority. defaults is 255
    """
    def __init__(self, bandwidth = None, strategy = None, priority = None):

        if bandwidth:
            bandwidth = BandWidth(bandwidth)
        self.bandwidth = bandwidth

        if not strategy:
            strategy = {}
        self.strategy = Strategy(strategy.get("logic"), strategy.get("timing"))

        if not priority:
            priority = 255
        self.priority = int(priority)
        ReadOnly.__init__(self)


class PathDescription(ReadOnly):
    """Path Settings.

        src[Peer]  -- src node locator described by Peer.
        dst[Peer]  -- dst node locator described by Peer.
        app_id[AppId] -- some id which describe the Path. set flow tables.
    """
    def __init__(self, src, dst, app_id):
        self.src = Peer.from_dict(src)
        self.dst = Peer.from_dict(dst)
        assert isinstance(app_id, dict)
        self.app_id = AppId(tos = app_id.get("tos"), vlan = app_id.get("vlan"))
        ReadOnly.__init__(self)


class Strategy(ReadOnly):
    """Routing Strategy.

        logic[str]   --- strategy logic. default = "DIJKSTRA"
        timing[str] --- apply timnig. default = "STATIC"
    """
    def __init__(self, logic = None, timing = None):
        if not logic:
            logic = "DIJKSTRA"
        if not timing:
            timing = "STATIC"
        self.logic   = logic
        self.timing = timing
        ReadOnly.__init__(self)


class BandWidth(ReadOnly):
    """BandWidth Setting.
        bandwidth[BandWidth] -- is like 200Mbps, 0.2GBPS, 200000Kbps

    """
    BANDCHECK = re.compile("^(\d+)([" + "".join(UNITS) + "]{0,1})(bps|BPS)*$")

    def __init__(self, bandwidth, unit = None):
        match = BandWidth.BANDCHECK.search(str(bandwidth))
        if match:
            bandwidth = match.group(1)
            if unit and unit in UNITS:
                pass
            else:
                unit = match.group(2)
            self.bandwidth = bandwidth
            self.unit = unit
        else:
            raise ValueError("invalid bandwidth format{%s}. ex.100Gbps" % bandwidth)
        ReadOnly.__init__(self)


class AppId(ReadOnly):
    """Path Identification for OFS.
        we use tos or vlan.
        TODO: use anything else?.
    """

    tos  = None
    vlan = None

    def __init__(self, tos = None, vlan = None):
        if tos is not None:
            self.tos = int(tos)
        if vlan is not None:
            self.vlan = int(vlan)
        """if self.vlan is None:
           raise ValueError("need vlan")
        """
        ReadOnly.__init__(self)

    def get_id(self):
        """get appid.
            vlan's priority is high.
        """
        if self.vlan is not None:
            return {
                "type"  : "dl_vlan",
                "value" : self.vlan
            }
        if self.tos is not None:
            return {
                "type" : "nw_tos",
                "value": self.tos
            }

class PathList(dict, RedisFeature):
    """table of created Path objects.
    """
    _rediskey = "paths"
    def __init__(self):
        dict.__init__(self)
        RedisFeature.__init__(self)

    def add(self, key, path):
        """add Path object.
            key[str] -- path_id
            path[Path] -- path object
        """
        self[str(key)] = path
        self.__save_state__(self._rediskey, path.to_json())
        self.__publish__(self._rediskey + ":ADD", path.to_json())

        return self

    def remove(self, key):
        """remove path object.
            key[str] -- path_id
        """
        _key = ""
        if isinstance(key, Path):
            _key = key.path_id
        else:
            _key = key
        path = self[str(_key)]
        save = path.to_json()
        self.__delete_state__(self._rediskey, save)
        self.__publish__(self._rediskey + ":REMOVE", save)
        del self[str(_key)]

        return self

