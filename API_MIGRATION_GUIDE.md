# Nodz API Migration Guide

## Overview

This guide helps developers migrate from the legacy Nodz API (pre-MVC architecture) to the new unified API with clean MVC architecture. The new version introduces significant improvements in code organization, maintainability, and functionality while providing a more consistent and powerful API.

## Table of Contents

1. [Architecture Changes](#architecture-changes)
2. [Breaking Changes](#breaking-changes)
3. [API Comparison](#api-comparison)
4. [Migration Examples](#migration-examples)
5. [New Features](#new-features)
6. [Troubleshooting](#troubleshooting)

---

## Architecture Changes

### Old Architecture (Legacy)
- **Monolithic Design**: Single `nodz_main.py` file (~2127 lines)
- **Direct View Manipulation**: Direct interaction with Qt graphics items
- **No Separation of Concerns**: Business logic mixed with UI code
- **Limited Error Handling**: Basic print statements for errors
- **Node Object References**: API methods required actual node objects

### New Architecture (MVC)
- **Model-View-Controller Pattern**: Clean separation of concerns
- **Modular Design**: Organized into separate modules (`models.py`, `views.py`, `controllers.py`, `main.py`)
- **Unified API Facade**: Single `NodzAPI` class for all operations
- **String-Based References**: API methods use node names (strings) instead of objects
- **Comprehensive Error Handling**: Custom exception hierarchy with descriptive messages

### File Structure Comparison

**Legacy Structure:**
```
├── nodz_main.py          # Everything in one file
├── nodz_utils.py         # Utilities
├── nodz_demo.py          # Demo
└── default_config.json   # Configuration
```

**New Structure:**
```
├── nodz/
│   ├── __init__.py       # Package initialization
│   ├── main.py           # Main view and factory functions
│   ├── models.py         # Data models
│   ├── views.py          # Qt graphics views
│   ├── controllers.py    # Business logic and unified API
│   ├── utils.py          # Utilities
│   └── default_config.json
├── nodz_mvc_demo.py      # MVC demo
└── nodz_unified_api_demo.py  # Unified API demo
```

---

## Breaking Changes

### 1. Import Changes

**Legacy:**
```python
import nodz_main
nodz = nodz_main.Nodz(None)
```

**New:**
```python
from nodz.main import create_nodz_view
nodz = create_nodz_view()
```

### 2. Initialization Changes

**Legacy:**
```python
nodz = nodz_main.Nodz(None)
nodz.loadConfig(configPath)
nodz.initialize()
```

**New:**
```python
# Configuration is loaded automatically
nodz = create_nodz_view()
# Access the unified API
api = nodz.api
```

### 3. Node Reference Changes

**Legacy:** Methods required node objects
```python
node = nodz.createNode('myNode')
nodz.createAttribute(node, 'attr1', ...)  # Pass node object
nodz.deleteNode(node)                     # Pass node object
```

**New:** Methods use node names (strings)
```python
api.create_node('myNode')
api.create_attribute('myNode', 'attr1', ...)  # Pass node name
api.delete_node('myNode')                      # Pass node name
```

### 4. Method Name Changes

| Legacy Method        | New Method            | Notes                 |
| -------------------- | --------------------- | --------------------- |
| `createNode()`       | `create_node()`       | Snake case naming     |
| `deleteNode()`       | `delete_node()`       | Snake case naming     |
| `editNode()`         | `rename_node()`       | More descriptive name |
| `createAttribute()`  | `create_attribute()`  | Snake case naming     |
| `deleteAttribute()`  | `delete_attribute()`  | Snake case naming     |
| `editAttribute()`    | `edit_attribute()`    | Snake case naming     |
| `createConnection()` | `create_connection()` | Snake case naming     |
| `saveGraph()`        | `save_graph()`        | Snake case naming     |
| `loadGraph()`        | `load_graph()`        | Snake case naming     |
| `evaluateGraph()`    | `evaluate_graph()`    | Snake case naming     |
| `clearGraph()`       | `clear_graph()`       | Snake case naming     |

### 5. Parameter Changes

**Attribute Operations:**
- Legacy: `deleteAttribute(node, index)` - used index
- New: `delete_attribute(node_name, attr_name)` - uses attribute name

**Node Operations:**
- Legacy: `editNode(node, newName)` - took node object
- New: `rename_node(node_name, new_name)` - takes node name strings

---

## API Comparison

### Node Operations

#### Creating Nodes

**Legacy:**
```python
node = nodz.createNode(name='myNode',
                      preset='node_preset_1',
                      position=QtCore.QPointF(100, 100),
                      alternate=True)
```

**New:**
```python
node_name = api.create_node(name='myNode',
                           preset='node_preset_1',
                           position=QtCore.QPointF(100, 100),
                           alternate=True)
```

#### Deleting Nodes

**Legacy:**
```python
nodz.deleteNode(node)  # Required node object
```

**New:**
```python
api.delete_node('myNode')  # Uses node name
```

#### Renaming Nodes

**Legacy:**
```python
nodz.editNode(node, newName='newNodeName')
```

**New:**
```python
api.rename_node('myNode', 'newNodeName')
```

### Attribute Operations

#### Creating Attributes

**Legacy:**
```python
nodz.createAttribute(node=node,
                    name='attr1',
                    index=-1,
                    preset='attr_preset_1',
                    plug=True,
                    socket=False,
                    dataType=str,
                    plugMaxConnections=-1,
                    socketMaxConnections=1)
```

**New:**
```python
api.create_attribute(node_name='myNode',
                    name='attr1',
                    index=-1,
                    preset='attr_preset_1',
                    plug=True,
                    socket=False,
                    data_type=str,
                    plug_max_connections=-1,
                    socket_max_connections=1)
```

#### Deleting Attributes

**Legacy:**
```python
nodz.deleteAttribute(node, index=0)  # Used index
```

**New:**
```python
api.delete_attribute('myNode', 'attr1')  # Uses attribute name
```

#### Editing Attributes

**Legacy:**
```python
nodz.editAttribute(node, index=0, newName='newAttr', newIndex=1)
```

**New:**
```python
api.edit_attribute('myNode', 'attr1', new_name='newAttr', new_index=1)
```

### Connection Operations

#### Creating Connections

**Legacy:**
```python
nodz.createConnection('sourceNode', 'sourceAttr', 'targetNode', 'targetAttr')
```

**New:**
```python
api.create_connection('sourceNode', 'sourceAttr', 'targetNode', 'targetAttr')
# Same interface - no changes needed!
```

### Graph Operations

#### Saving and Loading

**Legacy:**
```python
nodz.saveGraph('path/to/graph.json')
nodz.loadGraph('path/to/graph.json')
```

**New:**
```python
api.save_graph('path/to/graph.json')
api.load_graph('path/to/graph.json')
```

#### Evaluating Graph

**Legacy:**
```python
connections = nodz.evaluateGraph()
# Returns: [("sourceNode.attr", "targetNode.attr"), ...]
```

**New:**
```python
connections = api.evaluate_graph()
# Returns: [("sourceNode.attr", "targetNode.attr"), ...]
# Same format - no changes needed!
```

---

## Migration Examples

### Complete Migration Example

**Legacy Code:**
```python
import nodz_main
from Qt import QtCore, QtWidgets

# Initialize
app = QtWidgets.QApplication([])
nodz = nodz_main.Nodz(None)
nodz.initialize()
nodz.show()

# Create nodes
nodeA = nodz.createNode('nodeA', 'node_preset_1', QtCore.QPointF(100, 100))
nodeB = nodz.createNode('nodeB', 'node_preset_1', QtCore.QPointF(300, 100))

# Create attributes
nodz.createAttribute(nodeA, 'output', -1, 'attr_preset_1',
                    plug=True, socket=False, dataType=str)
nodz.createAttribute(nodeB, 'input', -1, 'attr_preset_1',
                    plug=False, socket=True, dataType=str)

# Create connection
nodz.createConnection('nodeA', 'output', 'nodeB', 'input')

# Save graph
nodz.saveGraph('my_graph.json')

app.exec_()
```

**New Code:**
```python
from nodz.main import create_nodz_view
from qtpy import QtCore, QtWidgets

# Initialize
app = QtWidgets.QApplication([])
nodz = create_nodz_view()
nodz.show()

# Access unified API
api = nodz.api

# Create nodes
api.create_node('nodeA', 'node_preset_1', QtCore.QPointF(100, 100))
api.create_node('nodeB', 'node_preset_1', QtCore.QPointF(300, 100))

# Create attributes
api.create_attribute('nodeA', 'output', -1, 'attr_preset_1',
                    plug=True, socket=False, data_type=str)
api.create_attribute('nodeB', 'input', -1, 'attr_preset_1',
                    plug=False, socket=True, data_type=str)

# Create connection (same interface!)
api.create_connection('nodeA', 'output', 'nodeB', 'input')

# Save graph
api.save_graph('my_graph.json')

app.exec_()
```

### Signal Connection Migration

**Legacy:**
```python
# Connect signals
nodz.signal_NodeCreated.connect(on_node_created)
nodz.signal_NodeDeleted.connect(on_node_deleted)
nodz.signal_PlugConnected.connect(on_plug_connected)
```

**New:**
```python
# Signals are still available through the view
nodz.api.signals.node_created.connect(on_node_created)
nodz.api.signals.node_deleted.connect(on_node_deleted)
nodz.api.signals.connection_created.connect(on_connection_created)
```

---

## New Features

### 1. Enhanced Error Handling

The new API provides comprehensive error handling with custom exceptions:

```python
from nodz.controllers import (
    NodeNotFoundError,
    NodeExistsError,
    AttributeNotFoundError,
    IncompatibleTypesError,
    ConnectionError
)

try:
    api.create_connection('NodeA', 'output', 'NodeB', 'input')
except NodeNotFoundError as e:
    print(f"Node not found: {e.node_name}")
except IncompatibleTypesError as e:
    print(f"Type mismatch: {e.source_type} -> {e.target_type}")
except ConnectionError as e:
    print(f"Connection error: {e}")
```

### 2. Graph Analysis Tools

```python
# Get graph statistics
stats = api.get_graph_stats()
print(f"Nodes: {stats['nodes']}, Connections: {stats['connections']}")

# Find cycles in the graph
cycles = api.find_cycles()
if cycles:
    print(f"Found cycles: {cycles}")

# Get execution order (topological sort)
try:
    execution_order = api.get_execution_order()
    print(f"Execution order: {execution_order}")
except ValueError:
    print("Graph contains cycles - cannot determine execution order")

# Get node dependencies
upstream = api.get_upstream_nodes('myNode')
downstream = api.get_downstream_nodes('myNode')
```

### 3. Validation Tools

```python
# Validate graph integrity
errors = api.validate_graph()
if errors:
    for error in errors:
        print(f"Validation error: {error}")
else:
    print("Graph is valid")
```

### 4. Utility Methods

```python
# Check existence
if api.node_exists('myNode'):
    print("Node exists")

if api.attribute_exists('myNode', 'myAttr'):
    print("Attribute exists")

if api.connection_exists('NodeA', 'output', 'NodeB', 'input'):
    print("Connection exists")

# Get information
node_names = api.get_node_names()
attributes = api.get_node_attributes('myNode')
connections = api.get_connections()
node_connections = api.get_node_connections('myNode')
```

### 5. Position Management

```python
# Get and set node positions
position = api.get_node_position('myNode')
api.set_node_position('myNode', QtCore.QPointF(200, 150))
```

### 6. Logging Control

```python
# Control logging levels
api.set_logging_level('DEBUG')
current_level = api.get_logging_level()
```

### 7. Viewport Control

```python
# Save and restore viewport state
framing = api.get_viewport_framing()
# ... do something ...
api.set_viewport_framing(framing)  # Restore view
```

---

## Troubleshooting

### Common Migration Issues

#### 1. Import Errors

**Problem:**
```python
ImportError: No module named 'nodz_main'
```

**Solution:**
```python
# Old import
import nodz_main

# New import
from nodz.main import create_nodz_view
```

#### 2. Node Object References

**Problem:**
```python
TypeError: 'str' object has no attribute 'attrs'
```

**Cause:** Trying to use old API methods that expected node objects.

**Solution:**
```python
# Old way - node object required
node = nodz.createNode('myNode')
nodz.createAttribute(node, 'attr1', ...)

# New way - use node name strings
api.create_node('myNode')
api.create_attribute('myNode', 'attr1', ...)
```

#### 3. Attribute Index vs Name

**Problem:**
```python
# Old method using index
nodz.deleteAttribute(node, 0)  # No longer works
```

**Solution:**
```python
# New method using attribute name
api.delete_attribute('myNode', 'attr1')
```

#### 4. Method Name Changes

**Problem:**
```python
AttributeError: 'NodzAPI' object has no attribute 'createNode'
```

**Solution:**
```python
# Old camelCase
nodz.createNode(...)

# New snake_case
api.create_node(...)
```

#### 5. Signal Connection Issues

**Problem:**
```python
AttributeError: 'NodzAPI' object has no attribute 'signal_NodeCreated'
```

**Solution:**
```python
# Signals are accessed through the view or API signals object
nodz.api.signals.node_created.connect(callback)
# or through the view directly if needed
```


### Debugging Tips

1. **Enable Debug Logging**:
   ```python
   api.set_logging_level('DEBUG')
   ```

2. **Use Graph Validation**:
   ```python
   errors = api.validate_graph()
   if errors:
       for error in errors:
           print(f"Graph error: {error}")
   ```

3. **Check Node/Attribute Existence**:
   ```python
   if not api.node_exists('myNode'):
       print("Node doesn't exist!")

   if not api.attribute_exists('myNode', 'myAttr'):
       print("Attribute doesn't exist!")
   ```

### Migration Checklist

- [ ] Update imports from `nodz_main` to `nodz.main`
- [ ] Change initialization from `Nodz()` to `create_nodz_view()`
- [ ] Replace node object references with node name strings
- [ ] Update method names from camelCase to snake_case
- [ ] Change attribute operations from index-based to name-based
- [ ] Update signal connections if used
- [ ] Add error handling with new exception types
- [ ] Test all functionality with the new API
- [ ] Update documentation and comments
- [ ] Consider using new features (graph analysis, validation, etc.)

---

## Conclusion

The new MVC architecture provides a much more robust, maintainable, and feature-rich API while maintaining backward compatibility where possible. The migration effort is primarily focused on updating method calls and parameter passing, with the core functionality remaining the same.

The new unified API offers significant advantages:

- **Better Error Handling**: Comprehensive exception hierarchy
- **Enhanced Functionality**: Graph analysis, validation, and utility methods
- **Cleaner Code**: Consistent naming and parameter conventions
- **Better Maintainability**: Modular architecture with clear separation of concerns

For complex migrations or specific use cases not covered in this guide, please refer to the demo files (`nodz_mvc_demo.py` and `nodz_unified_api_demo.py`) for comprehensive examples.