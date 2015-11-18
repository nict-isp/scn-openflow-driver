# -*- coding: utf-8 -*-
"""
scn.plugins.middleware.interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import json

from pox.core import core

from pox.lib.addresses import IPAddr
from pox.lib.revent import EventMixin

from events import (CmdResp,
        InitializeReq, InitializeResp, CreateBiPathReq, CreateBiPathResp,
        DeleteBiPathReq, DeleteBiPathResp, UpdatePathReq, UpdatePathResp,
        OptimizeReq, OptimizeResp, PushReq, HeartBeatReq, DumpReq, DumpResp)
from utils.widgets import Transport, Peer
from utils.connection import MWTcpServer, MWUdpServer, MWTcpClient

log = core.getLogger()

def send_tcp_payload(dst_peer, payload):
    """send TCP message I/F using MWTcpClient(original TCP client for SCN).
    dst_peer need for getting application port.
    """
    # get registed node.
    node = core.topology.getHost(dst_peer.ipaddr)
    ofp = node.ofp
    switch = ofp.ofs
    dpid = switch.dpid
    port = ofp.number

    src_mac = ofp.hwAddr
    src_ip = ofp.ipAddr
    src = (src_mac, src_ip)

    dst_mac = node.macAddr
    dst_ip = dst_peer.ipaddr
    dst_port = dst_peer.port
    dst = (dst_mac, dst_ip, dst_port)

    log.info("request : dpid=%s, port=%s,src=%s, dst=%s" % (dpid, port, src, dst))
    log.debug("payload : %s" % str(payload))

    tcp_client = MWTcpClient(dpid, port, src, dst, payload)
    core.protocols.addClient(tcp_client)
    tcp_client.start()


class Interface(EventMixin):
    """request and response I/F from/to node(SCN) or Switch(OFC)
    """

    _eventMixin_events = [
        CmdResp,
        InitializeReq,
        CreateBiPathReq,
        UpdatePathReq,
        DeleteBiPathReq,
        OptimizeReq,
        HeartBeatReq,
        DumpReq
    ]

    supported = {
        Peer.TCP : send_tcp_payload
    }

    def __init__(self):
        EventMixin.__init__(self)

        udp_server = MWUdpServer(self.process_command, Transport.LPORT)
        core.protocols.addServer(udp_server)

        tcp_server = MWTcpServer(self.process_command, Transport.LPORT)
        core.protocols.addServer(tcp_server,
                                 needSend=True)

        core.middleware.listenTo(self)
        self.register_event_handler()

        # register decode class for input (request/response) message.
        # 本OFCサーバへの入力メッセージをデコードするクラスを登録する
        # (入力メッセージボディのNAMEプロパティから,対応するクラスメソッドが呼びだされる)
        self.decode_classes = {
            # JSON CMD Name      : called Class
            InitializeReq.NAME   : InitializeReq,
            CreateBiPathReq.NAME : CreateBiPathReq,
            UpdatePathReq.NAME   : UpdatePathReq,
            DeleteBiPathReq.NAME : DeleteBiPathReq,
            OptimizeReq.NAME     : OptimizeReq,
            HeartBeatReq.NAME    : HeartBeatReq,
            DumpReq.NAME         : DumpReq
        }

    def register_event_handler(self):
        """register handler for event raised middlewar.py
            request handler is for innter domain request.
        """
        for req in [InitializeReq, CreateBiPathReq, UpdatePathReq, \
                DeleteBiPathReq, OptimizeReq, HeartBeatReq, DumpReq]:
            core.middleware.addListenerByName(req.__name__, self.handle_request)
        for resp in [InitializeResp, CreateBiPathResp, UpdatePathResp, \
                DeleteBiPathResp, OptimizeResp, DumpResp, PushReq, CmdResp]:
            core.middleware.addListenerByName(resp.__name__, self.handle_response)

    def process_command(self, node, data):
        """input handler.
           call when MWTcpServer receive payload.
             @param [ScnOpenFlowHost] node input src node
             @param [string] data JSON format
        """
        log.debug('process_command = [%s]' % repr(data))
        event = self.decode_json(data)

        if not node:
            # if not node -> create registerd node instance from listen_peer
            node = core.topology.getHost(IPAddr(event.dst_peer.ipaddr))

        self.raiseEvent(event, node)

    def decode_json(self, data):
        """decode json protocol cmd.
            use reigisted class(self.decode_class)
        """
        try:
            kwargs = json.loads(data)
            kwargs['buf'] = data
            cls = self.decode_classes.get(kwargs['NAME'])
            if not cls:
                log.warn('Unknown Command Type')
                return CmdResp()
            decoded = cls.from_dict(kwargs)
            if not decoded:
                log.warn('No Data ? Class=%s' % str(cls))
                return CmdResp()
        except (TypeError, ValueError) as inst:
            log.exception(inst)
            log.error("Could not decode json : [%s]" % str(data))
            return CmdResp()

        log.info('\n--\n%s command received\n%s\n--\n' % (decoded.NAME, repr(data)))
        return decoded

    # ========= Handler from OFC Server(middlewar.py) raise (request/response) message =========== #
    def handle_response(self, resp):
        """ handler to send response.
        """
        log.info("send response to node :%s" % str(resp))
        self.__send_data__(resp, resp.dst_peer)

    def handle_request(self, req):
        """ handler to send resquest.
        """
        log.info("send request to other OFC :%s" % str(req))
        self.__send_data__(req, req.dst_peer)

    def __send_data__(self, send_cls, dst_peer):
        """send data.
            check protocol and convert data.
            do send method.
        """
        if not dst_peer:
            log.warning('Peer is none. It might be a static service with no listen peer...')
            return

        if not self.__check_supported_protocol__(dst_peer.protocol):
            log.warn("not supported protocol.%s" % str(dst_peer.protocol))
            return

        payload = None
        try:
            payload = send_cls.to_json() + MWTcpServer.DELIMITER
        except (TypeError, ValueError) as inst:
            log.exception(inst)

        if not payload:
            log.warn("no payload")
            return

        log.info('\n--\n%s: %s to\n%s\n--\n' % (send_cls.NAME, repr(payload), dst_peer))
        self.__get_request_method__(dst_peer.protocol)(dst_peer, payload)

    def __check_supported_protocol__(self, protocol):
        """check that protocol can use ?
        """
        return self.supported.has_key(protocol)

    def __get_request_method__(self, protocol):
        """get sender method.
        """
        return self.supported[protocol]


def launch(**kwargs):
    """middlewareCmds launch
       **kwargs is need for option args.
       see __init__.py also.
    """
    log.debug(kwargs)
    Interface()

