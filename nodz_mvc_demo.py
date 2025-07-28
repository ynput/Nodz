#!/usr/bin/env python
"""
Nodz MVC Demo

This script demonstrates how to use the new MVC architecture for Nodz.
It creates a simple node graph with a few nodes and connections.
"""

import sys
from typing import Union
from qtpy import QtCore, QtGui, QtWidgets

from nodz.main import create_nodz_view

# Create application
app = (
    QtWidgets.QApplication(sys.argv)
    if not QtWidgets.QApplication.instance()
    else QtWidgets.QApplication.instance()
)

# Create Nodz view
nodz = create_nodz_view()
nodz.setWindowTitle("Nodz MVC Demo")
nodz.resize(800, 600)
nodz.show()

# Create nodes
nodeA = nodz.api.create_node(
    name="nodeA",
    preset="node_preset_1",
    position=QtCore.QPointF(100, 100),
    help="NodeA has its own special help string!",
)

nodz.api.create_attribute(
    node_name=nodeA,
    name="Aattr1",
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
    help="Just checking this is working!",
)

nodz.api.create_attribute(
    node_name=nodeA,
    name="Aattr2",
    preset="attr_preset_1",
    plug=False,
    socket=False,
    data_type=int,
    help="This attribute is purely decorative.",
)

nodz.api.create_attribute(
    node_name=nodeA,
    name="Aattr3",
    preset="attr_preset_2",
    plug=True,
    socket=True,
    data_type=int,
)

nodz.api.create_attribute(
    node_name=nodeA,
    name="Aattr4",
    preset="attr_preset_2",
    plug=True,
    socket=True,
    data_type=str,
)

nodz.api.create_attribute(
    node_name=nodeA,
    name="Aattr5",
    preset="attr_preset_3",
    plug=True,
    socket=True,
    data_type=int,
    plug_max_connections=1,
    socket_max_connections=-1,
)

nodz.api.create_attribute(
    node_name=nodeA,
    name="Aattr6",
    preset="attr_preset_3",
    plug=True,
    socket=True,
    data_type=int,
    plug_max_connections=1,
    socket_max_connections=-1,
)

# Node B
nodeB = nodz.api.create_node(
    name="nodeB", preset="node_preset_1", position=QtCore.QPointF(300, 100)
)

nodz.api.create_attribute(
    node_name=nodeB,
    name="Battr1",
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.api.create_attribute(
    node_name=nodeB,
    name="Battr2",
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=int,
)

nodz.api.create_attribute(
    node_name=nodeB,
    name="Battr3",
    preset="attr_preset_2",
    plug=True,
    socket=False,
    data_type=int,
)

nodz.api.create_attribute(
    node_name=nodeB,
    name="Battr4",
    preset="attr_preset_3",
    plug=True,
    socket=False,
    data_type=int,
    plug_max_connections=1,
    socket_max_connections=-1,
)

# Node C
nodeC = nodz.api.create_node(
    name="nodeC", preset="node_preset_1", position=QtCore.QPointF(500, 100)
)

nodz.api.create_attribute(
    node_name=nodeC,
    name="Cattr1",
    preset="attr_preset_1",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.api.create_attribute(
    node_name=nodeC,
    name="Cattr2",
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=int,
)

nodz.api.create_attribute(
    node_name=nodeC,
    name="Cattr3",
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.api.create_attribute(
    node_name=nodeC,
    name="Cattr4",
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=str,
)

# Node D
nodeD = nodz.api.create_node(name="nodeD", preset="node_preset_1")

nodz.api.create_attribute(
    nodeD,
    name="Dattr1",
    index=-1,
    preset="attr_preset_3",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.api.create_attribute(
    nodeD,
    name="Dattr2",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    data_type=int,
)

# Node E
nodeE = nodz.api.create_node(name="nodeE", preset="node_preset_1")

nodz.api.create_attribute(
    nodeE,
    name="Eattr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.api.create_attribute(
    nodeE,
    name="Eattr2",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.api.create_attribute(
    nodeE,
    name="Eattr3",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=int,
)

# Node F
nodeF = nodz.api.create_node(name="nodeF", preset="node_preset_1")

nodz.api.create_attribute(
    nodeF,
    name="Fattr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.api.create_attribute(
    nodeF,
    name="Fattr2",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.api.create_attribute(
    nodeF,
    name="Fattr3",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=int,
)

# Create connections
nodz.api.create_connection("nodeB", "Battr2", "nodeA", "Aattr3")
nodz.api.create_connection("nodeB", "Battr1", "nodeA", "Aattr4")
nodz.api.create_connection("nodeC", "Cattr2", "nodeA", "Aattr6")

# Print instructions
print("\nNodz MVC Demo")
print("=============")
print("Keyboard shortcuts:")
print("  A: Frame all nodes")
print("  L: Layout graph")
print("  S: Save graph")
print("  O: Load graph")
print("  C: Clear graph")
print("\nMouse controls:")
print("  Left click: Select nodes")
print("  Middle click + drag: Pan view")
print("  Scroll wheel: Zoom view")
print("  Left click + drag on plug/socket: Create connection")
print("  Double click on connection: Delete connection")

# Run application
if app:
    sys.exit(app.exec_())
