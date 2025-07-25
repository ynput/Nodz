import sys
from typing import Any, Union
from collections import OrderedDict
from qtpy import QtCore, QtGui, QtWidgets

from nodz import view, items
from nodz.api import (
    NodzAdapter,
    GraphModel,
    NodeModel,
    AttrModel,
    ConnectionModel,
)
from nodz.utils import nlog

# This is a standalone example, so we create a QApplication instance.
# If you are integrating Nodz into an existing Qt application, you do not need this.
app = (
    QtWidgets.QApplication(sys.argv)
    if not QtWidgets.QApplication.instance()
    else QtWidgets.QApplication.instance()
)

######################################################################
# Custom Items
######################################################################


class TestNode(items.NodeItem):
    """
    Derived class adding a tooltip on the node and changing the attributes'
    label alignment based on its category (slot, plug or socket).
    """

    def __init__(
        self,
        model: NodeModel,
        config: dict,
        help="%(name)s is a TestNode",
    ) -> None:
        super().__init__(model, config)
        if self.model.kwargs.get("help") != help:
            self.model.kwargs["help"] = help
        self.setToolTip(self.model.kwargs["help"] % self.model.to_dict())

    def paint_attr_label(
        self,
        attr: str,
        painter: QtGui.QPainter,
        rect: QtCore.QRect,
        align_flag: QtCore.Qt.AlignmentFlag = QtCore.Qt.AlignmentFlag.AlignVCenter,
    ):
        attr_data = self.model.attributes[attr]

        align_flag = QtCore.Qt.AlignmentFlag.AlignVCenter | (
            QtCore.Qt.AlignmentFlag.AlignLeft
            if attr_data.socket and not attr_data.plug
            else QtCore.Qt.AlignmentFlag.AlignRight
            if attr_data.plug and not attr_data.socket
            else QtCore.Qt.AlignmentFlag.AlignCenter
        )

        super().paint_attr_label(
            attr,
            painter,
            rect,
            align_flag=align_flag,
        )


class TestPlug(items.PlugItem):
    """
    Derived class adding a tooltip on the plug.
    """

    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        model: AttrModel,
        config: dict,
        help="%(attribute)s is a TestPlug of type %(data_type)s",
    ) -> None:
        super().__init__(
            parent,
            model,
            config,
        )
        if self.model.kwargs.get("help") != help:
            self.model.kwargs["help"] = help
        self.setToolTip(self.model.kwargs["help"] % self.model.to_dict())


class TestSocket(items.SocketItem):
    """
    Derived class adding a tooltip on the socket.
    """

    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        model: AttrModel,
        config: dict,
        help="%(attribute)s  is a TestSocket of type %(data_type)s",
    ) -> None:
        super().__init__(
            parent,
            model,
            config,
        )
        if self.model.kwargs.get("help") != help:
            self.model.kwargs["help"] = help
        self.setToolTip(self.model.kwargs["help"] % self.model.to_dict())


class TestConnection(items.ConnectionItem):
    def __init__(
        self,
        source_point: QtCore.QPoint,
        target_point: QtCore.QPoint,
        source: items.SlotItem,
        target: Union[items.SlotItem, None],
    ) -> None:
        super().__init__(source_point, target_point, source, target)

    def set_connection_color(self, color):
        self._pen.setColor(color)


# We can create a new factory inheriting from NodeFactory to implement
# custom logic when instancing items.
class TestFactory(items.ItemFactory):
    def create_connection_item(
        self,
        source_point: QtCore.QPoint,
        target_point: QtCore.QPoint,
        source: items.SlotItem,
        target: Union[items.SlotItem, None],
    ) -> items.ConnectionItem:
        c = TestConnection(source_point, target_point, source, target)
        if source.model.data_type is str:
            c.set_connection_color("#55AA55")
        return c


# We replace some of the standard item classes with our own.
test_factory = TestFactory(
    node_cls=TestNode, plug_cls=TestPlug, socket_cls=TestSocket
)

######################################################################
# Test Adapter
######################################################################


