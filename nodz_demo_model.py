from typing import Union, Any
from collections import OrderedDict
from qtpy import QtCore, QtGui, QtWidgets
import nodz.view as view
import nodz.items as items
from nodz.utils import nlog
from nodz.data_types import (
    NodeModel,
    AttrModel,
    ConnectionModel,
    GraphModel,
    NodzAdapter,
)

try:
    app = QtWidgets.QApplication([])
except BaseException:
    # I guess we're running somewhere that already has a QApp created
    app = None

######################################################################
# Test subclasses and factory
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
    def from_graph_model(self, data: GraphModel) -> Any:
        nlog.info(
            f"GRAPH model update: nodes: {list(data.nodes.keys())} with "
            f"{len(data.connections)} connections"
        )

    def from_node_model(self, data: NodeModel) -> Any:
        nlog.info(
            f"NODE model update: {data.name} with "
            f"{list(data.attributes.keys())}"
        )

    def from_connection_model(self, data: ConnectionModel) -> Any:
        nlog.info(f"CONNECTION model update: {data}")


######################################################################
# Setup and initialization
######################################################################

nodz = view.Nodz(
    None,
)
nodz.setWindowTitle("Nodz Demo Model")
nodz.initialize(node_factory=test_factory, adapter=TestAdapter())
nodz.show()


######################################################################
# Test Model API
######################################################################

graph = GraphModel()

# Node A
nodeA = NodeModel(
    name="nodeA",
    alternate=True,
    preset="node_preset_1",
    kwargs={
        "help": "NodeA has it's own special help string !",
    },
)
graph.nodes[nodeA.name] = nodeA
# nlog.info(f"diff = {nodz.model_api.diff_graph(graph)}")
nodz.model_api.update_view(graph)
# nodz.model_api.update_view(ModelEntity.Node, ModelEdit.Create, nodeA)

nodeA.attributes["Aattr1"] = AttrModel(
    attribute="Aattr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
    kwargs={"help": "Just checking this is working !"},
)
nodeA.attributes["Aattr2"] = AttrModel(
    attribute="Aattr2",
    index=-1,
    preset="attr_preset_1",
    plug=False,
    socket=False,
    data_type=int,
    kwargs={
        "help": "This attribute is purely decorative and the tooltip won't show."
    },
)
nodeA.attributes["Aattr3"] = AttrModel(
    attribute="Aattr3",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=True,
    data_type=int,
)
nodeA.attributes["Aattr4"] = AttrModel(
    attribute="Aattr4",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=True,
    data_type=str,
)
nodeA.attributes["Aattr5"] = AttrModel(
    attribute="Aattr5",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=True,
    data_type=int,
    plug_max_connections=1,
    socket_max_connections=-1,
)
nodeA.attributes["Aattr6"] = AttrModel(
    attribute="Aattr6",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=True,
    data_type=int,
    plug_max_connections=1,
    socket_max_connections=-1,
)
nodz.model_api.update_view(graph)

# Node B
nodeB = NodeModel(name="nodeB", alternate=True, preset="node_preset_1")
graph.nodes[nodeB.name] = nodeB
nodeB.attributes = OrderedDict(
    {
        "Battr1": AttrModel(
            attribute="Battr1",
            index=-1,
            preset="attr_preset_1",
            plug=True,
            socket=False,
            data_type=str,
        ),
        "Battr2": AttrModel(
            attribute="Battr2",
            index=-1,
            preset="attr_preset_1",
            plug=True,
            socket=False,
            data_type=int,
        ),
        "Battr3": AttrModel(
            attribute="Battr3",
            index=-1,
            preset="attr_preset_2",
            plug=True,
            socket=False,
            data_type=int,
        ),
        "Battr4": AttrModel(
            attribute="Battr4",
            index=-1,
            preset="attr_preset_3",
            plug=True,
            socket=False,
            data_type=int,
            plug_max_connections=1,
            socket_max_connections=-1,
        ),
    }
)
nodz.model_api.update_view(graph)


# Node C
nodeC = NodeModel(name="nodeC", alternate=True, preset="node_preset_1")
nodeC.attributes = OrderedDict(
    {
        "Cattr1": AttrModel(
            attribute="Cattr1",
            index=-1,
            preset="attr_preset_1",
            plug=False,
            socket=True,
            data_type=str,
        ),
        "Cattr2": AttrModel(
            attribute="Cattr2",
            index=-1,
            preset="attr_preset_1",
            plug=True,
            socket=False,
            data_type=int,
        ),
        "Cattr3": AttrModel(
            attribute="Cattr3",
            index=-1,
            preset="attr_preset_1",
            plug=True,
            socket=False,
            data_type=str,
        ),
        "Cattr4": AttrModel(
            attribute="Cattr4",
            index=-1,
            preset="attr_preset_2",
            plug=False,
            socket=True,
            data_type=str,
        ),
        "Cattr5": AttrModel(
            attribute="Cattr5",
            index=-1,
            preset="attr_preset_2",
            plug=False,
            socket=True,
            data_type=int,
        ),
        "Cattr6": AttrModel(
            attribute="Cattr6",
            index=-1,
            preset="attr_preset_3",
            plug=True,
            socket=False,
            data_type=str,
        ),
        "Cattr7": AttrModel(
            attribute="Cattr7",
            index=-1,
            preset="attr_preset_3",
            plug=True,
            socket=False,
            data_type=str,
        ),
        "Cattr8": AttrModel(
            attribute="Cattr8",
            index=-1,
            preset="attr_preset_3",
            plug=True,
            socket=False,
            data_type=int,
        ),
    }
)
graph.nodes[nodeC.name] = nodeC
nodz.model_api.update_view(graph)

