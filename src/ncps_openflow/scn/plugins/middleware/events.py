# -*- coding: utf-8 -*-
"""
scn.plugins.middleware.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from pox.core import core
import time
import json
import inspect

from pox.lib.revent import Event
from utils.widgets import Peer, TraceList # PEP328

log = core.getLogger()


class Command(Event):
    """ Command Top Class
    """
    NAME = 'COMMAND'

    def __init__(self, req_id, *args, **kwargs):
        Event.__init__(self)
        self.req_id = req_id
        self.timestamp = time.time()

    def __str__(self):
        return self.__class__.__name__ + "<%s>" % self._data_str()

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.req_id == self.req_id

    def _data_str(self):
        """ helper __str__
            create string from attributes.
        """
        return "req_id=%s, time=%s" % (self.req_id, self.timestamp)


class CmdReq(Command):
    """ Request Command Top class
    """
    NAME = 'COMMAND_REQUEST'
    cls_dict  = {}

    def __init__(self, req_id, buf = None, *args, **kwargs):
        Command.__init__(self, req_id, *args, **kwargs)
        self.buf = buf

    @classmethod
    def from_json(cls, string):
        """create instance from JSON
        """
        data = json.loads(string)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data):
        """create instance from dict object
        """
        return create_cmd_from_dict(
                cls,
                data,
                cls_dict = cls.cls_dict
            )


class CmdResp(Command):
    """ Response Command Top class
    """
    NAME = 'COMMAND_RESPONSE'

    def __init__(self, req_id, dst_peer, error = None, error_info = None, *args, **kwargs):
        """
            dst_peer[Peer] : peer(node) to send cmd.
        """
        Command.__init__(self, req_id, *args, **kwargs)
        assert isinstance(dst_peer, Peer)
        self.dst_peer = dst_peer
        if not error:
            error = None
        self.error = error
        if not error_info:
            error_info = None
        self.error_info = error_info

    def _data_str(self):
        s = "dst=%s" % self.dst_peer
        if self.error:
            s += ",error=%s" % self.error
        if self.error_info:
            s += ",error_info=%s" % self.error_info
        return Command._data_str(self) + s

    def __eq__(self, other):
        return (Command.__eq__(self, other)
                and self.dst_peer == other.dst_peer)

    def to_json(self):
        """decode self attribute to JSON string.
           dict keys, values is decieded by this method.
        """
        return json.dumps({
            "error"      : self.error,
            "error_info" : self.error_info,
            "req_id"     : self.req_id,
            "NAME"       : self.NAME
        })


class InterDomainMsg(CmdReq, CmdResp):
    """ InterDomain Msg Command Top class
        TODO ドメイン間コントロール用の準備(json両変換が必要)
    """
    NAME = 'INTER_DOMAIN_COMMAND_MSG'

    def __init__(self, req_id, dst_peer, trace_list, *args, **kwargs):
        """
            dst_peer[Peer] : peer(node) to send cmd.
            trace_list[TraceList] : passed switch list.
        """
        CmdReq.__init__(self, req_id, *args, **kwargs)
        CmdResp.__init__(self, req_id, dst_peer, *args, **kwargs)
        assert isinstance(trace_list, TraceList)
        self.trace_list = trace_list

    def __eq__(self, other):
        return (CmdReq.__eq__(self, other)
                and CmdResp.__eq__(self, other)
                and self.trace_list == other.trace_list)

    def to_json(self):
        return json.dumps({
            "NAME" : self.NAME,
            "trace_list" : self.trace_list.to_json()
        })


class PushReq(CmdResp):
    """ Push request from ofc to SCN node.
        notice: format is response msg.
    """
    NAME = 'PUSH_REQUEST'

    def __init__(self, event, payload, dst_peer, *args, **kwargs):
        CmdResp.__init__(self, None, dst_peer, *args, **kwargs)
        self.event = event
        self.payload = payload

    def to_json(self):
        payload = None
        if callable(self.payload):
            payload = self.payload.to_json()
        else:
            payload = json.dumps(self.payload)

        return json.dumps({
            "payload"    : payload,
            "event"      : self.event,
            "NAME"       : self.NAME
        })

    def _data_str(self):
        return "%s,event=%s,payload=%s" % (
                CmdResp._data_str(self),
                self.event,
                self.payload
            )


class InitializeReq(CmdReq):
    """ Initialize Command Requset
    """
    NAME = 'INITIALIZE_REQUEST'
    cls_dict = {'listen_peer': Peer}

    def __init__(self, req_id, buf, listen_peer, *args, **kwargs):
        CmdReq.__init__(self, req_id, buf, *args, **kwargs)
        assert isinstance(listen_peer, Peer)
        self.listen_peer = listen_peer

    def __eq__(self, other):
        return (CmdReq.__eq__(self, other)
                and self.listen_peer == other.listen_peer
                )

    def _data_str(self):
        return "%s,listen_peer=%s" % (
                CmdReq._data_str(self),
                self.listen_peer
            )


class InitializeResp(CmdResp):
    """ Initialize Command Response
    """
    NAME = 'INITIALIZE_RESPONSE'

    def __init__(self, req_id, gw_peer, scn_id, svs_srv_ip, dst_peer,  *args, **kwargs):
        CmdResp.__init__(self, req_id, dst_peer, *args, **kwargs)
        assert isinstance(gw_peer, Peer)
        self.gw_peer = gw_peer
        self.scn_id = scn_id
        self.svs_srv_ip = svs_srv_ip

    def _data_str(self):
        return "%s,gw_peer=%s,scn_id=%s" % (
                CmdResp._data_str(self),
                self.gw_peer,
                str(self.scn_id)
            )

    def to_json(self):
        return json.dumps({
            "error"      : self.error,
            "error_info" : self.error_info,
            "req_id"     : self.req_id,
            "gw_peer"    : self.gw_peer.to_json(),
            "scn_id"     : str(self.scn_id),
            "svs_srv_ip": self.svs_srv_ip,
            "NAME"       : self.NAME
        })


class CreatePathReq(CmdReq):
    """ CreatePath Command Requset (Old version command)
    """
    NAME = 'CREATE_PATH_REQUEST'
    cls_dict = {'listen_peer': Peer}

    def __init__(self, req_id, buf, src, dst, app_id, listen_peer, conditions = None, *args, **kwargs):
        CmdReq.__init__(self, req_id, buf, *args, **kwargs)
        self.src = src
        self.dst = dst
        self.app_id = app_id
        if not conditions:
            conditions = {}
        self.conditions = conditions
        assert isinstance(listen_peer, Peer)
        self.listen_peer = listen_peer

    def _data_str(self):
        return (CmdReq._data_str(self) +
               ",src=%s,dst=%s,cond=%s,app_id=%s,listen_peer=%s" %
                (self.src, self.dst, self.conditions, self.app_id, self.listen_peer))


class CreateBiPathReq(CmdReq):
    """ CreateBiPath Command Requset
    """
    NAME = 'CREATE_BI_PATH_REQUEST'
    cls_dict = {'listen_peer': Peer}

    def __init__(self, req_id, buf, src, dst, app_id, listen_peer,
            send_conditions = None, recv_conditions = None, *args, **kwargs):
        CmdReq.__init__(self, req_id, buf, *args, **kwargs)
        self.src = src
        self.dst = dst
        self.app_id = app_id
        if not send_conditions:
            send_conditions = {}
        self.send_conditions = send_conditions
        if not recv_conditions:
            recv_conditions = {}
        self.recv_conditions = recv_conditions
        assert isinstance(listen_peer, Peer)
        self.listen_peer = listen_peer

    def _data_str(self):
        return (CmdReq._data_str(self) +
               ",src=%s,dst=%s,send_cond=%s,recv_cond=%s,app_id=%s,listen_peer=%s" %
               (self.src, self.dst, self.send_conditions, self.recv_conditions,
                   self.app_id, self.listen_peer))


class CreateBiPathResp(CmdResp):
    """ CreateBiPath Command Response
    """
    NAME = 'CREATE_BI_PATH_RESPONSE'

    def __init__(self, req_id, path_id, dst_peer, *args, **kwargs):
        CmdResp.__init__(self, req_id, dst_peer, *args, **kwargs)
        self.path_id = path_id

    def _data_str(self):
        return "%s,path_id=%s," % (CmdResp._data_str(self), self.path_id)

    def to_json(self):
        return json.dumps({
            "error"        : self.error,
            "error_info"   : self.error_info,
            "req_id"       : self.req_id,
            "path_id"      : self.path_id,
            "NAME"         : self.NAME
        })


class UpdatePathReq(CmdReq):
    """ UpdatePath Command Requset
    """
    NAME = 'UPDATE_PATH_REQUEST'
    cls_dict = {'listen_peer': Peer}

    def __init__(self, req_id, buf, path_id, conditions, listen_peer, *args, **kwargs):
        CmdReq.__init__(self, req_id, buf, *args, **kwargs)
        self.path_id = path_id
        self.conditions = conditions

        assert isinstance(listen_peer, Peer)
        self.listen_peer = listen_peer

    def _data_str(self):
        return (CmdReq._data_str(self) + "listen_peer=%s" % (self.listen_peer))


class UpdatePathResp(CmdResp):
    """ UpdatePath Command Response
    """
    NAME = 'UPDATE_PATH_RESPONSE'

    def __init__(self, req_id, dst_peer, *args, **kwargs):
        CmdResp.__init__(self, req_id, dst_peer, *args, **kwargs)

    def to_json(self):
        return json.dumps({
            "error"      : self.error,
            "error_info" : self.error_info,
            "req_id"     : self.req_id,
            "NAME"       : self.NAME
        })


class DeleteBiPathReq(CmdReq):
    """ DeleteBiPath Command Requset
    """
    NAME = 'DELETE_BI_PATH_REQUEST'
    cls_dict = {'listen_peer': Peer}

    def __init__(self, req_id, buf, path_id, listen_peer, *args, **kwargs):
        CmdReq.__init__(self, req_id, buf, *args, **kwargs)
        self.path_id = path_id
        assert isinstance(listen_peer, Peer)
        self.listen_peer = listen_peer

    def _data_str(self):
        return (CmdReq._data_str(self) +
               ",path_id=%s,listen_peer=%s" %
                (self.path_id, self.listen_peer))


class DeleteBiPathResp(CmdResp):
    """ DeleteBiPath Command Response
    """
    NAME = 'DELETE_BI_PATH_RESPONSE'

    def __init__(self, req_id, dst_peer, *args, **kwargs):
        CmdResp.__init__(self, req_id, dst_peer, *args, **kwargs)

    def to_json(self):
        return json.dumps({
            "error"      : self.error,
            "error_info" : self.error_info,
            "req_id"     : self.req_id,
            "NAME"       : self.NAME
        })


class OptimizeReq(CmdReq):
    """ Optimize Command Requset
    """
    NAME = 'OPTIMIZE_REQUEST'
    cls_dict = {'listen_peer': Peer}

    def __init__(self, req_id, buf, listen_peer, *args, **kwargs):
        CmdReq.__init__(self, req_id, buf, *args, **kwargs)
        assert isinstance(listen_peer, Peer)
        self.listen_peer = listen_peer

    def _data_str(self):
        return (CmdReq._data_str(self) + "listen_peer=%s" % (self.listen_peer))


class OptimizeResp(CmdResp):
    """ Optimize Command Response
    """
    NAME = 'OPTIMIZE_RESPONSE'

    def __init__(self, req_id, dst_peer, *args, **kwargs):
        CmdResp.__init__(self, req_id, dst_peer, *args, **kwargs)

    def to_json(self):
        return json.dumps({
            "error"      : self.error,
            "error_info" : self.error_info,
            "req_id"     : self.req_id,
            "NAME"       : self.NAME
        })


class HeartBeatReq(CmdReq):
    """ Dump Command Requset
    """
    NAME = 'HEART_BEAT_REQUEST'
    cls_dict = {'listen_peer': Peer}

    def __init__(self, req_id, buf, listen_peer, *args, **kwargs):
        CmdReq.__init__(self, req_id, buf, *args, **kwargs)
        assert isinstance(listen_peer, Peer)
        self.listen_peer = listen_peer

    def _data_str(self):
        return (CmdReq._data_str(self) + "listen_peer=%s" % (self.listen_peer))


class DumpReq(CmdReq):
    """ HeartBeat Command Requset
    """
    NAME = 'DUMP_REQUEST'
    cls_dict = {'listen_peer': Peer}

    def __init__(self, req_id, buf, listen_peer, *args, **kwargs):
        CmdReq.__init__(self, req_id, buf, *args, **kwargs)
        assert isinstance(listen_peer, Peer)
        self.listen_peer = listen_peer

    def _data_str(self):
        return (CmdReq._data_str(self) + "listen_peer=%s" % (self.listen_peer))


class DumpResp(CmdResp):
    """ Dump Command Response
    """
    NAME = 'DUMP_RESPONSE'

    def __init__(self, req_id, topology, routes, dst_peer, *args, **kwargs):
        CmdResp.__init__(self, req_id, dst_peer, *args, **kwargs)
        self.topology = topology
        self.routes = routes

    def to_json(self):
        return json.dumps({
            "error"      : self.error,
            "error_info" : self.error_info,
            "topology"   : self.topology,
            "routes"     : self.routes,
            "req_id"     : self.req_id,
            "NAME"       : self.NAME
        })


# ------ utilties ----- #
def create_cmd_from_dict(cls, data, cls_dict = None):
    """create instance from dict automaticaly
        cls_dict  : class definition used by inner attribute.
    """
    cls_dict = cls_dict or {}
    data = __encode_character(data)
    (required_args, defaults_args) = __get_args_spec_with_defaults(cls)

    args = []
    for i in xrange(0, len(required_args)):
        arg = required_args[i]
        _arg = arg
        if arg in cls_dict.keys():
            _cls = cls_dict[arg]
            val = create_cmd_from_dict(_cls, data[_arg])
        else:
            val = data[_arg]
        args.append(val)

    kwargs = {}
    for _key, _value in defaults_args.items():
        if _key in data.keys():
            val = data[_key]
        else:
            val = _value
        if _key in cls_dict.keys():
            _cls = cls_dict[_key]
            log.info("cls = %s" % str(_cls))
            log.info("value = %s" % str(val))
            if val:
                val = create_cmd_from_dict(_cls, val)
        kwargs[_key] = val

    if not defaults_args and not required_args and not args and not kwargs:
        inst = cls(**kwargs)
    else:
        inst = cls(*args, **kwargs)
    return inst


def __encode_character(data):
    """encode dict keys and values.
        try ascii encode -> fail -> utf8 encode
    """
    _data = {}
    for key, value in data.items():
        try:
            _key = key.encode('ascii')
            if isinstance(value, (unicode, str)):
                _value = value.encode('ascii')
            else:
                _value = value
            _data[_key] = _value
            continue
        except UnicodeError:
            pass
        try:
            _key = key.encode('utf-8')
            if isinstance(value, (unicode, str)):
                _value = value.encode('utf-8')
            else:
                _value = value
            _data[_key] = _value
            continue
        except UnicodeError:
            pass
    return _data


def __get_args_spec_with_defaults(cls):
    """get required args and default args from class info.
    """
    args_spec = inspect.getargspec(cls.__init__)
    defaults = args_spec.defaults or []
    if len(defaults) > 0:
        required_args = list(args_spec.args[:-len(defaults)])
        kwargs_names = args_spec.args[-len(defaults):]
    else:
        required_args = list(args_spec.args)
        kwargs_names = []
    required_args.remove('self')
    defaults_args = {}
    for i in xrange(0, len(kwargs_names)):
        defaults_args[kwargs_names[i]] = defaults[i]

    return (required_args, defaults_args)

