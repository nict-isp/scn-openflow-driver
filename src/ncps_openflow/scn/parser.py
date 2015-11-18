# -*- coding: utf-8 -*-
"""
scn.parser
~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from pox.core import core
from ConfigParser import ConfigParser

log = core.getLogger()
NAME='parser'

CONTROLLER = 'CONTROLLER'
IP         = 'IP'
MAC        = 'MAC'
SWITCHS    = 'SWITCHS'
SPEED      = 'SPEED'
PLUGINS    = 'PLUGINS'
TOPOLOGY   = 'TOPOLOGY'
PORTS      = 'PORTS'
INTFNAME   = 'NAME'


class Parser:

    def __init__(self):
        self.fileName = None
        self.config   = None


    def parseFile(self, fileName):
        if not fileName:
            return

        if fileName == self.fileName:
            return

        self.fileName = fileName
        if not self.config:
            self.config = ConfigParser(allow_no_value=True)
            self.config.optionxform = str

        log.info("parseFile %s" % self.fileName)
        return self.config.read(self.fileName)


    def getKeys(self, section):
        if not self.config.has_section(section):
            return []

        return map(lambda x: x[0], self.config.items(section))


    def getValues(self, section):
        if not self.config.has_section(section):
            return []

        return map(lambda x: x[1], self.config.items(section))


    def getKeyValues(self, section):
        kw = {}
        if not self.config.has_section(section):
            return kw

        try:
            for k,v in self.config.items(section):
                kw[k] = v
        except Exception as inst:
            log.exception(inst)

        return kw


    def getValue(self, section, key):
        try:
            return self.config.get(section, key)
        except:
            return None


    def getPlugins(self):
        plugins = {}
        pluginNames = self.getKeys(PLUGINS)
        for plugin in pluginNames:
            kw = self.getKeyValues(plugin)
            plugins[plugin] = kw

        return plugins


    def getSwitchsSections(self):
        res = []
        switchs = self.getValue(TOPOLOGY, SWITCHS)
        if not switchs:
            return res

        res = map(lambda x: x.strip(), switchs.split(','))
        return res


    def getPortsSections(self, section):
        res = []
        ports = self.getValue(section, PORTS)
        if not ports:
            return res

        res = map(lambda x: x.strip(), ports.split(','))
        return res


def launch(fileName):
    if core.hasComponent(NAME):
        return None

    comp = Parser()
    if not comp.parseFile(fileName):
        return

    core.register(NAME, comp)
    return comp

