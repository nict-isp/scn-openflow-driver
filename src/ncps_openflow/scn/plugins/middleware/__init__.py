"""launch script.
"""
from pox.core import core
log = core.getLogger()

from handler import launch as launch_handler
from handler import NAME
from interface import launch as launch_interface

TRANSPORT = 'transport'
JSON = 'json'
XML  = 'xml'
YAML = 'yaml'
TRANSPORT_TYPES = [JSON, XML, YAML] # ANYTHING ELSE ?


def launch(**kwargs):
    """start trigger.
        called by nwgn.py.
    """

    if core.hasComponent(NAME):
        return

    comp = launch_handler(**kwargs)
    core.register(NAME, comp)

    transport = kwargs.get(TRANSPORT, None)
    if transport not in TRANSPORT_TYPES:
        log.warn("Unkown transport.")
        return

    launch_interface(**kwargs)

    return comp

