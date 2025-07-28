# Nodz Unified API Guide

This guide explains the enhanced unified API facade for Nodz, which provides a clean, consistent interface that hides the complexity of the underlying MVC architecture.

## Overview

The `NodzAPI` class serves as a unified facade that provides:
- **Consistent Interface**: All operations use the same naming conventions and parameter patterns
- **Comprehensive Functionality**: Complete coverage of node graph operations
- **Error Handling**: Proper exception handling with descriptive error messages
- **Utility Methods**: Helper functions for common graph analysis tasks
- **Documentation**: Extensive docstrings for all methods

## Basic Usage

```python
from nodz.main import create_nodz_view

# Create a Nodz view
nodz = create_nodz_view()
nodz.show()

# Access the unified API
api = nodz.api
```

## API Categories

### 1. Node Operations

#### Creating Nodes
```python
# Basic node creation
node_name = api.create_node("MyNode")

# Advanced node creation with options
node_name = api.create_node(
    name="ProcessNode",
    preset="node_preset_1",
    position=QtCore.QPointF(100, 100),
    alternate=True,
    description="Custom description"
)
```

#### Managing Nodes
```python
# Check if node exists
if api.node_exists("MyNode"):
    print("Node exists")

# Get all node names
nodes = api.get_node_names()

# Rename a node
api.rename_node("OldName", "NewName")

# Delete a node
api.delete_node("MyNode")

# Get/set node position
pos = api.get_node_position("MyNode")
api.set_node_position("MyNode", QtCore.QPointF(200, 200))
```

### 2. Attribute Operations

#### Creating Attributes
```python
# Create a plug (output) attribute
api.create_attribute(
    node_name="MyNode",
    name="output",
    plug=True,
    socket=False,
    data_type=str
)

# Create a socket (input) attribute
api.create_attribute(
    node_name="MyNode",
    name="input",
    plug=False,
    socket=True,
    data_type=str
)

# Create a bidirectional attribute
api.create_attribute(
    node_name="MyNode",
    name="data",
    plug=True,
    socket=True,
    data_type=int,
    plug_max_connections=1,
    socket_max_connections=1
)
```

#### Managing Attributes
```python
# Get node attributes
attrs = api.get_node_attributes("MyNode")

# Check if attribute exists
if api.attribute_exists("MyNode", "output"):
    print("Attribute exists")

# Edit attribute
api.edit_attribute("MyNode", "old_name", new_name="new_name")

# Delete attribute
api.delete_attribute("MyNode", "output")
```

### 3. Connection Operations

#### Creating Connections
```python
# Connect two nodes
api.create_connection(
    source_node="NodeA",
    source_attr="output",
    target_node="NodeB",
    target_attr="input"
)
```

#### Managing Connections
```python
# Get all connections
connections = api.get_connections()
for src_node, src_attr, tgt_node, tgt_attr in connections:
    print(f"{src_node}.{src_attr} -> {tgt_node}.{tgt_attr}")

# Check if connection exists
exists = api.connection_exists("NodeA", "output", "NodeB", "input")

# Get connections for a specific node
node_connections = api.get_node_connections("MyNode")

# Delete connection
api.delete_connection("NodeA", "output", "NodeB", "input")
```

### 4. Graph Operations

#### Save/Load
```python
# Save graph to file
api.save_graph("my_graph.json")

# Load graph from file
api.load_graph("my_graph.json")

# Clear entire graph
api.clear_graph()
```

#### Graph Analysis
```python
# Get graph statistics
stats = api.get_graph_stats()
print(f"Nodes: {stats['nodes']}, Connections: {stats['connections']}")

# Evaluate graph (get connection list)
evaluation = api.evaluate_graph()

# Validate graph integrity
errors = api.validate_graph()
if errors:
    print("Validation errors:", errors)
```

### 5. Advanced Graph Analysis

#### Dependency Analysis
```python
# Get upstream dependencies
upstream = api.get_upstream_nodes("MyNode")
print(f"Nodes that feed into MyNode: {upstream}")

# Get downstream dependencies
downstream = api.get_downstream_nodes("MyNode")
print(f"Nodes that MyNode feeds into: {downstream}")
```

#### Cycle Detection
```python
# Find cycles in the graph
cycles = api.find_cycles()
if cycles:
    print(f"Found cycles: {cycles}")
else:
    print("Graph is acyclic")
```

#### Execution Order
```python
# Get topological execution order
try:
    order = api.get_execution_order()
    print(f"Execute nodes in this order: {order}")
except ValueError as e:
    print(f"Cannot determine order: {e}")  # Graph has cycles
```

