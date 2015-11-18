# -*- coding: utf-8 -*-
"""
protocols.base
~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.

"""
import logging
import types

log = logging.getLogger('pox.protocols.base')
prot = None
name = ''
OsiLayer = 0


def process(packet):
    raise NotImplementedError("should be implemented.")


def extract(packet, prot):
    try:
        if not isinstance(prot, str):
            if isinstance(prot, (types.ClassType, types.TypeType)):
                prot = prot.__name__
            else:
                prot = prot.__class__.__name__
        if packet.parsed:
            return packet.find(prot)

    except Exception as inst:
        log.debug('not a %s package' % str(prot))
        log.exception(inst)

    return None


def buildResponse(self, req, pkt):
  resp = None
  return resp


def parse(packet, name):
  try:
    p = packet.find(name)
    if p is None:
      return (False, None)
  except:
    return (False, None)

  return (True, p)

