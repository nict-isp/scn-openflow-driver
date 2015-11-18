# -*- coding: utf-8 -*-
"""
scn.plugins.middleware.utils.widgets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import json
from datetime import datetime
from pox.lib.addresses import IPAddr
from redisFeature import RedisFeature


class Transport:
    """For Transport Constants
    """
    LPORT = 55555
    TCP   = 'TCP'
    UDP   = 'UDP'

    def __init__(self):
        pass


class IPEncoder(json.JSONEncoder):
    """JSON Encoder for IPAddr
       use when Peer jsonize
    """
    def default(self, obj):
        if isinstance(obj, IPAddr):
            return str(obj)
        elif isinstance(obj, datetime):
            return None

        return json.JSONEncoder.default(self, obj)


class PeerEncoder(IPEncoder):
    """JSON Encoder for Peer
       use when TraceList jsonize
    """
    def default(self, obj):
        if isinstance(obj, Peer):
            return obj.to_json()

        return IPEncoder.default(self, obj)


class Peer:
    """This class express some Communication Object.
       mainly, TCP
       TODO : is domain realy need?
    """
    TCP = Transport.TCP
    UDP = Transport.UDP

    def __init__(self, ipaddr, port, protocol = TCP, domain = None):

        if not isinstance(ipaddr, IPAddr):
            ipaddr = IPAddr(str(ipaddr))
        self.ipaddr = ipaddr

        self.port = int(port)

        if not protocol:
            protocol = self.TCP
        self.protocol = protocol

        self.domain = domain


    @classmethod
    def from_dict(cls, info):
        """create instance from dict
        """
        peer = None
        if isinstance(info, dict):
            peer = Peer(
                    info.get("ipaddr"),
                    info.get("port"),
                    info.get("protocol"),
                    info.get("domain")
                  )
        return peer


    @classmethod
    def from_json(cls, string):
        """create instance from JSON
        """
        return Peer.from_dict(json.loads(string))


    def to_json(self):
        """get JSON string
        """
        return json.dumps(dict(self.__dict__), cls=IPEncoder)


    def __eq__(self, other):
        if not isinstance(other, Peer):
            return False
        if (self.ipaddr   != other.ipaddr   and
            self.port     != other.port     and
            self.protocol != other.protocol and
            self.domain   != other.domain):
            return False
        return True


    def __str__(self):
        return '%s<%s:%s:%d (%s)>' % (
                self.__class__.__name__,
                self.protocol.lower(),
                str(self.ipaddr),
                self.port,
                str(self.domain)
              )


class GwPeer(Peer):
    """ Gateway Peer
        for the nearest OFS(VirtualNode) or interdomain GW OFS(VirtualNode)
        Node最寄りのOFSやドメイン間でのゲートウェイ用
        set LPORT for communication to OFC.
        OFCとの通信のため、LPORTを固定で設定
    """
    def __init__(self, ipaddr, *args, **kwargs):
        Peer.__init__(self, ipaddr, Transport.LPORT, *args, **kwargs)


class ScnClientNode(Peer):
    """ Scn Middleware Node.
        has scn middleware id.
    """
    def __init__(self, scn_id, ipaddr, port, protocol = Peer.TCP, domain = None):
        Peer.__init__(self, ipaddr, port, protocol, domain)
        self.scn_id = scn_id
        self.heartbeat = datetime.now()


    def __hash__(self):
        return self.scn_id.__hash__()


    def __eq__(self, other):
        return self.scn_id == other.scn_id and Peer.__eq__(self, other)


    def __str__(self):
        return '%s<%s:%s:%d (%s), id=%s>' % (
                self.__class__.__name__,
                self.protocol.lower(),
                str(self.ipaddr),
                self.port,
                str(self.domain),
                str(self.scn_id)
              )


class TraceList:
    """Peer List
       Pass Node List on inter domain communication
       that has Peer class List
       ドメイン間を渡る場合に利用する、通過ノード一覧
    """

    # @param [list{dict}] peers    this method can input parsable JSON.
    #                              dict形式を内包するlistを受け付ける.(parse可能なJSON文字列でも可)
    def __init__(self):
        # @attribute [list{Peer}] _peers ノード一覧
        self._peers = []


    def append(self, peer):
        """ append peer.
        """
        assert isinstance(peer, Peer)
        self._peers.append(peer)
        return self


    def pop(self):
        """pop peer.
        """
        if len(self._peers) > 0:
            return self._peers.pop()


    def to_json(self):
        """get JSON string
        """
        return json.dumps(self._peers, cls=PeerEncoder)


    @classmethod
    def get_tracelist(cls, peers):
        """create instance from list
        """
        if not isinstance(peers, list):
            peers = [peers]
        trace_list = TraceList()
        for peer in peers:
            if isinstance(peer, (str, unicode)):
                trace_list.append(Peer.from_json(peer))
            elif isinstance(peer, dict):
                trace_list.append(Peer.from_dict(peer))
        return trace_list


    @classmethod
    def from_json(cls, string):
        """create instance from JSON
        """
        return TraceList.get_tracelist(json.loads(string))


    def __str__(self):
        string = self.__class__.__name__ + "<"
        for peer in self._peers:
            string = string + "{" + str(peer) + "} "
        return string + ">"


    def __len__(self):
        return len(self._peers)


class NodeList(list, RedisFeature):
    """list of SCN Nodes(Peer).
    """
    _rediskey = "nodes"
    def __init__(self):
        list.__init__(self)
        RedisFeature.__init__(self)


    def first(self):
        """get first node.
        """
        return self[0]


    def last(self):
        """get last node.
        """
        return self[-1]


    def index_by_ip(self, ip):
        """get index by IP Address.
        """
        return self.index_by("ipaddr", ip)


    def get_by(self, key, value):
        """get node by some key, value.
            key[str] -- search attr key
            value[any] -- mathc value

            return node[Peer](None if not exist)
        """
        (node, index) = self.__get_by__(key, value)
        return node


    def index_by(self, key, value):
        """get Node index by some key.
            key[str] -- search attr key
            value[any] -- mathc value

            return index(-1 if not exist)
        """
        (node, index) = self.__get_by__(key, value)
        return index


    def __get_by__(self, key, value):
        for i in range(len(self)):
            if getattr(self[i], key) == value:
                return (self[i], i)
        return (None, -1)


    def append(self, node):
        """append and do somthing for redis.
        """
        assert isinstance(node, Peer)
        save = node.to_json()
        idx = self.index_by_ip(node.ipaddr)
        if idx < 0:
            list.append(self, node)
            self.__save_state__(self._rediskey, save)
            self.__publish__(self._rediskey + ":ADD", save)
        else:
            del self[idx]
            list.append(self, node)
            self.__save_state__(self._rediskey, save)
            self.__publish__(self._rediskey + ":UPDATE", save)