## Error Handling

The API uses a comprehensive exception hierarchy:

```python
from nodz.controllers import (
    NodzError,           # Base exception
    NodeError,           # Node-related errors
    NodeNotFoundError,   # Node doesn't exist
    NodeExistsError,     # Node already exists
    AttributeError,      # Attribute-related errors
    AttributeNotFoundError,  # Attribute doesn't exist
    ConnectionError,     # Connection-related errors
    IncompatibleTypesError   # Type mismatch
)

try:
    api.create_node("ExistingNode")
except NodeExistsError as e:
    print(f"Node already exists: {e.node_name}")
except NodzError as e:
    print(f"General error: {e}")
```

## Best Practices

### 1. Error Handling
Always wrap API calls in try-except blocks for production code:

```python
try:
    api.create_connection("NodeA", "out", "NodeB", "in")
except NodeNotFoundError as e:
    print(f"Node not found: {e.node_name}")
except AttributeNotFoundError as e:
    print(f"Attribute not found: {e.node_name}.{e.attr_name}")
except IncompatibleTypesError as e:
    print(f"Type mismatch: {e.source_type} -> {e.target_type}")
```

### 2. Validation
Validate your graph before critical operations:

```python
errors = api.validate_graph()
if not errors:
    # Safe to proceed
    order = api.get_execution_order()
else:
    print("Fix these issues first:", errors)
```

### 3. Existence Checks
Check existence before operations to avoid exceptions:

```python
if api.node_exists("MyNode") and api.attribute_exists("MyNode", "output"):
    api.create_connection("MyNode", "output", "OtherNode", "input")
```

### 4. Graph Analysis
Use analysis methods to understand your graph:

```python
# Check for cycles before execution
cycles = api.find_cycles()
if not cycles:
    execution_order = api.get_execution_order()
    for node in execution_order:
        # Execute node
        pass
```

## Complete Example

Here's a complete example that demonstrates the unified API:

```python
from nodz.main import create_nodz_view
from qtpy import QtCore, QtWidgets
import sys

# Create application and view
app = QtWidgets.QApplication(sys.argv)
nodz = create_nodz_view()
api = nodz.api

try:
    # Create nodes
    input_node = api.create_node("Input", position=QtCore.QPointF(0, 0))
    process_node = api.create_node("Process", position=QtCore.QPointF(200, 0))
    output_node = api.create_node("Output", position=QtCore.QPointF(400, 0))

    # Create attributes
    api.create_attribute(input_node, "data_out", plug=True, socket=False, data_type=str)
    api.create_attribute(process_node, "data_in", plug=False, socket=True, data_type=str)
    api.create_attribute(process_node, "result_out", plug=True, socket=False, data_type=str)
    api.create_attribute(output_node, "data_in", plug=False, socket=True, data_type=str)

    # Create connections
    api.create_connection("Input", "data_out", "Process", "data_in")
    api.create_connection("Process", "result_out", "Output", "data_in")

    # Analyze graph
    print(f"Graph stats: {api.get_graph_stats()}")
    print(f"Execution order: {api.get_execution_order()}")

    # Save graph
    api.save_graph("example_graph.json")

    # Show the view
    nodz.show()
    sys.exit(app.exec_())

except Exception as e:
    print(f"Error: {e}")
```

## Migration from Old API

If you're migrating from the old dual-API system (CoreAPI/ModelAPI), here's how the methods map:

| Old API | New Unified API |
|---------|----------------|
| `core_api.create_node()` | `api.create_node()` |
| `core_api.delete_node()` | `api.delete_node()` |
| `model_api.update_view()` | Not needed (automatic) |
| `core_api.save_graph()` | `api.save_graph()` |
| `core_api.load_graph()` | `api.load_graph()` |
| `core_api.evaluate_graph()` | `api.evaluate_graph()` |

The unified API provides all the functionality of both old APIs in a single, consistent interface.

## Conclusion

The unified API facade provides a clean, powerful interface for working with Nodz graphs. It hides the complexity of the underlying MVC architecture while providing comprehensive functionality for creating, manipulating, and analyzing node graphs.

Key benefits:
- **Simplicity**: Single API for all operations
- **Consistency**: Uniform naming and parameter patterns
- **Completeness**: Full coverage of graph operations
- **Robustness**: Comprehensive error handling
- **Analysis**: Built-in graph analysis tools
- **Documentation**: Extensive inline documentation

For more examples, see the demo files:
- `nodz_mvc_demo.py` - Basic MVC demonstration
- `nodz_unified_api_demo.py` - Comprehensive API demonstration