class TestAdapter(NodzAdapter):
    def to_graph_model(self, data: Any) -> GraphModel:
        graph = GraphModel()

        # Create nodes and attributes from data
        for node_name, node_data in data["graph_data"].items():
            node = NodeModel(
                name=node_name,
                preset=node_data.get("preset", "node_default"),
                alternate=node_data.get("alternate", False),
                kwargs=node_data.get("kwargs", {}),
            )
            for attr_name, attr_data in node_data.get(
                "attributes", {}
            ).items():
                try:
                    node.attributes[attr_name] = AttrModel(
                        attribute=attr_name, index=-1, **attr_data
                    )
                except TypeError:
                    node.attributes[attr_name] = AttrModel(**attr_data)
            graph.nodes[node_name] = node

        for src_node, src_attr, dst_node, dst_attr in data["connections_data"]:
            graph.add_connection(
                ConnectionModel(src_node, src_attr, dst_node, dst_attr)
            )

        return graph

    def from_graph_model(self, data: GraphModel) -> Any:
        nlog.info(
            f"GRAPH model update: nodes: {list(data.nodes.keys())} with "
            f"{len(data.connections)} connections"
        )
        # delete missing nodes
        for name in list(self.client_model["graph_data"].keys()):
            if name not in data.nodes:
                del self.client_model["graph_data"][name]
        # add new nodes
        for name, model in data.nodes.items():
            self.client_model["graph_data"][name] = model.to_dict()
        # add new connections
        for con in data.connections:
            con_tuple = (
                con.plug_node,
                con.plug_attr,
                con.socket_node,
                con.socket_attr,
            )
            if con_tuple not in self.client_model["connections_data"]:
                self.client_model["connections_data"].append(con_tuple)
        # delete missing connections
        for con in self.client_model["connections_data"]:
            con_model = ConnectionModel(*con)
            if con_model not in data.connections:
                self.client_model["connections_data"].pop(
                    self.client_model["connections_data"].index(con)
                )

    def from_node_model(self, data: NodeModel) -> Any:
        nlog.info(
            f"NODE model update: {data.name} with "
            f"{list(data.attributes.keys())}"
        )

    def from_connection_model(self, data: ConnectionModel) -> Any:
        nlog.info(f"CONNECTION model update: {data}")


######################################################################
# Test Model Data
######################################################################

client_model = {
    "graph_data": {
        "nodeA": {
            "preset": "node_preset_1",
            "alternate": True,
            "kwargs": {"help": "NodeA has its own special help string!"},
            "attributes": OrderedDict(
                {
                    "Aattr1": {
                        "preset": "attr_preset_1",
                        "plug": True,
                        "socket": False,
                        "data_type": str,
                        "kwargs": {
                            "help": "Just checking this is working!",
                        },
                    },
                    "Aattr2": {
                        "preset": "attr_preset_1",
                        "plug": False,
                        "socket": False,
                        "data_type": int,
                        "kwargs": {
                            "help": "This attribute is purely decorative.",
                        },
                    },
                    "Aattr3": {
                        "preset": "attr_preset_2",
                        "plug": True,
                        "socket": True,
                        "data_type": int,
                    },
                    "Aattr4": {
                        "preset": "attr_preset_2",
                        "plug": True,
                        "socket": True,
                        "data_type": str,
                    },
                    "Aattr5": {
                        "preset": "attr_preset_3",
                        "plug": True,
                        "socket": True,
                        "data_type": Union[int, str],
                        "plug_max_connections": 1,
                        "socket_max_connections": -1,
                    },
                    "Aattr6": {
                        "preset": "attr_preset_3",
                        "plug": True,
                        "socket": True,
                        "data_type": int,
                        "plug_max_connections": 1,
                        "socket_max_connections": -1,
                    },
                    "Aattr7 Any": {
                        "preset": "attr_preset_3",
                        "plug": True,
                        "socket": True,
                        "data_type": Any,
                        "plug_max_connections": 1,
                        "socket_max_connections": -1,
                    },
                }
            ),
        },
        "nodeB": {
            "preset": "node_preset_1",
            "alternate": True,
            "attributes": OrderedDict(
                {
                    "Battr1": {
                        "preset": "attr_preset_1",
                        "plug": True,
                        "socket": False,
                        "data_type": str,
                    },
                    "Battr2": {
                        "preset": "attr_preset_1",
                        "plug": True,
                        "socket": False,
                        "data_type": int,
                    },
                    "Battr3": {
                        "preset": "attr_preset_2",
                        "plug": True,
                        "socket": False,
                        "data_type": int,
                    },
                    "Battr4": {
                        "preset": "attr_preset_3",
                        "plug": True,
                        "socket": False,
                        "data_type": int,
                        "plug_max_connections": 1,
                        "socket_max_connections": -1,
                    },
                }
            ),
        },
        "nodeC": {
            "preset": "node_preset_1",
            "alternate": True,
            "attributes": OrderedDict(
                {
                    "Cattr1": {
                        "preset": "attr_preset_1",
                        "plug": False,
                        "socket": True,
                        "data_type": str,
                    },
                    "Cattr2": {
                        "preset": "attr_preset_1",
                        "plug": True,
                        "socket": False,
                        "data_type": int,
                    },
                    "Cattr3": {
                        "preset": "attr_preset_1",
                        "plug": True,
                        "socket": False,
                        "data_type": str,
                    },
                    "Cattr4": {
                        "preset": "attr_preset_2",
                        "plug": False,
                        "socket": True,
                        "data_type": str,
                    },
                    "Cattr5": {
                        "preset": "attr_preset_2",
                        "plug": False,
                        "socket": True,
                        "data_type": int,
                    },
                    "Cattr6": {
                        "preset": "attr_preset_3",
                        "plug": True,
                        "socket": False,
                        "data_type": str,
                    },
                    "Cattr7": {
                        "preset": "attr_preset_3",
                        "plug": True,
                        "socket": False,
                        "data_type": str,
                    },
                    "Cattr8": {
                        "preset": "attr_preset_3",
                        "plug": True,
                        "socket": False,
                        "data_type": int,
                    },
                }
            ),
        },
        "nodeD": {
            "preset": "node_preset_1",
            "alternate": True,
            "attributes": OrderedDict(
                {
                    "Dattr1": {
                        "preset": "attr_preset_3",
                        "plug": False,
                        "socket": True,
                        "data_type": str,
                    },
                    "Dattr2": {
                        "preset": "attr_preset_3",
                        "plug": True,
                        "socket": False,
                        "data_type": int,
                    },
                    "Dattr3 Union": {
                        "preset": "attr_preset_3",
                        "plug": False,
                        "socket": True,
                        "data_type": Union[str, int],
                    },
                }
            ),
        },
        "nodeE": {
            "preset": "node_preset_1",
            "alternate": True,
            "attributes": OrderedDict(
                {
                    "Eattr1": {
                        "preset": "attr_preset_1",
                        "plug": True,
                        "socket": False,
                        "data_type": str,
                    },
                    "Eattr2": {
                        "preset": "attr_preset_2",
                        "plug": False,
                        "socket": True,
                        "data_type": str,
                    },
                    "Eattr3": {
                        "preset": "attr_preset_2",
                        "plug": False,
                        "socket": True,
                        "data_type": int,
                    },
                }
            ),
        },
        "nodeF": {
            "preset": "node_preset_1",
            "alternate": True,
            "attributes": OrderedDict(
                {
                    "Fattr1": {
                        "preset": "attr_preset_1",
                        "plug": True,
                        "socket": False,
                        "data_type": str,
                    },
                    "Fattr2": {
                        "preset": "attr_preset_2",
                        "plug": False,
                        "socket": True,
                        "data_type": str,
                    },
                    "Fattr3": {
                        "preset": "attr_preset_2",
                        "plug": False,
                        "socket": True,
                        "data_type": int,
                    },
                }
            ),
        },
    },
    "connections_data": [
        ("nodeB", "Battr2", "nodeA", "Aattr3"),
        ("nodeB", "Battr1", "nodeA", "Aattr4"),
        ("nodeD", "Dattr2", "nodeA", "Aattr6"),
        ("nodeE", "Eattr1", "nodeF", "Fattr2"),
    ],
}

