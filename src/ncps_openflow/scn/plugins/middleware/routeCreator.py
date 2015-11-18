# -*- coding: utf-8 -*-
"""
scn.plugins.middleware.routeCreator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

from pox.core import core
log = core.getLogger()

class RouteCreatorIF:
    """RouteCreator inteface
    """
    TYPE = ''

    def __init__(self):
        pass

    def estimate_route(self, path_list, auto_apply):
        """estimate links(=route)
          shoud estimate links by path description(src, dst).
          and set links to path.
          install flow table if auto_apply is true.
           - path_list  : List<Path>
           - auto_apply : Boolean
        """
        raise NotImplementedError()


class RoundRobinCreator(RouteCreatorIF):
    """use round robin logic.
       no implementation yet
    """
    TYPE = 'ROUNDROBIN'

    def estimate_route(self, path_list, auto_apply = True):
        pass


class DijkstraRouteCreator(RouteCreatorIF):
    """use Dijkstra logic.
    """
    TYPE = 'DIJKSTRA'

    def estimate_route(self, path_list, auto_apply = True):
        log.info("start Dijkstra estimate")
        if not path_list:
            path_list = []

        if not isinstance(path_list, list):
            path_list = [path_list]

        all_links = core.openflow_discovery.getAllLinks()
        graph = self.create_graph(all_links)

        for path in path_list:
            src_node = core.topology.getHost(path.get_src_ip())
            dst_node = core.topology.getHost(path.get_dst_ip())
            if src_node and dst_node:
                links = self.search_links(src_node.ofp.ofs.dpid, dst_node.ofp.ofs.dpid, graph)
                if not links:
                    log.warn("can not get links [src: %s] ,[dst: %s]" % (src_node, dst_node))
                    return False

                if auto_apply:
                    path.update_links(links)
                else:
                    path.links = links
            else:
                log.warn("not specified [src: %s] or [dst: %s]" % (src_node, dst_node))
                return False

        return path_list

    @classmethod
    def create_graph(cls, links):
        """ create graph map.
           links -- List of ScnLink.

           create dict like below.
           {
               src_dpid1 : {
                   dst_dpid1 : weight,
                   dst_dpid2 : weight,
                   ...
               },
               src_dpid2 : {
                   dst_dpid1 : weight,
                   dst_dpid2 : weight,
                   ...
               }
           }
        """
        graph = {}
        for link in links:
            dstLst = {}
            try:
                dstLst = graph[link.dpid1]
            except KeyError:
                pass

            linkBwUsed = link.getBandwidthUsed()
            if link.stat_unit != "bit":
                linkBwUsed = linkBwUsed*8

            linkBwReserved = 0
            for rsvd in link.reserved:
                conditions = rsvd["conditions"]
                if conditions:
                    bw = conditions.get("bandwidth")
                    if bw:
                        linkBwReserved += bw

            maximumBwNonFree = max(linkBwUsed, linkBwReserved)  # Non Free -> heavy cost.
            if link.stat_unit == "bit":
                maximumBwNonFree = maximumBwNonFree/8

            dstLst[link.dpid2] = maximumBwNonFree
            graph[link.dpid1] = dstLst
        return graph

    @classmethod
    def search_links(cls, src_dpid, dst_dpid, graph):
        """search links represented by dpid.

           src_dpid -- [int] src ofs dpid.
           dst_dpid -- [int] dst ofs dpid.
           graph -- [dict] all ofs weight matrix.

           graph is like below
             {1: {2: 60.7027065744944, 3: 69.40116    28163512, 4: 69.3756246599734},
              2: {1: 60.68642607840347, 3: 69.40112294317312, 4: 69.3756310349918},
              3: {1: 69.35592985381967 , 2: 69.37452179942217, 4: 69.3756310349918},
              4: {1: 60.686398203558156, 2: 60.7027065744944, 3: 60.725970015235205}}
          TODO represent grahp by ScnLink instance.
          <ja> リストなどで計算せずに、ScnLinkオブジェクトのまま計算したほうがよいと思う
        """
        log.info("src=%d, dst=%d, graph=%s" % (int(src_dpid), int(dst_dpid), str(graph)))
        distances = {} # Final distances dict
        predecessor = {} # predecessor dict

        # Fill the dicts with default values
        for node in graph.keys():
            distances[node] = 10**15 # Vertices are unreachable
            predecessor[node] = "" # Vertices have no predecessors

        distances[src_dpid] = 0 # The start vertex needs no move

        unseen_nodes = graph.keys() # All nodes are unseen

        foundDst = False

        if src_dpid not in graph.keys():
            log.warn("no src")
            return []

        while len(unseen_nodes) > 0:
            # Select the node with the lowest value in D (final distance)
            shortest = None
            node = ''
            for temp_node in unseen_nodes:
                if shortest == None:
                    shortest = distances[temp_node]
                    node = temp_node
                elif distances[temp_node] < shortest:
                    shortest = distances[temp_node]
                    node = temp_node

            # Remove the selected node from unseen_nodes
            unseen_nodes.remove(node)

            # For each child (ie: connected vertex) of the current node
            for child_node, child_value in graph[node].items():
                if child_node == dst_dpid:
                    foundDst = True
                if distances[child_node] > distances[node] + child_value:
                    distances[child_node] = distances[node] + child_value
                    # To go to child_node, you have to go through node
                    predecessor[child_node] = node

        if not foundDst:
            log.warn("no dst")
            return []

        # Set a clean path
        path = []
        links = []

        # We begin from the end
        node = dst_dpid
        # While we are not arrived at the beginning
        while not (node == src_dpid):
            if path.count(node) == 0:
                # Insert the predecessor of the current node
                path.insert(0, (predecessor[node], node, graph[predecessor[node]][node]))
                links.insert(0, core.openflow_discovery.getLinkByDpid(predecessor[node], node))
                node = predecessor[node] # The current node becomes its predecessor
            else:
                break

        log.info(map(str, links))
        return links

