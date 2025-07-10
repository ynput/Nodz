from typing import Union
from qtpy import QtCore, QtGui, QtWidgets
import nodz.view as view
import nodz.items as items
from nodz.utils import nlog
from nodz.data_types import NodeModel, AttrModel, ConnectionModel

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
        attr_data = self.attrs_data[attr]

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
    def create_connection(
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
nodz = view.Nodz(
    None,
)
nodz.initialize(node_factory=test_factory)
nodz.show()


######################################################################
# Test signals
######################################################################


# Nodes
@QtCore.Slot(object)  # type: ignore
def on_nodeCreated(node_model: NodeModel):
    nlog.info(f"> node created : {node_model.name}")


@QtCore.Slot(str)  # type: ignore
def on_nodeDeleted(node_name):
    nlog.info(f"> node deleted : {node_name}")


@QtCore.Slot(str, str)  # type: ignore
def on_nodeEdited(node_name, new_name):
    nlog.info(f"> node edited : {node_name}, new name : {new_name}")


@QtCore.Slot(object)  # type: ignore
def on_nodeSelected(nodes_names: list):
    nlog.info(f"> node selected : {nodes_names}")


@QtCore.Slot(object, object)  # type: ignore
def on_nodeMoved(node_model: NodeModel, nodePos: QtCore.QPointF):
    nlog.info(f"> node {node_model.name} moved to {nodePos.toTuple()}")


@QtCore.Slot(object)  # type: ignore
def on_nodeDoubleClick(node_model: NodeModel):
    nlog.info(f"> double click on node : {node_model.name}")


# Attrs
@QtCore.Slot(object, int)  # type: ignore
def on_attrCreated(model: NodeModel, attr_id: int):
    nlog.info(
        f"> attr created : {model.name}.{model.attributes[attr_id].attribute} "
        f"at index : {attr_id}"
    )


@QtCore.Slot(object, int)  # type: ignore
def on_attrDeleted(model: NodeModel, attr_id: int):
    nlog.info(f"> attr Deleted : {model.name} at old index : {attr_id}")


@QtCore.Slot(object, int, int)  # type: ignore
def on_attrEdited(model: NodeModel, old_id: int, new_id: int):
    nlog.info(
        f"> attr Edited : {model.name}.{model.attributes[new_id].attribute} "
        f"at old index : {old_id}, new index : {new_id}"
    )


# Connections
@QtCore.Slot(object)  # type: ignore
def on_connected(model: ConnectionModel):
    nlog.info(
        f'> connected src: "{model.plug_node}" at "{model.plug_attr}" to dst: '
        f'"{model.socket_node}" at "{model.socket_attr}"'
    )


@QtCore.Slot(object)  # type: ignore
def on_disconnected(model: ConnectionModel):
    nlog.info(
        f'> disconnected src: "{model.plug_node}" at "{model.plug_attr}" from dst: '
        f'"{model.socket_node}" at "{model.socket_attr}"'
    )


# Graph
@QtCore.Slot()  # type: ignore
def on_graphSaved():
    nlog.info("> graph saved !")


@QtCore.Slot()  # type: ignore
def on_graphLoaded():
    nlog.info("> graph loaded !")


@QtCore.Slot()  # type: ignore
def on_graphCleared():
    nlog.info("> graph cleared !")


@QtCore.Slot()  # type: ignore
def on_graphEvaluated():
    nlog.info("> graph evaluated !")


# Other
_last_key = None


@QtCore.Slot(object)  # type: ignore
def on_keyPressed(key):
    global _last_key
    if _last_key != key:
        nlog.info(f"key pressed :  {key}")
        _last_key = key


nodz._scene.signal_NodeCreated.connect(on_nodeCreated)
nodz._scene.signal_NodeDeleted.connect(on_nodeDeleted)
nodz._scene.signal_NodeEdited.connect(on_nodeEdited)
nodz._scene.signal_NodeSelected.connect(on_nodeSelected)
nodz._scene.signal_NodeMoved.connect(on_nodeMoved)
nodz._scene.signal_NodeDoubleClicked.connect(on_nodeDoubleClick)

nodz._scene.signal_AttrCreated.connect(on_attrCreated)
nodz._scene.signal_AttrDeleted.connect(on_attrDeleted)
nodz._scene.signal_AttrEdited.connect(on_attrEdited)

nodz._scene.signal_PlugConnected.connect(on_connected)
nodz._scene.signal_SocketConnected.connect(on_connected)
nodz._scene.signal_PlugDisconnected.connect(on_disconnected)
nodz._scene.signal_SocketDisconnected.connect(on_disconnected)

nodz._scene.signal_GraphSaved.connect(on_graphSaved)
nodz._scene.signal_GraphLoaded.connect(on_graphLoaded)
nodz._scene.signal_GraphCleared.connect(on_graphCleared)
nodz._scene.signal_GraphEvaluated.connect(on_graphEvaluated)

nodz.signal_KeyPressed.connect(on_keyPressed)


######################################################################
# Test API
######################################################################

# Node A
nodeA = nodz.create_node(
    name="nodeA",
    preset="node_preset_1",
    position=None,
    help="NodeA has it's own special help string !",
)

nodz.create_attribute(
    nodeA,
    name="Aattr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
    help="Just checking this is working !",
)

nodz.create_attribute(
    nodeA,
    name="Aattr2",
    index=-1,
    preset="attr_preset_1",
    plug=False,
    socket=False,
    data_type=int,
    help="This attribute is purely decorative and the tooltip won't show.",
)

nodz.create_attribute(
    nodeA,
    name="Aattr3",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=True,
    data_type=int,
)

nodz.create_attribute(
    nodeA,
    name="Aattr4",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    nodeA,
    name="Aattr5",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=True,
    data_type=int,
    plug_max_connections=1,
    socket_max_connections=-1,
)

nodz.create_attribute(
    nodeA,
    name="Aattr6",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=True,
    data_type=int,
    plug_max_connections=1,
    socket_max_connections=-1,
)


# Node B
nodeB = nodz.create_node(name="nodeB", preset="node_preset_1")

nodz.create_attribute(
    nodeB,
    name="Battr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    nodeB,
    name="Battr2",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=int,
)

nodz.create_attribute(
    nodeB,
    name="Battr3",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=False,
    data_type=int,
)

nodz.create_attribute(
    nodeB,
    name="Battr4",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    data_type=int,
    plug_max_connections=1,
    socket_max_connections=-1,
)


# Node C
nodeC = nodz.create_node(name="nodeC", preset="node_preset_1")

nodz.create_attribute(
    nodeC,
    name="Cattr1",
    index=-1,
    preset="attr_preset_1",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    nodeC,
    name="Cattr2",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=int,
)

nodz.create_attribute(
    nodeC,
    name="Cattr3",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    nodeC,
    name="Cattr4",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    nodeC,
    name="Cattr5",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=int,
)

nodz.create_attribute(
    nodeC,
    name="Cattr6",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    nodeC,
    name="Cattr7",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    nodeC,
    name="Cattr8",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    data_type=int,
)

# Node D
nodeD = nodz.create_node(name="nodeD", preset="node_preset_1")

nodz.create_attribute(
    nodeD,
    name="Dattr1",
    index=-1,
    preset="attr_preset_3",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    nodeD,
    name="Dattr2",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    data_type=int,
)

# Node E
nodeE = nodz.create_node(name="nodeE", preset="node_preset_1")

nodz.create_attribute(
    nodeE,
    name="Eattr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    nodeE,
    name="Eattr2",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    nodeE,
    name="Eattr3",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=int,
)

# Node F
nodeF = nodz.create_node(name="nodeF", preset="node_preset_1")

nodz.create_attribute(
    nodeF,
    name="Fattr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    nodeF,
    name="Fattr2",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    nodeF,
    name="Fattr3",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=int,
)


# Please note that this is a local test so once the graph is cleared
# and reloaded, all the local variables are not valid anymore, which
# means the following code to alter nodes won't work but saving/loading/
# clearing/evaluating will.

# Connection creation
nodz.create_connection("nodeB", "Battr2", "nodeA", "Aattr3")
nodz.create_connection("nodeB", "Battr1", "nodeA", "Aattr4")
nodz.create_connection("nodeD", "Dattr2", "nodeA", "Aattr6")
nodz.create_connection("nodeE", "Eattr1", "nodeF", "Fattr2")

# Attributes Edition
nodz.edit_attribute(nodeC, index=0, new_name=None, new_index=-1)
nodz.edit_attribute(nodeC, index=-1, new_name="NewAttrName", new_index=None)

# Attributes Deletion
nodz.delete_attribute(nodeC, index=-1)


# Nodes Edition
nodeC = nodz.edit_node(nodeC, new_name="newNodeName")

# Nodes Deletion
nodz.delete_node(nodeC)


# Graph
nlog.info(f"graph evaluation = {nodz.evaluate_graph()}")

nodz.save_graph(file_path="nodz_demo_graph.json")

nodz.clear_graph()

nodz.load_graph(file_path="nodz_demo_graph.json")

nodz._layout_graph()

if app:
    # command line stand alone test... run our own event loop
    app.exec_()
