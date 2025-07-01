from typing import Any
from qtpy import QtCore, QtWidgets
import nodz.core as core
from nodz.utils import nlog

try:
    app = QtWidgets.QApplication([])
except BaseException:
    # I guess we're running somewhere that already has a QApp created
    app = None

######################################################################
# Test subclasses
######################################################################


class TestNode(core.NodeItem):
    def __init__(
        self,
        name: str,
        alternate: bool,
        preset: str,
        config: dict,
        help: str = "",
    ) -> None:
        super().__init__(name, alternate, preset, config)
        self.help = help if help else "This is a subclassed node."

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["help"] = self.help
        return d

    def configure_from_dict(self, d: dict) -> None:
        if d and "help" in d:
            self.help = d["help"]


class TestPlug(core.PlugItem):
    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        attribute: str,
        index: int,
        preset: str,
        data_type: Any,
        max_connections: int,
        help: str = "",
    ) -> None:
        super().__init__(
            parent, attribute, index, preset, data_type, max_connections
        )
        self.help = help if help else "This is a subclassed plug."

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["help"] = self.help
        return d

    def configure_from_dict(self, d: dict) -> None:
        if d and "help" in d:
            self.help = d["help"]


class TestSocket(core.SocketItem):
    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        attribute: str,
        index: int,
        preset: str,
        data_type: Any,
        max_connections: int,
        help: str = "",
    ) -> None:
        super().__init__(
            parent, attribute, index, preset, data_type, max_connections
        )
        self.help = help if help else "This is a subclassed socket."

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["help"] = self.help
        return d

    def configure_from_dict(self, d: dict) -> None:
        if d and "help" in d:
            self.help = d["help"]


nodz = core.Nodz(
    None,
    nodeitem_cls=TestNode,
    plugitem_cls=TestPlug,
    socketitem_cls=TestSocket,
)
# nodz.loadConfig(filePath='')
nodz.initialize()
nodz.show()


######################################################################
# Test signals
######################################################################


# Nodes
@QtCore.Slot(str)
def on_nodeCreated(nodeName):
    nlog.info(f"node created : {nodeName}")


@QtCore.Slot(str)
def on_nodeDeleted(nodeName):
    nlog.info(f"node deleted : {nodeName}")


@QtCore.Slot(str, str)
def on_nodeEdited(nodeName, newName):
    nlog.info(f"node edited : {nodeName}, new name : {newName}")


@QtCore.Slot(str)
def on_nodeSelected(nodesName):
    nlog.info(f"node selected : {nodesName}")


@QtCore.Slot(str, object)
def on_nodeMoved(nodeName, nodePos):
    nlog.info(f"node {nodeName} moved to {nodePos}")


@QtCore.Slot(str)
def on_nodeDoubleClick(nodeName):
    nlog.info(f"double click on node : {nodeName}")


# Attrs
@QtCore.Slot(str, int)
def on_attrCreated(nodeName, attrId):
    nlog.info(f"attr created : {nodeName} at index : {attrId}")


@QtCore.Slot(str, int)
def on_attrDeleted(nodeName, attrId):
    nlog.info(f"attr Deleted : {nodeName} at old index : {attrId}")


@QtCore.Slot(str, int, int)
def on_attrEdited(nodeName, oldId, newId):
    nlog.info(
        f"attr Edited : {nodeName} at old index : {oldId}, new index : {newId}"
    )


# Connections
@QtCore.Slot(str, str, str, str)
def on_connected(srcNodeName, srcPlugName, destNodeName, dstSocketName):
    nlog.info(
        f'connected src: "{srcNodeName}" at "{srcPlugName}" to dst: '
        f'"{destNodeName}" at "{dstSocketName}"'
    )


@QtCore.Slot(str, str, str, str)
def on_disconnected(srcNodeName, srcPlugName, destNodeName, dstSocketName):
    nlog.info(
        f'disconnected src: "{srcNodeName}" at "{srcPlugName}" from dst: '
        f'"{destNodeName}" at "{dstSocketName}"'
    )


# Graph
@QtCore.Slot()
def on_graphSaved():
    nlog.info("graph saved !")


