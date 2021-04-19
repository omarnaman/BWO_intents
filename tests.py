#!/usr/bin/env python3

import unittest
import os
import Graph
graph_dir = os.path.join("tests", "graphs")
intents_dir = os.path.join("tests", "intents")
class TestGraph(unittest.TestCase):
    def do_work(self, graph_number, online=False):
        graph_file = f"g{graph_number}.graph"
        intents_file = f"int{graph_number}.intents"
        graph_file = os.path.join(graph_dir, graph_file)
        graph_file = os.path.abspath(graph_file)
        intents_file = os.path.join(intents_dir, intents_file)
        intents_file = os.path.abspath(intents_file)
        return Graph.main(graph_file, intents_file, online)        
    
    def test_1(self):
        i = 1
        self.assertTrue(self.do_work(i), f"Failed Graph{i}")
    
    def test_2(self):
        i = 2
        self.assertTrue(self.do_work(i), f"Failed Graph{i}")

    def test_1_online(self):
        i = 1
        self.assertTrue(self.do_work(i, True), f"Failed Graph{i}")
    
if __name__=="__main__":
    unittest.main()