import matplotlib.pyplot as plt
import networkx as nx


def draw(G, labels = False, filename="graph.png"):
    plt.close()
    options = {
        'node_color': 'black',
        'node_size': 100,
        'width': 3,
    }
    nx.draw(G, with_labels = labels)
    plt.savefig(filename)
