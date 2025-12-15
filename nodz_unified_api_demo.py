#!/usr/bin/env python
"""
Nodz Unified API Demo

This script demonstrates the enhanced unified API facade for Nodz.
It shows how the API provides a clean, consistent interface that hides
the complexity of the underlying MVC architecture.
"""

import sys
from qtpy import QtCore, QtGui, QtWidgets

from nodz.main import create_nodz_view
from nodz.utils import nlog

# Create application
app = (
    QtWidgets.QApplication(sys.argv)
    if not QtWidgets.QApplication.instance()
    else QtWidgets.QApplication.instance()
)

# Create Nodz view
nodz = create_nodz_view()
nodz.setWindowTitle("Nodz Unified API Demo")
nodz.resize(1000, 700)
nodz.show()

nlog.info("=== Nodz Unified API Demo ===")
nlog.info("This demo showcases the enhanced unified API facade.\n")

# === Node Operations ===
nlog.info("1. Creating nodes...")

# Create nodes with different configurations
input_node = nodz.api.create_node(
    name="InputNode",
    preset="node_preset_1",
    position=QtCore.QPointF(50, 100),
    description="Input data source",
)

process_node = nodz.api.create_node(
    name="ProcessNode",
    preset="node_preset_1",
    position=QtCore.QPointF(300, 100),
    description="Data processing node",
)

output_node = nodz.api.create_node(
    name="OutputNode",
    preset="node_preset_1",
    position=QtCore.QPointF(550, 100),
    description="Output destination",
)

nlog.info(f"Created nodes: {nodz.api.get_node_names()}")

# === Attribute Operations ===
print()
nlog.info("2. Creating attributes...")

# Input node attributes
nodz.api.create_attribute(
    node_name=input_node,
    name="data_out",
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
    help="Output data stream",
)

nodz.api.create_attribute(
    node_name=input_node,
    name="config",
    preset="attr_preset_2",
    plug=False,
    socket=False,
    data_type=dict,
    help="Configuration parameters",
)

# Process node attributes
nodz.api.create_attribute(
    node_name=process_node,
    name="data_in",
    preset="attr_preset_1",
    plug=False,
    socket=True,
    data_type=str,
    help="Input data stream",
)

nodz.api.create_attribute(
    node_name=process_node,
    name="processed_out",
    preset="attr_preset_2",
    plug=True,
    socket=False,
    data_type=str,
    help="Processed data output",
)

nodz.api.create_attribute(
    node_name=process_node,
    name="status",
    preset="attr_preset_3",
    plug=True,
    socket=False,
    data_type=bool,
    help="Processing status",
)

# Output node attributes
nodz.api.create_attribute(
    node_name=output_node,
    name="data_in",
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=str,
    help="Input data to save",
)

nodz.api.create_attribute(
    node_name=output_node,
    name="status_in",
    preset="attr_preset_3",
    plug=False,
    socket=True,
    data_type=bool,
    help="Status input",
)

nlog.info("Attributes created for all nodes")

# === Connection Operations ===
print()
nlog.info("3. Creating connections...")

# Create connections between nodes
nodz.api.create_connection("InputNode", "data_out", "ProcessNode", "data_in")
nodz.api.create_connection("ProcessNode", "processed_out", "OutputNode", "data_in")
nodz.api.create_connection("ProcessNode", "status", "OutputNode", "status_in")

nlog.info(f"Created {len(nodz.api.get_connections())} connections")

# === API Information Methods ===
print()
nlog.info("4. Graph information...")

# Show graph statistics
stats = nodz.api.get_graph_stats()
nlog.info(f"Graph stats: {stats}")

# Show connections
connections = nodz.api.get_connections()
nlog.info("Connections:")
for src_node, src_attr, tgt_node, tgt_attr in connections:
    nlog.info(f"  {src_node}.{src_attr} -> {tgt_node}.{tgt_attr}")

# Show node dependencies
nlog.info(
    f"\nUpstream nodes for ProcessNode: {nodz.api.get_upstream_nodes('ProcessNode')}"
)
nlog.info(
    f"Downstream nodes for ProcessNode: {nodz.api.get_downstream_nodes('ProcessNode')}"
)

