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
        
    def topk_greedy_allocate(self, intents):
        self.reset_capacities()
        intents = sorted(intents, key=lambda x: x.required_bw, reverse=True)
        flows = []
        # self.reset_capacities()
        for intent in intents:
            source = intent.src_host
            destination = intent.dst_host
            req = intent.required_bw
            paths = self.get_shortest_paths(source, destination, req)
            if len(paths) == 0:
                return False # No Solution
            path = paths[0][0]
            self.allocate_flow(path, req)
            flows.append((intent, path))
        return flows

    # TODO: Convert to Binary Search
    def filter_too_long(self, paths, hop_diff):
        if len(paths) == 0:
            return []
        limit = len(paths[0][0]) + hop_diff
        for i, (path, _) in enumerate(paths):
            if len(path) > limit:
                return paths[:i]
        return paths

    # TODO: Reimplement `shortest_simple_paths` to calculate capacity
    def get_path_capacity(self, path, use_original_capacity=False):
        capacity_key = "remaining_capacity"
        if use_original_capacity:
            capacity_key = "max_capacity"
        if len(path) < 2:
            raise Exception("Invalid path")
        min_edge = self[path[0]][path[1]][capacity_key]
        for u, v in pairwise(path):
            min_edge = min(min_edge, self[u][v][capacity_key])

        return min_edge

    def get_shortest_paths(self, src, dst, required_capacity):
        paths = nx.shortest_simple_paths(self, src, dst)
        path_cap = []
        for path in paths:
            cap = self.get_path_capacity(path)
            if required_capacity <= cap:
                path_cap.append((path, cap))
        path_cap = self.filter_too_long(path_cap, 3)
        path_cap = list(sorted(path_cap, key=lambda x: (len(x[0]), x[1])))
        return path_cap

    def allocate_flow(self, path, req):
        for i, node in enumerate(path[:-1]):
            s, d = node, path[i+1]
            self[s][d]["remaining_capacity"] -= req
            
    def allocate_single(self, intent: Intent):
        source = intent.src_host
        destination = intent.dst_host
        req = intent.required_bw
        paths = self.get_shortest_paths(source, destination, req)
        if len(paths) == 0:
                return False # No Solution
        path = paths[0][0]
        self.allocate_flow(path, req)
        return (intent, path)
    def reset_capacities(self):
        for u, v in self.edges:
            self[u][v]["remaining_capacity"] = self[u][v]["max_capacity"]

if __name__=="__main__":
    main()