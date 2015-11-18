# -*- coding: utf-8 -*-
"""
scn.nwgn
~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from pox.core import core
from pox.lib.revent import *

log = core.getLogger()
NAME = 'nwgn'


class NwGN(EventMixin):

    def load_plugins(self):
        log.debug("loadPlugins")
        try:
            parser = core.parser
        except:
            log.warning("No parser")
            return

        plugins = parser.getPlugins()
        priority = []

        import sys
        for p in plugins.keys():
            exec "import scn.plugins.%s" % p
            py_mod = sys.modules['scn.plugins.%s' % p]
            wantComponents = py_mod.__dict__.get('wantComponents', [])
            del py_mod

            for dep in wantComponents:
                if dep not in plugins.keys():
                    log.error("Dependency unmet for %s: %s" % (p, dep))
                    sys.exit(2)

                if dep in priority:
                    priority.remove(dep)

                priority = [dep] + priority

            if p not in priority:
                priority.append(p)

        for p in priority:
            log.info("Load %s" % p)
            kwStr = ''
            for k,v in plugins[p].iteritems():
                kwStr += '%s=%s, ' % (k,v)

            codeStr = 'from scn.plugins.%s import launch' % p
            codeStr += '\nlaunch(%s)\n' % kwStr
            exec codeStr


#./pox.py --no-cli scn.nwgn --inifile=ext/scn/example.ini
def launch(inifile=None):

    if core.hasComponent(NAME):
        return None

    from scn.parser import launch as parser_launch
    res = parser_launch(inifile)
    if inifile != None and not res:
        log.warning("Unable to parse ini file")
        import sys
        sys.exit(2)
        return

    from scn.scnTopology import launch as topology_launch
    topology_launch()

    from scn.scnOFTopology import launch as of_topology_launch
    of_topology_launch()

    from scn.scnDiscovery import launch as discovery_launch
    discovery_launch()

    from scn.scnHostTracker import launch as hosttracker_launch
    hosttracker_launch(arpAware=20, arpSilent=20)

    from protocols.processor import launch as processer_launch
    processer_launch()

    from scn.routing import launch as routing_launch
    routing_launch()

    from log.level import launch as log_level_launch
    log_level_launch(WARNING=True)
    #log_level_launch(INFO=True)
    #log_level_launch(DEBUG=True)

    from log import launch as log_launch
    formatter = "[%(levelname)s][%(asctime)s][%(module)s:%(funcName)s;%(lineno)d] - %(message)s"
    log_launch(format=formatter)

    comp = NwGN()
    comp.load_plugins()
    core.register(NAME, comp)

    return comp