# Node D
nodeD = NodeModel(name="nodeD", preset="node_preset_1")
nodeD.attributes = OrderedDict(
    {
        "Dattr1": AttrModel(
            attribute="Dattr1",
            index=-1,
            preset="attr_preset_3",
            plug=False,
            socket=True,
            data_type=str,
        ),
        "Dattr2": AttrModel(
            attribute="Dattr2",
            index=-1,
            preset="attr_preset_3",
            plug=True,
            socket=False,
            data_type=int,
        ),
    }
)
graph.nodes[nodeD.name] = nodeD
nodz.model_api.update_view(graph)

# Node E
nodeE = NodeModel(name="nodeE", preset="node_preset_1")
nodeE.attributes = OrderedDict(
    {
        "Eattr1": AttrModel(
            attribute="Eattr1",
            index=-1,
            preset="attr_preset_1",
            plug=True,
            socket=False,
            data_type=str,
        ),
        "Eattr2": AttrModel(
            attribute="Eattr2",
            index=-1,
            preset="attr_preset_2",
            plug=False,
            socket=True,
            data_type=str,
        ),
        "Eattr3": AttrModel(
            attribute="Eattr3",
            index=-1,
            preset="attr_preset_2",
            plug=False,
            socket=True,
            data_type=int,
        ),
    }
)
graph.nodes[nodeE.name] = nodeE
nodz.model_api.update_view(graph)

# Node F
nodeF = NodeModel(name="nodeF", preset="node_preset_1")
nodeF.attributes = OrderedDict(
    {
        "Fattr1": AttrModel(
            attribute="Fattr1",
            index=-1,
            preset="attr_preset_1",
            plug=True,
            socket=False,
            data_type=str,
        ),
        "Fattr2": AttrModel(
            attribute="Fattr2",
            index=-1,
            preset="attr_preset_2",
            plug=False,
            socket=True,
            data_type=str,
        ),
        "Fattr3": AttrModel(
            attribute="Fattr3",
            index=-1,
            preset="attr_preset_2",
            plug=False,
            socket=True,
            data_type=int,
        ),
    }
)
graph.nodes[nodeF.name] = nodeF
nodz.model_api.update_view(graph)


# Please note that this is a local test so once the graph is cleared
# and reloaded, all the local variables are not valid anymore, which
# means the following code to alter nodes won't work but saving/loading/
# clearing/evaluating will.

# Connection creation
graph.connections.append(ConnectionModel("nodeB", "Battr2", "nodeA", "Aattr3"))
nodz.model_api.update_view(graph)
graph.connections.append(ConnectionModel("nodeB", "Battr1", "nodeA", "Aattr4"))
graph.connections.append(ConnectionModel("nodeD", "Dattr2", "nodeA", "Aattr6"))
graph.connections.append(ConnectionModel("nodeE", "Eattr1", "nodeF", "Fattr2"))
nodz.model_api.update_view(graph)

# Attributes Edition
# Move first attribute to the end
attr_0 = nodeC.attributes.pop(nodeC.attribute_name_from_index(0))
nodeC.attributes[attr_0.attribute] = attr_0
nodeC.sort_attributes()
nodz.model_api.update_view(graph)
# Rename last attribute
nodeC.attributes[nodeC.attribute_name_from_index(-1)].attribute = "NewAttrName"
nodeC.sort_attributes()
nodz.model_api.update_view(graph)

# Attributes Deletion - delete last attribute
nodeC.attributes.pop(nodeC.attribute_name_from_index(-1))
nodz.model_api.update_view(graph)

# Nodes Edition - rename node
graph.rename_node(nodeC.name, "newNodeName")
nodz.model_api.update_view(graph)

# Nodes Deletion
del graph.nodes["newNodeName"]
nodz.model_api.update_view(graph)

# Graph
nlog.info(f"graph evaluation = {nodz.api.evaluate_graph()}")

nodz.api.save_graph(file_path="nodz_demo_model_graph.json")

nodz.api.clear_graph()

nodz.model_api.load_graph(file_path="nodz_demo_model_graph.json")


# test view -> data model communication
print()
nlog.info("test view -> data model communication ============================")
nodz.api.create_node("test node")
nodz.api.create_attribute(
    "test node", name="T_attr1", plug=True, socket=False, data_type=str
)
nodz.api.edit_node("test node", "test node renamed")

nodz._layout_graph()

if app:
    # command line stand alone test... run our own event loop
    app.exec_()
