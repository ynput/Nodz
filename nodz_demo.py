from qtpy import QtCore, QtWidgets
import nodz.core as core
from nodz.utils import nlog

try:
    app = QtWidgets.QApplication([])
except:
    # I guess we're running somewhere that already has a QApp created
    app = None

nodz = core.Nodz(None)
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
nodeA = nodz.createNode(name="nodeA", preset="node_preset_1", position=None)

nodz.createAttribute(
    node=nodeA,
    name="Aattr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    dataType=str,
)

nodz.createAttribute(
    node=nodeA,
    name="Aattr2",
    index=-1,
    preset="attr_preset_1",
    plug=False,
    socket=False,
    dataType=int,
)

nodz.createAttribute(
    node=nodeA,
    name="Aattr3",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=True,
    dataType=int,
)

nodz.createAttribute(
    node=nodeA,
    name="Aattr4",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=True,
    dataType=str,
)

nodz.createAttribute(
    node=nodeA,
    name="Aattr5",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=True,
    dataType=int,
    plugMaxConnections=1,
    socketMaxConnections=-1,
)

nodz.createAttribute(
    node=nodeA,
    name="Aattr6",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=True,
    dataType=int,
    plugMaxConnections=1,
    socketMaxConnections=-1,
)


# Node B
nodeB = nodz.createNode(name="nodeB", preset="node_preset_1")

nodz.createAttribute(
    node=nodeB,
    name="Battr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    dataType=str,
)

nodz.createAttribute(
    node=nodeB,
    name="Battr2",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    dataType=int,
)

nodz.createAttribute(
    node=nodeB,
    name="Battr3",
    index=-1,
    preset="attr_preset_2",
    plug=True,
    socket=False,
    dataType=int,
)

nodz.createAttribute(
    node=nodeB,
    name="Battr4",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    dataType=int,
    plugMaxConnections=1,
    socketMaxConnections=-1,
)


# Node C
nodeC = nodz.createNode(name="nodeC", preset="node_preset_1")

nodz.createAttribute(
    node=nodeC,
    name="Cattr1",
    index=-1,
    preset="attr_preset_1",
    plug=False,
    socket=True,
    dataType=str,
)

nodz.createAttribute(
    node=nodeC,
    name="Cattr2",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    dataType=int,
)

nodz.createAttribute(
    node=nodeC,
    name="Cattr3",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    dataType=str,
)

nodz.createAttribute(
    node=nodeC,
    name="Cattr4",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    dataType=str,
)

nodz.createAttribute(
    node=nodeC,
    name="Cattr5",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    dataType=int,
)

nodz.createAttribute(
    node=nodeC,
    name="Cattr6",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    dataType=str,
)

nodz.createAttribute(
    node=nodeC,
    name="Cattr7",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    dataType=str,
)

nodz.createAttribute(
    node=nodeC,
    name="Cattr8",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    dataType=int,
)

# Node D
nodeD = nodz.createNode(name="nodeD", preset="node_preset_1")

nodz.createAttribute(
    node=nodeD,
    name="Dattr1",
    index=-1,
    preset="attr_preset_3",
    plug=False,
    socket=True,
    dataType=str,
)

nodz.createAttribute(
    node=nodeD,
    name="Dattr2",
    index=-1,
    preset="attr_preset_3",
    plug=True,
    socket=False,
    dataType=int,
)

# Node E
nodeE = nodz.createNode(name="nodeE", preset="node_preset_1")

nodz.createAttribute(
    node=nodeE,
    name="Eattr1",
    index=-1,
    preset="attr_preset_1",
    plug=True,
    socket=False,
    dataType=str,
)

nodz.createAttribute(
    node=nodeE,
    name="Eattr2",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    dataType=str,
)

nodz.createAttribute(
    node=nodeE,
    name="Eattr3",
    index=-1,
    preset="attr_preset_2",
    plug=False,
    socket=True,
    dataType=int,
)


# Please note that this is a local test so once the graph is cleared
# and reloaded, all the local variables are not valid anymore, which
# means the following code to alter nodes won't work but saving/loading/
# clearing/evaluating will.

# Connection creation
nodz.createConnection("nodeB", "Battr2", "nodeA", "Aattr3")
nodz.createConnection("nodeB", "Battr1", "nodeA", "Aattr4")
nodz.createConnection("nodeD", "Dattr2", "nodeA", "Aattr6")

# Attributes Edition
nodz.editAttribute(node=nodeC, index=0, newName=None, newIndex=-1)
nodz.editAttribute(node=nodeC, index=-1, newName="NewAttrName", newIndex=None)

# Attributes Deletion
nodz.deleteAttribute(node=nodeC, index=-1)


# Nodes Edition
nodz.editNode(node=nodeC, newName="newNodeName")

# Nodes Deletion
nodz.deleteNode(node=nodeC)


# Graph
nlog.info(nodz.evaluateGraph())

nodz.saveGraph(filePath="Enter your path")

nodz.clearGraph()

nodz.loadGraph(filePath="Enter your path")

nodz._layout_graph()

if app:
    # command line stand alone test... run our own event loop
    app.exec_()
