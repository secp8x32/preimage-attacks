# -*- coding: utf-8 -*-
import networkx as nx
import matplotlib.pyplot as plt
from multiprocessing import Pool

from utils.constants import BIT_PRED, HASH_INPUT_NBITS, MAX_CONNECTIONS_PER_NODE


class UndirectedGraph(object):

  def __init__(self, prob, size, config, fc_graph=None,
               max_connections=MAX_CONNECTIONS_PER_NODE):
    self.prob = prob
    self.count = 0
    self.verbose = config.verbose
    self.num_workers = config.num_workers
    self.max_connections = max_connections
    self.N, self.n = size  # (number of samples, number of variables)
    if fc_graph is None:
      self.fc_graph = self.createFullyConnectedGraph()
    else:
      self.fc_graph = nx.read_yaml(fc_graph)
    self.graph = self.pruneGraph(self.fc_graph)


  def saveFullyConnectedGraph(self, filename):
    if self.verbose:
      print('Saving fully connected graph as "%s"...' % filename)

    nx.write_yaml(self.fc_graph, filename)


  def saveUndirectedGraph(self, filename):
    if self.verbose:
      print('Saving undirected Bayesian network as "%s"...' % filename)

    nx.write_yaml(self.graph, filename)


  def visualizeGraph(self, img_file):
    if self.verbose:
      print('Visualizing undirected Bayesian network...')

    plt.close()
    nx.draw_spectral(self.graph, with_labels=True)
    plt.savefig(img_file)


  def createFullyConnectedGraph(self):
    graph = nx.Graph()

    self.counter = 0
    m = self.n - HASH_INPUT_NBITS
    max_count = m * (m - 1) / 2

    if self.verbose:
      print('Calculating %d mutual information scores...' % max_count)

    for i in range(self.n):
      # (i, j) score is symmetric to (j, i) score so we only need to
      # calculate an upper-triangular matrix with zeros on the diagonal
      inputs = [(self, i, j, max_count, graph) for j in range(i + 1, self.n)]

      with Pool(self.num_workers) as p:
        p.map(multiprocessingHelperFunc, inputs)

    return graph


  def pruneGraph(self, fc_graph):
    graph = fc_graph.copy()

    prune = True
    while prune:
      prune = False
      for rv in graph.nodes():
        num_neighbors = len(graph[rv])
        if num_neighbors <= self.max_connections:
          continue

        # Prune away least negative edge
        neighbors = [n for n in graph.edges(rv, data='weight')]
        neighbors = list(sorted(neighbors, key=lambda n: n[2]))
        to_remove = neighbors[0] # first one has smallest mutual info score
        graph.remove_edge(to_remove[0], to_remove[1])
        prune = True

    components = [graph.subgraph(c) for c in nx.connected_components(graph)]
    relevant_component = [g for g in components if BIT_PRED in g.nodes()][0]

    if self.verbose:
      print('The optimized BN has %d edges.' % graph.number_of_edges())
      print('\tconnected = {}'.format(len(components) == 1))
      print('\tnum connected components = %d' % len(components))
      largest_cc = max(nx.connected_components(graph), key=len)
      print('\tlargest component has %d nodes' % len(largest_cc))
      print('\tcomponent with bit %d has %d nodes' % (BIT_PRED, relevant_component.number_of_nodes()))

    return relevant_component


def multiprocessingHelperFunc(x):
  """
  A helper function for computing the fully-connected graph is given here
  at top-level due to pickling requirements of Python multiprocessing library
  """
  udg, i, j, max_count, graph = x

  l_bound = 256
  u_bound = 256 + HASH_INPUT_NBITS
  if (l_bound <= i < u_bound) and (l_bound <= j < u_bound):
    return  # No edges between hash input bit random variables

  udg.counter += 1
  weight = udg.prob.iHat([i, j])
  graph.add_edge(i, j, weight=weight)

  if udg.verbose and udg.counter % (max_count / 100) == 0:
    pct_done = 100.0 * udg.counter / max_count
    print('%.2f%% done.' % pct_done)
