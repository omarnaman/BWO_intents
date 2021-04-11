#!/usr/bin/env python3

from utilClasses import Intent
import networkx as nx
from networkx.utils import pairwise


class Graph(nx.Graph):

    hops = None

    def __init__(self, file=None) -> None:
        super(Graph, self).__init__()
        self.hops = None
        if file is not None:
            self.read_edgelist(file)


    def sorted_edgelist(self, node, destination, dec = False):
        l = []
        for u in self[node]:
            cost = self.hops[destination][u]
            cap = self[node][u]["remaining_capacity"]
            l.append((u, cap, cost))
        return sorted(l, key=lambda x: (x[2], x[1]), reverse=dec) 
        
    def read_edgelist(self, file="g.graph") -> dict:
        with open(file, 'r') as f:
            edges = f.readlines()
            for edge in edges:
                if len(edge) < 2:
                    continue
                s, d, cap = edge.split()
                cap = int(cap)
                self.add_edge(s, d, max_capacity=cap, remaining_capacity=cap)
        self.hops = dict.fromkeys(self.nodes)
        for key in self.hops:
            self.hops[key] = dict.fromkeys(self.nodes, None)
        return self.edges


    def init_hops_from_edgelist(self):
        self.hops = dict.fromkeys(self.nodes())
        for key in self.hops:
            self.hops[key] = dict.fromkeys(self.nodes, None)

    def bfs(self, source):
        q = [source]
        vis = dict.fromkeys(self.nodes, False)
        self.hops[source][source] = 0
        cost = 0
        vis[source] = True
        while len(q) != 0:
            size = len(q)
            while size > 0:
                s = q[0]
                size -= 1
                q = q[1:]
                for d in self[s]:
                    if vis[d]:
                        continue
                    self.hops[source][d] = cost + 1
                    vis[d] = True
                    q.append(d)
            cost += 1

        return self.hops[source]

    
    def _astar(self, source, destination, min_link):

        if self._vis[source]:
            return False
        self._vis[source] = True
        if source == destination:
            return True
        for d, cap, _ in self.sorted_edgelist(source, destination):
                if cap < min_link:
                    continue
                if self._vis[d]:
                    continue
                self._path[d] = source
                ret = self._astar(d, destination, min_link)
                if ret:
                    return ret
                self._path[d] = None
        self._vis[source] = False
        return False

    N = 10
    def _astar_N(self, source, destination, min_link):
        if self._vis[source]:
            return False
            
        self._vis[source] = True
        if source == destination:
            self._vis[source] = False
            self._paths.append(self._path.copy())
            if len(self._paths) >= self.N:
                return True
            return False

        for d, cap, _ in self.sorted_edgelist(source, destination):
                if cap < min_link:
                    continue
                if self._vis[d]:
                    continue
                self._path[d] = source
                ret = self._astar_N(d, destination, min_link)
                if ret:
                    return ret
                self._path[d] = None
        self._vis[source] = False
        return False

    def astar_N(self, source, destination, min_link):
        self._paths = []
        self._vis = dict.fromkeys(self.nodes, False)
        self._path = dict.fromkeys(self.nodes, None)
        self.bfs(destination)
        
        res = self._astar(source, destination, min_link)
        if not res:
            return None
        node = destination
        path = []
        while node is not None:
            path.append(node)
            node = self._path[node]

        return list(reversed(path))

    def astar(self, source, destination, min_link):
        self._paths = []
        self._vis = dict.fromkeys(self.nodes, False)
        self._path = dict.fromkeys(self.nodes, None)
        self.bfs(destination)
        
        self._astar_N(source, destination, min_link)
        # [print(path) for path in self._paths]
        for rec_path in self._paths:
            node = destination
            path = []
            while node is not None:
                path.append(node)
                node = rec_path[node]

            return list(reversed(path))
        return None

    def greedy_alloc(self, intents):
        intents = sorted(intents, key=lambda x: x.required_bw, reverse=True)
        flows = []
        # self.reset_capacities()
        for intent in intents:
            source = intent.src_host
            destination = intent.dst_host
            req = intent.required_bw
            path = self.astar(source, destination, req)
            if path is None:
                return False # No Solution
            self.allocate_flow(path, req)
            flows.append((intent, path))
        return flows
        

def main():
    g = Graph("g.graph")
    # g.astar("1", "5", 5)
    print(g.hops)

if __name__=="__main__":
    main()