@QtCore.Slot()
def on_graphLoaded():
    nlog.info("graph loaded !")


@QtCore.Slot()
def on_graphCleared():
    nlog.info("graph cleared !")


@QtCore.Slot()
def on_graphEvaluated():
    nlog.info("graph evaluated !")


# Other
@QtCore.Slot(object)
def on_keyPressed(key):
    nlog.info(f"key pressed :  {key}")


nodz.signal_NodeCreated.connect(on_nodeCreated)
nodz.signal_NodeDeleted.connect(on_nodeDeleted)
nodz.signal_NodeEdited.connect(on_nodeEdited)
nodz.signal_NodeSelected.connect(on_nodeSelected)
nodz.signal_NodeMoved.connect(on_nodeMoved)
nodz.signal_NodeDoubleClicked.connect(on_nodeDoubleClick)

nodz.signal_AttrCreated.connect(on_attrCreated)
nodz.signal_AttrDeleted.connect(on_attrDeleted)
nodz.signal_AttrEdited.connect(on_attrEdited)

nodz.signal_PlugConnected.connect(on_connected)
nodz.signal_SocketConnected.connect(on_connected)
nodz.signal_PlugDisconnected.connect(on_disconnected)
nodz.signal_SocketDisconnected.connect(on_disconnected)

nodz.signal_GraphSaved.connect(on_graphSaved)
nodz.signal_GraphLoaded.connect(on_graphLoaded)
nodz.signal_GraphCleared.connect(on_graphCleared)
nodz.signal_GraphEvaluated.connect(on_graphEvaluated)

nodz.signal_KeyPressed.connect(on_keyPressed)


######################################################################
# Test API
######################################################################

# Node A
nodeA = nodz.create_node(name="nodeA", preset="node_preset_1", position=None)

nodz.create_attribute(
    node=nodeA,
    name="Aattr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    node=nodeA,
    name="Aattr2",
    index=-1,
    preset="attr_preset_1",
    plug=False,
    socket=False,
    data_type=int,
)

nodz.create_attribute(
    node=nodeA,
    name="Aattr3",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=True,
    data_type=int,
)

nodz.create_attribute(
    node=nodeA,
    name="Aattr4",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    node=nodeA,
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
    node=nodeA,
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
    node=nodeB,
    name="Battr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    node=nodeB,
    name="Battr2",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=int,
)

nodz.create_attribute(
    node=nodeB,
    name="Battr3",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=False,
    data_type=int,
)

nodz.create_attribute(
    node=nodeB,
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
    node=nodeC,
    name="Cattr1",
    index=-1,
    preset="attr_preset_1",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    node=nodeC,
    name="Cattr2",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=int,
)

nodz.create_attribute(
    node=nodeC,
    name="Cattr3",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    node=nodeC,
    name="Cattr4",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    node=nodeC,
    name="Cattr5",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=int,
)

nodz.create_attribute(
    node=nodeC,
    name="Cattr6",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    node=nodeC,
    name="Cattr7",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    node=nodeC,
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
    node=nodeD,
    name="Dattr1",
    index=-1,
    preset="attr_preset_3",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    node=nodeD,
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
    node=nodeE,
    name="Eattr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    data_type=str,
)

nodz.create_attribute(
    node=nodeE,
    name="Eattr2",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    data_type=str,
)

nodz.create_attribute(
    node=nodeE,
    name="Eattr3",
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

# Attributes Edition
nodz.edit_attribute(node=nodeC, index=0, new_name=None, new_index=-1)
nodz.edit_attribute(
    node=nodeC, index=-1, new_name="NewAttrName", new_index=None
)

# Attributes Deletion
nodz.delete_attribute(node=nodeC, index=-1)


# Nodes Edition
nodz.edit_node(node=nodeC, new_name="newNodeName")

# Nodes Deletion
nodz.delete_node(node=nodeC)


# Graph
nlog.info(nodz.evaluate_graph())

nodz.save_graph(file_path="Enter your path")

nodz.clear_graph()

nodz.load_graph(file_path="Enter your path")

nodz._layout_graph()

if app:
    # command line stand alone test... run our own event loop
    app.exec_()