######################################################################
# Setup and initialization
######################################################################

# Create the Nodz view.
nodz = view.Nodz(None)
nodz.setWindowTitle("Nodz Model API Demo")
nodz.initialize(node_factory=test_factory, adapter=TestAdapter(client_model))
nodz.show()

######################################################################
# Test Model API
######################################################################

nodz.model_api.update_view(client_model)


# --- The rest of the script remains for demonstrating dynamic operations ---

# Please note that this is a local test so once the graph is cleared
# and reloaded, all the local variables are not valid anymore, which
# means the following code to alter nodes won't work but saving/loading/
# clearing/evaluating will.

# Get a reference to a node model for manipulation
nodeC = client_model["graph_data"]["nodeC"]

# Attributes Edition
# Move first attribute to the end
first_attr_name = next(iter(nodeC["attributes"]))
# first_attr = nodeC["attributes"].pop(first_attr_name)
nodeC["attributes"][first_attr_name] = nodeC["attributes"].pop(first_attr_name)
nodz.model_api.update_view(client_model)

# Rename last attribute
last_attr_name = next(reversed(nodeC["attributes"]))
nodeC["attributes"]["NewAttrName"] = nodeC["attributes"].pop(last_attr_name)
nodz.model_api.update_view(client_model)

# Attributes Deletion - delete last attribute
last_attr_name = next(reversed(nodeC["attributes"]))
nodeC["attributes"].pop(last_attr_name)
nodz.model_api.update_view(client_model)

# Nodes Edition - rename node
client_model["graph_data"]["newNodeName"] = client_model["graph_data"].pop(
    "nodeC"
)
nodz.model_api.update_view(client_model)

# Nodes Deletion
del client_model["graph_data"]["newNodeName"]
nodz.model_api.update_view(client_model)

# Graph
nlog.info(f"graph evaluation = {nodz.api.evaluate_graph()}")

nodz.api.save_graph(file_path="nodz_demo_model_graph.json")

nodz.api.clear_graph()

nodz.model_api.load_graph(file_path="nodz_demo_model_graph.json")


# test view -> data model communication
print()
nlog.info("test view -> data model communication ============================")
test_node = nodz.api.create_node("test node")
nodz.api.create_attribute(
    test_node, name="T_attr1", plug=True, socket=False, data_type=str
)
nodz.api.edit_node(test_node, "test node renamed")

nodz._layout_graph()

if app:
    # command line stand alone test... run our own event loop
    app.exec_()