# === Graph Analysis ===
print()
nlog.info("5. Graph analysis...")

# Check for cycles
cycles = nodz.api.find_cycles()
if cycles:
    nlog.info(f"Found cycles: {cycles}")
else:
    nlog.info("No cycles found in graph")

# Get execution order
try:
    execution_order = nodz.api.get_execution_order()
    nlog.info(f"Execution order: {execution_order}")
except ValueError as e:
    nlog.info(f"Cannot determine execution order: {e}")

# Validate graph
validation_errors = nodz.api.validate_graph()
if validation_errors:
    nlog.info(f"Validation errors: {validation_errors}")
else:
    nlog.info("Graph validation passed")

# === Utility Operations ===
print()
nlog.info("6. Utility operations...")

# Check existence
nlog.info(f"Node 'ProcessNode' exists: {nodz.api.node_exists('ProcessNode')}")
nlog.info(f"Node 'NonExistent' exists: {nodz.api.node_exists('NonExistent')}")
nlog.info(
    f"Attribute 'ProcessNode.data_in' exists: {nodz.api.attribute_exists('ProcessNode', 'data_in')}"
)

# Get node attributes
attrs = nodz.api.get_node_attributes("ProcessNode")
nlog.info(f"ProcessNode attributes: {attrs}")

# Check specific connection
conn_exists = nodz.api.connection_exists(
    "InputNode", "data_out", "ProcessNode", "data_in"
)
nlog.info(f"Connection InputNode.data_out -> ProcessNode.data_in exists: {conn_exists}")

# === Advanced Operations ===
print()
nlog.info("7. Advanced operations...")

# Create a more complex graph to demonstrate cycles
nodz.api.create_node("CycleNode1", position=QtCore.QPointF(100, 300))
nodz.api.create_node("CycleNode2", position=QtCore.QPointF(300, 300))

nodz.api.create_attribute("CycleNode1", "out", plug=True, socket=False, data_type=int)
nodz.api.create_attribute("CycleNode1", "in", plug=False, socket=True, data_type=int)
nodz.api.create_attribute("CycleNode2", "out", plug=True, socket=False, data_type=int)
nodz.api.create_attribute("CycleNode2", "in", plug=False, socket=True, data_type=int)

# Create a cycle
nodz.api.create_connection("CycleNode1", "out", "CycleNode2", "in")
nodz.api.create_connection("CycleNode2", "out", "CycleNode1", "in")

nlog.info("Created cycle between CycleNode1 and CycleNode2")

# Check for cycles again
cycles = nodz.api.find_cycles()
if cycles:
    nlog.info(f"Found cycles: {cycles}")

# Try to get execution order (should fail due to cycle)
try:
    execution_order = nodz.api.get_execution_order()
    nlog.info(f"Execution order: {execution_order}")
except ValueError as e:
    nlog.info(f"Cannot determine execution order: {e}")

# === Save and Load Operations ===
print()
nlog.info("8. Save and load operations...")

# Save the graph
save_path = "unified_api_demo_graph.json"
nodz.api.save_graph(save_path)
nlog.info(f"Graph saved to {save_path}")

# Show final statistics
final_stats = nodz.api.get_graph_stats()
nlog.info(f"Final graph stats: {final_stats}")

nodz.layout_graph()

# === Instructions ===
print()
nlog.info("" + "=" * 50)
nlog.info("INTERACTIVE DEMO")
nlog.info("=" * 50)
nlog.info("The graph is now loaded and ready for interaction!")
print("")
nlog.info("API Features Demonstrated:")
nlog.info("  ✓ Node creation and management")
nlog.info("  ✓ Attribute creation and management")
nlog.info("  ✓ Connection creation and management")
nlog.info("  ✓ Graph analysis (cycles, execution order)")
nlog.info("  ✓ Graph validation")
nlog.info("  ✓ Utility methods (existence checks, dependencies)")
nlog.info("  ✓ Statistics and information gathering")
nlog.info("  ✓ Save/load functionality")

# Run application
if app:
    sys.exit(app.exec_())
