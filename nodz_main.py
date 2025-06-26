from __future__ import annotations
import os
from typing import Any
from enum import Enum, auto
from qtpy import QtGui, QtCore, QtWidgets
import nodz_utils as utils
from nodz_utils import nlog


DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "default_config.json"
)


def _nodz_instance(cls) -> Nodz:
    try:
        view = cls.scene().views()[0]
    except BaseException as err:
        raise RuntimeError(f"Could not get first scene view: {err} ")
    else:
        if isinstance(view, Nodz):
            return view
        else:
            raise TypeError(f"Unexpected view type: {view}")


def _nodz_scene(cls) -> NodeScene:
    scene = cls.scene()
    if isinstance(scene, NodeScene):
        return scene
    else:
        raise TypeError(f"Unexpected scene type: {scene}")


class ViewState(Enum):
    DEFAULT = 0
    SELECTION = 1
    ADD_SELECTION = 2
    SUBTRACT_SELECTION = 3
    TOGGLE_SELECTION = 4
    ZOOM_VIEW = 5
    DRAG_VIEW = 6
    DRAG_ITEM = 7


class Nodz(QtWidgets.QGraphicsView):
    """
    The main view for the node graph representation.

    The node view implements a state pattern to control all the
    different user interactions.

    """

    # FIXME: Somehow QtCore.Signal is flagged by pylance as
    # not exported by qtpy.QtCore...

    signal_NodeCreated = QtCore.Signal(object)  # type: ignore (qtpy)
    signal_NodeDeleted = QtCore.Signal(object)  # type: ignore (qtpy)
    signal_NodeEdited = QtCore.Signal(object, object)  # type: ignore (qtpy)
    signal_NodeSelected = QtCore.Signal(object)  # type: ignore (qtpy)
    signal_NodeMoved = QtCore.Signal(str, object)  # type: ignore (qtpy)
    signal_NodeDoubleClicked = QtCore.Signal(str)  # type: ignore (qtpy)

    signal_AttrCreated = QtCore.Signal(object, object)  # type: ignore (qtpy)
    signal_AttrDeleted = QtCore.Signal(object, object)  # type: ignore (qtpy)
    signal_AttrEdited = QtCore.Signal(object, object, object)  # type: ignore (qtpy)

    signal_PlugConnected = QtCore.Signal(object, object, object, object)  # type: ignore (qtpy)
    signal_PlugDisconnected = QtCore.Signal(object, object, object, object)  # type: ignore (qtpy)
    signal_SocketConnected = QtCore.Signal(object, object, object, object)  # type: ignore (qtpy)
    signal_SocketDisconnected = QtCore.Signal(object, object, object, object)  # type: ignore (qtpy)

    signal_GraphSaved = QtCore.Signal()  # type: ignore (qtpy)
    signal_GraphLoaded = QtCore.Signal()  # type: ignore (qtpy)
    signal_GraphCleared = QtCore.Signal()  # type: ignore (qtpy)
    signal_GraphEvaluated = QtCore.Signal()  # type: ignore (qtpy)

    signal_KeyPressed = QtCore.Signal(object)  # type: ignore (qtpy)
    signal_Dropped = QtCore.Signal()  # type: ignore (qtpy)

    def __init__(
        self,
        parent: Any,
        configPath: str = DEFAULT_CONFIG_PATH,
    ):
        """
        Initialize the graphics view.

        """
        super(Nodz, self).__init__(parent)

        # Load nodz configuration.
        self.loadConfig(configPath)

        # General data.
        self.gridVisToggle = True
        self.gridSnapToggle = False
        self._nodeSnap = False

        # Connections data.
        self.drawingConnection = False
        self.currentHoveredNode: NodeItem | None = None
        self.sourceSlot: SlotItem | None = None

        # Display options.
        self.currentState = ViewState.DEFAULT
        self.pressedKeys = list()

    @property
    def nodz_scene(self) -> NodeScene:
        return _nodz_scene(self)

    @property
    def scene_nodes(self) -> dict:
        try:
            return self.nodz_scene.nodes
        except AttributeError:
            raise RuntimeError(
                "Scene hasn't been setup yet ! Run Nodz.Initialize() first."
            )

    @scene_nodes.setter
    def scene_nodes(self, value):
        try:
            self.nodz_scene.nodes = value
        except AttributeError:
            raise RuntimeError(
                "Scene hasn't been setup yet ! Run Nodz.Initialize() first."
            )

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """
        Zoom in the view with the mouse wheel.

        """
        self.currentState = ViewState.ZOOM_VIEW
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        inFactor = 1.15
        outFactor = 1 / inFactor

        delta = event.angleDelta().y()

        if delta > 0:
            zoomFactor = inFactor
        else:
            zoomFactor = outFactor

        self.scale(zoomFactor, zoomFactor)
        self.currentState = ViewState.DEFAULT

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Initialize tablet zoom, drag canvas and the selection.

        """
        # Tablet zoom
        if (
            event.button() == QtCore.Qt.MouseButton.RightButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.AltModifier
        ):
            self.currentState = ViewState.ZOOM_VIEW
            self.initMousePos = event.pos()
            self.zoomInitialPos = event.pos()
            self.initMouse = QtGui.QCursor.pos()
            self.setInteractive(False)

        # Drag view
        elif (
            event.button() == QtCore.Qt.MouseButton.MiddleButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.AltModifier
        ):
            self.currentState = ViewState.DRAG_VIEW
            self.prevPos = event.pos()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            self.setInteractive(False)

        # Rubber band selection
        elif (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier
            and self.scene().itemAt(
                self.mapToScene(event.pos()), QtGui.QTransform()
            )
            is None
        ):
            self.currentState = ViewState.SELECTION
            self._initRubberband(event.pos().toPointF())
            self.setInteractive(False)

        # Drag Item
        elif (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier
            and self.scene().itemAt(
                self.mapToScene(event.pos()), QtGui.QTransform()
            )
            is not None
        ):
            self.currentState = ViewState.DRAG_ITEM
            self.setInteractive(True)

        # Add selection
        elif (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and QtCore.Qt.Key.Key_Shift in self.pressedKeys
            and QtCore.Qt.Key.Key_Control in self.pressedKeys
        ):
            self.currentState = ViewState.ADD_SELECTION
            self._initRubberband(event.pos().toPointF())
            self.setInteractive(False)

        # Subtract selection
        elif (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self.currentState = ViewState.SUBTRACT_SELECTION
            self._initRubberband(event.pos().toPointF())
            self.setInteractive(False)

        # Toggle selection
        elif (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            self.currentState = ViewState.TOGGLE_SELECTION
            self._initRubberband(event.pos().toPointF())
            self.setInteractive(False)

        else:
            self.currentState = ViewState.DEFAULT

        super(Nodz, self).mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Update tablet zoom, canvas dragging and selection.

        """
        # Zoom.
        if self.currentState == ViewState.ZOOM_VIEW:
            offset = self.zoomInitialPos.x() - event.pos().x()

            if offset > self.previousMouseOffset:
                self.previousMouseOffset = offset
                self.zoomDirection = -1
                self.zoomIncr -= 1

            elif offset == self.previousMouseOffset:
                self.previousMouseOffset = offset
                if self.zoomDirection == -1:
                    self.zoomDirection = -1
                else:
                    self.zoomDirection = 1

            else:
                self.previousMouseOffset = offset
                self.zoomDirection = 1
                self.zoomIncr += 1

            if self.zoomDirection == 1:
                zoomFactor = 1.03
            else:
                zoomFactor = 1 / 1.03

            # Perform zoom and re-center on initial click position.
            pBefore = self.mapToScene(self.initMousePos)
            self.setTransformationAnchor(
                QtWidgets.QGraphicsView.ViewportAnchor.AnchorViewCenter
            )
            self.scale(zoomFactor, zoomFactor)
            pAfter = self.mapToScene(self.initMousePos)
            diff = pAfter - pBefore

            self.setTransformationAnchor(
                QtWidgets.QGraphicsView.ViewportAnchor.NoAnchor
            )
            self.translate(diff.x(), diff.y())

        # Drag canvas.
        elif self.currentState == ViewState.DRAG_VIEW:
            offset = self.prevPos - event.pos()
            self.prevPos = event.pos()
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() + offset.y()
            )
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() + offset.x()
            )

        # RuberBand selection.
        elif (
            self.currentState == ViewState.SELECTION
            or self.currentState == ViewState.ADD_SELECTION
            or self.currentState == ViewState.SUBTRACT_SELECTION
            or self.currentState == ViewState.TOGGLE_SELECTION
        ):
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin.toPoint(), event.pos()).normalized()
            )

        super(Nodz, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Apply tablet zoom, dragging and selection.

        """
        # Zoom the View.
        if self.currentState == ViewState.ZOOM_VIEW:
            self.offset = 0
            self.zoomDirection = 0
            self.zoomIncr = 0
            self.setInteractive(True)

        # Drag View.
        elif self.currentState == ViewState.DRAG_VIEW:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            self.setInteractive(True)

        # Selection.
        elif self.currentState == ViewState.SELECTION:
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin.toPoint(), event.pos()).normalized()
            )
            painterPath = self._releaseRubberband()
            self.setInteractive(True)
            self.scene().setSelectionArea(painterPath)

        # Add Selection.
        elif self.currentState == ViewState.ADD_SELECTION:
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin.toPoint(), event.pos()).normalized()
            )
            painterPath = self._releaseRubberband()
            self.setInteractive(True)
            for item in self.scene().items(painterPath):
                item.setSelected(True)

        # Subtract Selection.
        elif self.currentState == ViewState.SUBTRACT_SELECTION:
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin.toPoint(), event.pos()).normalized()
            )
            painterPath = self._releaseRubberband()
            self.setInteractive(True)
            for item in self.scene().items(painterPath):
                item.setSelected(False)

        # Toggle Selection
        elif self.currentState == ViewState.TOGGLE_SELECTION:
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin.toPoint(), event.pos()).normalized()
            )
            painterPath = self._releaseRubberband()
            self.setInteractive(True)
            for item in self.scene().items(painterPath):
                if item.isSelected():
                    item.setSelected(False)
                else:
                    item.setSelected(True)

        self.currentState = ViewState.DEFAULT

        super(Nodz, self).mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """
        Save pressed key and apply shortcuts.

        Shortcuts are:
        DEL - Delete the selected nodes
        F - Focus view on the selection

        """
        if event.key() not in self.pressedKeys:
            self.pressedKeys.append(event.key())

        if event.key() in (
            QtCore.Qt.Key.Key_Delete,
            QtCore.Qt.Key.Key_Backspace,
        ):
            self._deleteSelectedNodes()

        if event.key() == QtCore.Qt.Key.Key_F:
            self._focus()

        if event.key() == QtCore.Qt.Key.Key_S:
            self._nodeSnap = True

        # Emit signal.
        self.signal_KeyPressed.emit(event.key())

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        """
        Clear the key from the pressed key list.

        """
        if event.key() == QtCore.Qt.Key.Key_S:
            self._nodeSnap = False

        if event.key() in self.pressedKeys:
            self.pressedKeys.remove(event.key())

    def _initRubberband(self, position: QtCore.QPointF) -> None:
        """
        Initialize the rubber band at the given position.

        """
        self.rubberBandStart = position
        self.origin = position
        self.rubberband.setGeometry(
            QtCore.QRect(self.origin.toPoint(), QtCore.QSize())
        )
        self.rubberband.show()

    def _releaseRubberband(self) -> QtGui.QPainterPath:
        """
        Hide the rubber band and return the path.

        """
        painterPath = QtGui.QPainterPath()
        rect = self.mapToScene(self.rubberband.geometry())
        painterPath.addPolygon(rect)
        self.rubberband.hide()
        return painterPath

    def _focus(self) -> None:
        """
        Center on selected nodes or all of them if no active selection.

        """
        if self.scene().selectedItems():
            itemsArea = self._getSelectionBoundingbox()
            self.fitInView(
                itemsArea, QtCore.Qt.AspectRatioMode.KeepAspectRatio
            )
        else:
            itemsArea = self.scene().itemsBoundingRect()
            self.fitInView(
                itemsArea, QtCore.Qt.AspectRatioMode.KeepAspectRatio
            )

    def _getSelectionBoundingbox(self) -> QtCore.QRectF:
        """
        Return the bounding box of the selection.

        """
        rect: QtCore.QRectF | None = None
        for item in self.scene().selectedItems():
            if not rect:
                rect = item.sceneBoundingRect()
            else:
                rect = rect.united(item.sceneBoundingRect())
        return rect if rect else QtCore.QRectF()

    def _deleteSelectedNodes(self) -> None:
        """
        Delete selected nodes.

        """
        selected_nodes = list()
        for node in self.scene().selectedItems():
            if not isinstance(node, NodeItem):
                raise TypeError(f"Unexpected node type in graph: {node}")
            selected_nodes.append(node.name)
            node._remove()

        # Emit signal.
        self.signal_NodeDeleted.emit(selected_nodes)

    def _returnSelection(self) -> None:
        """
        Wrapper to return selected items.

        """
        selected_nodes = list()
        if self.scene().selectedItems():
            for node in self.scene().selectedItems():
                if not isinstance(node, NodeItem):
                    raise TypeError(f"Unexpected node type in graph: {node}")
                selected_nodes.append(node.name)

        # Emit signal.
        self.signal_NodeSelected.emit(selected_nodes)

    ##################################################################
    # API
    ##################################################################

    def loadConfig(self, filePath: str) -> None:
        """
        Set a specific configuration for this instance of Nodz.

        :type  filePath: str.
        :param filePath: The path to the config file that you want to
                         use.

        """
        self.config = utils._loadConfig(filePath)

    def initialize(self) -> None:
        """
        Setup the view's behavior.

        """
        # Setup view.
        config = self.config
        self.setRenderHint(
            QtGui.QPainter.RenderHint.Antialiasing, config["antialiasing"]
        )
        self.setRenderHint(
            QtGui.QPainter.RenderHint.TextAntialiasing, config["antialiasing"]
        )
        self.setRenderHint(
            QtGui.QPainter.RenderHint.SmoothPixmapTransform,
            config["smooth_pixmap"],
        )
        self.setViewportUpdateMode(
            QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        )
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.rubberband = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Shape.Rectangle, self
        )

        # Setup scene.
        scene = NodeScene(self)
        sceneWidth = config["scene_width"]
        sceneHeight = config["scene_height"]
        scene.setSceneRect(0, 0, sceneWidth, sceneHeight)
        self.setScene(scene)
        # Connect scene node moved signal
        scene.signal_NodeMoved.connect(self.signal_NodeMoved)

        # Tablet zoom.
        self.previousMouseOffset = 0
        self.zoomDirection = 0
        self.zoomIncr = 0

        # Connect signals.
        self.scene().selectionChanged.connect(self._returnSelection)

    # NODES
    def createNode(
        self,
        name: str = "default",
        preset: str = "node_default",
        position: QtCore.QPointF | None = None,
        alternate: bool = True,
    ) -> NodeItem:
        """
        Create a new node with a given name, position and color.

        :type  name: str.
        :param name: The name of the node. The name has to be unique
                     as it is used as a key to store the node object.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :type  position: QtCore.QPoint.
        :param position: The position of the node once created. If None,
                         it will be created at the center of the scene.

        :type  alternate: bool.
        :param alternate: The attribute color alternate state, if True,
                          every 2 attribute the color will be slightly
                          darker.

        :return : The created node

        """
        # Check for name clashes
        if name in self.scene_nodes.keys():
            raise NameError(
                f"A node with the same name already exists : {name}"
            )

        nodeItem = NodeItem(
            name=name,
            alternate=alternate,
            preset=preset,
            config=self.config,
        )

        # Store node in scene.
        self.scene_nodes[name] = nodeItem

        if not position:
            # Get the center of the view.
            position = self.mapToScene(self.viewport().rect().center())

        # Set node position.
        self.scene().addItem(nodeItem)
        nodeItem.setPos(position - nodeItem.nodeCenter)

        # Emit signal.
        self.signal_NodeCreated.emit(name)

        return nodeItem

    def deleteNode(self, node: NodeItem) -> None:
        """
        Delete the specified node from the view.

        :type  node: class.
        :param node: The node instance that you want to delete.

        """
        if node not in self.scene_nodes.values():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Node deletion aborted !")
            return

        if node in self.scene_nodes.values():
            nodeName = node.name
            node._remove()

            # Emit signal.
            self.signal_NodeDeleted.emit([nodeName])

    def editNode(self, node, newName: str | None = None) -> None:
        """
        Rename an existing node.

        :type  node: class.
        :param node: The node instance that you want to delete.

        :type  newName: str.
        :param newName: The new name for the given node.

        """
        if node not in self.scene_nodes.values():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Node edition aborted !")
            return

        oldName = node.name

        if newName is not None:
            # Check for name clashes
            if newName in self.scene_nodes.keys():
                nlog.error(
                    f"A node with the same name already exists : {newName}"
                )
                nlog.error("Node edition aborted !")
                return
            else:
                node.name = newName

        # Replace node data.
        self.scene_nodes[newName] = self.scene_nodes[oldName]
        self.scene_nodes.pop(oldName)

        # Store new node name in the connections
        if node.sockets:
            for socket in node.sockets.values():
                for connection in socket.connections:
                    connection.socketNode = newName

        if node.plugs:
            for plug in node.plugs.values():
                for connection in plug.connections:
                    connection.plugNode = newName

        node.update()

        # Emit signal.
        self.signal_NodeEdited.emit(oldName, newName)

    # ATTRS
    def createAttribute(
        self,
        node: NodeItem,
        name: str = "default",
        index: int = -1,
        preset: str = "attr_default",
        plug: bool = True,
        socket: bool = True,
        dataType: Any = None,
        plugMaxConnections: int = -1,
        socketMaxConnections: int = 1,
    ) -> None:
        """
        Create a new attribute with a given name.

        :type  node: class.
        :param node: The node instance that you want to delete.

        :type  name: str.
        :param name: The name of the attribute. The name has to be
                     unique as it is used as a key to store the node
                     object.

        :type  index: int.
        :param index: The index of the attribute in the node.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :type  plug: bool.
        :param plug: Whether or not this attribute can emit connections.

        :type  socket: bool.
        :param socket: Whether or not this attribute can receive
                       connections.

        :type  dataType: type.
        :param dataType: Type of the data represented by this attribute
                         in order to highlight attributes of the same
                         type while performing a connection.

        :type  plugMaxConnections: int.
        :param plugMaxConnections: The maximum connections that the plug can have (-1 for infinite).

        :type  socketMaxConnections: int.
        :param socketMaxConnections: The maximum connections that the socket can have (-1 for infinite).

        """
        if node not in self.scene_nodes.values():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Attribute creation aborted !")
            return

        if name in node.attrs:
            nlog.error(
                f"An attribute with the same name already exists : {name}"
            )
            nlog.error("Attribute creation aborted !")
            return

        node._createAttribute(
            name=name,
            index=index,
            preset=preset,
            plug=plug,
            socket=socket,
            dataType=dataType,
            plugMaxConnections=plugMaxConnections,
            socketMaxConnections=socketMaxConnections,
        )

        # Emit signal.
        self.signal_AttrCreated.emit(node.name, index)

    def deleteAttribute(self, node: NodeItem, index: int) -> None:
        """
        Delete the specified attribute.

        :type  node: class.
        :param node: The node instance that you want to delete.

        :type  index: int.
        :param index: The index of the attribute in the node.

        """
        if node not in self.scene_nodes.values():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Attribute deletion aborted !")
            return

        node._deleteAttribute(index)

        # Emit signal.
        self.signal_AttrDeleted.emit(node.name, index)

    def editAttribute(
        self,
        node: NodeItem,
        index: int,
        newName: str | None = None,
        newIndex: int | None = None,
    ) -> None:
        """
        Edit the specified attribute.

        :type  node: class.
        :param node: The node instance that you want to delete.

        :type  index: int.
        :param index: The index of the attribute in the node.

        :type  newName: str.
        :param newName: The new name for the given attribute.

        :type  newIndex: int.
        :param newIndex: The index for the given attribute.

        """
        if node not in self.scene_nodes.values():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Attribute creation aborted !")
            return

        if newName is not None:
            if newName in node.attrs:
                nlog.error(
                    f"An attribute with the same name already exists : {newName}"
                )
                nlog.error("Attribute edition aborted !")
                return
            else:
                oldName = node.attrs[index]

            # Rename in the slot item(s).
            if node.attrsData[oldName]["plug"]:
                node.plugs[oldName].attribute = newName
                node.plugs[newName] = node.plugs[oldName]
                node.plugs.pop(oldName)
                for connection in node.plugs[newName].connections:
                    connection.plugAttr = newName

            if node.attrsData[oldName]["socket"]:
                node.sockets[oldName].attribute = newName
                node.sockets[newName] = node.sockets[oldName]
                node.sockets.pop(oldName)
                for connection in node.sockets[newName].connections:
                    connection.socketAttr = newName

            # Replace attribute data.
            node.attrsData[oldName]["name"] = newName
            node.attrsData[newName] = node.attrsData[oldName]
            node.attrsData.pop(oldName)
            node.attrs[index] = newName

        if isinstance(newIndex, int):
            utils._swapListIndices(node.attrs, index, newIndex)

            # Refresh connections.
            for plug in node.plugs.values():
                plug.update()
                if plug.connections:
                    for connection in plug.connections:
                        if isinstance(connection.source, PlugItem):
                            connection.source = plug
                            connection.source_point = plug.center()
                        else:
                            connection.target = plug
                            connection.target_point = plug.center()
                        if newName:
                            connection.plugAttr = newName
                        connection.updatePath()

            for socket in node.sockets.values():
                socket.update()
                if socket.connections:
                    for connection in socket.connections:
                        if isinstance(connection.source, SocketItem):
                            connection.source = socket
                            connection.source_point = socket.center()
                        else:
                            connection.target = socket
                            connection.target_point = socket.center()
                        if newName:
                            connection.socketAttr = newName
                        connection.updatePath()

            self.scene().update()

        node.update()

        # Emit signal.
        if newIndex:
            self.signal_AttrEdited.emit(node.name, index, newIndex)
        else:
            self.signal_AttrEdited.emit(node.name, index, index)

    # GRAPH
    def saveGraph(self, filePath: str = "path") -> None:
        """
        Get all the current graph infos and store them in a .json file
        at the given location.

        :type  filePath: str.
        :param filePath: The path where you want to save your graph at.

        """
        data = dict()

        # Store nodes data.
        data["NODES"] = dict()

        nodes = self.scene_nodes.keys()
        for node in nodes:
            nodeInst = self.scene_nodes[node]
            preset = nodeInst.nodePreset
            nodeAlternate = nodeInst.alternate

            data["NODES"][node] = {
                "preset": preset,
                "position": [nodeInst.pos().x(), nodeInst.pos().y()],
                "alternate": nodeAlternate,
                "attributes": [],
            }

            attrs = nodeInst.attrs
            for attr in attrs:
                attrData = nodeInst.attrsData[attr]

                # serialize dataType if needed.
                if isinstance(attrData["dataType"], type):
                    attrData["dataType"] = str(attrData["dataType"])

                data["NODES"][node]["attributes"].append(attrData)

        # Store connections data.
        data["CONNECTIONS"] = self.evaluateGraph()

        # Save data.
        try:
            utils._saveData(filePath=filePath, data=data)
        except BaseException:
            raise FileNotFoundError(f"Invalid path : {filePath}")

        # Emit signal.
        self.signal_GraphSaved.emit()

    def loadGraph(self, filePath: str = "path") -> None:
        """
        Get all the stored info from the .json file at the given location
        and recreate the graph as saved.

        :type  filePath: str.
        :param filePath: The path where you want to load your graph from.

        """
        # Load data.
        if os.path.exists(filePath):
            data = utils._loadData(filePath=filePath)
        else:
            raise FileNotFoundError(f"Invalid path : {filePath}")

        # Apply nodes data.
        nodesData = data["NODES"]
        nodesName = nodesData.keys()

        for name in nodesName:
            preset = nodesData[name]["preset"]
            position = nodesData[name]["position"]
            position = QtCore.QPointF(position[0], position[1])
            alternate = nodesData[name]["alternate"]

            node = self.createNode(
                name=name,
                preset=preset,
                position=position,
                alternate=alternate,
            )

            if node is None:
                nlog.warning(f"Not loading node {name}.")
                continue

            # Apply attributes data.
            attrsData = nodesData[name]["attributes"]

            for attrData in attrsData:
                index = attrsData.index(attrData)
                name = attrData["name"]
                plug = attrData["plug"]
                socket = attrData["socket"]
                preset = attrData["preset"]
                dataType = attrData["dataType"]
                plugMaxConnections = attrData["plugMaxConnections"]
                socketMaxConnections = attrData["socketMaxConnections"]

                # un-serialize data type if needed
                if isinstance(dataType, str) and dataType.find("<") == 0:
                    dataType = eval(str(dataType.split("'")[1]))

                self.createAttribute(
                    node=node,
                    name=name,
                    index=index,
                    preset=preset,
                    plug=plug,
                    socket=socket,
                    dataType=dataType,
                    plugMaxConnections=plugMaxConnections,
                    socketMaxConnections=socketMaxConnections,
                )

        # Apply connections data.
        connectionsData = data["CONNECTIONS"]

        for connection in connectionsData:
            source = connection[0]
            sourceNode = source.split(".")[0]
            sourceAttr = source.split(".")[1]

            target = connection[1]
            targetNode = target.split(".")[0]
            targetAttr = target.split(".")[1]

            self.createConnection(
                sourceNode, sourceAttr, targetNode, targetAttr
            )

        self.scene().update()

        # Emit signal.
        self.signal_GraphLoaded.emit()

    def createConnection(
        self,
        sourceNode: str,
        sourceAttr: str,
        targetNode: str,
        targetAttr: str,
    ) -> ConnectionItem:
        """
        Create a manual connection.

        :type  sourceNode: str.
        :param sourceNode: Node that emits the connection.

        :type  sourceAttr: str.
        :param sourceAttr: Attribute that emits the connection.

        :type  targetNode: str.
        :param targetNode: Node that receives the connection.

        :type  targetAttr: str.
        :param targetAttr: Attribute that receives the connection.

        """
        plug = self.scene_nodes[sourceNode].plugs[sourceAttr]
        socket = self.scene_nodes[targetNode].sockets[targetAttr]

        connection = ConnectionItem(
            plug.center(), socket.center(), plug, socket
        )

        connection.plugNode = plug.parentItem().name
        connection.plugAttr = plug.attribute
        connection.socketNode = socket.parentItem().name
        connection.socketAttr = socket.attribute

        plug.connect(socket, connection)
        socket.connect(plug, connection)

        connection.updatePath()

        self.scene().addItem(connection)

        return connection

    def evaluateGraph(self) -> list:
        """
        Create a list of connection tuples.
        [("sourceNode.attribute", "TargetNode.attribute"), ...]

        """
        scene = self.scene()

        data = list()

        for item in scene.items():
            if isinstance(item, ConnectionItem):
                connection = item

                data.append(connection._outputConnectionData())

        # Emit Signal
        self.signal_GraphEvaluated.emit()

        return data

    def clearGraph(self) -> None:
        """
        Clear the graph.

        """
        self.scene().clear()
        self.scene_nodes = dict()

        # Emit signal.
        self.signal_GraphCleared.emit()

    ##################################################################
    # END API
    ##################################################################


class NodeScene(QtWidgets.QGraphicsScene):
    """
    The scene displaying all the nodes.

    """

    signal_NodeMoved = QtCore.Signal(str, object)  # type: ignore (qtpy)

    def __init__(self, parent) -> None:
        """
        Initialize the class.

        """
        super(NodeScene, self).__init__(parent)

        # General.
        self.gridSize = parent.config["grid_size"]

        # Nodes storage.
        self.nodes = dict()

    @property
    def nodz_instance(self) -> Nodz:
        try:
            view = self.views()[0]
        except BaseException as err:
            raise RuntimeError(f"Could not get first scene view: {err} ")
        else:
            if isinstance(view, Nodz):
                return view
            else:
                raise TypeError(f"Unexpected view type: {view}")

    def dragEnterEvent(
        self,
        event: QtWidgets.QGraphicsSceneDragDropEvent,
    ) -> None:
        """
        Make the dragging of nodes into the scene possible.

        """
        event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        event.accept()

    def dragMoveEvent(
        self,
        event: QtWidgets.QGraphicsSceneDragDropEvent,
    ) -> None:
        """
        Make the dragging of nodes into the scene possible.

        """
        event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        event.accept()

    def dropEvent(
        self,
        event: QtWidgets.QGraphicsSceneDragDropEvent,
    ) -> None:
        """
        Create a node from the dropped item.

        """
        # Emit signal.
        if self.views():
            self.nodz_instance.signal_Dropped.emit(event.scenePos())

        event.accept()

    def drawBackground(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRect | QtCore.QRectF,
    ) -> None:
        """
        Draw a grid in the background.

        """
        config = self.nodz_instance.config

        self._brush = QtGui.QBrush()
        self._brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self._brush.setColor(utils._convertDataToColor(config["bg_color"]))

        painter.fillRect(rect, self._brush)

        if self.nodz_instance.gridVisToggle:
            leftLine = rect.left() - rect.left() % self.gridSize
            topLine = rect.top() - rect.top() % self.gridSize
            lines = list()

            i = int(leftLine)
            while i < int(rect.right()):
                lines.append(QtCore.QLineF(i, rect.top(), i, rect.bottom()))
                i += self.gridSize

            u = int(topLine)
            while u < int(rect.bottom()):
                lines.append(QtCore.QLineF(rect.left(), u, rect.right(), u))
                u += self.gridSize

            self.pen = QtGui.QPen()
            self.pen.setColor(utils._convertDataToColor(config["grid_color"]))
            self.pen.setWidth(0)
            painter.setPen(self.pen)
            painter.drawLines(lines)

    def updateScene(self) -> None:
        """
        Update the connections position.

        """
        for connection in [
            i for i in self.items() if isinstance(i, ConnectionItem)
        ]:
            if not connection.target:
                raise RuntimeError("connection.target is invalid")
            connection.target_point = connection.target.center()
            if not connection.source:
                raise RuntimeError("connection.source is invalid")
            connection.source_point = connection.source.center()
            connection.updatePath()


class NodeItem(QtWidgets.QGraphicsItem):
    """
    A graphic representation of a node containing attributes.

    """

    def __init__(
        self, name: str, alternate: bool, preset: str, config: dict
    ) -> None:
        """
        Initialize the class.

        :type  name: str.
        :param name: The name of the node. The name has to be unique
                     as it is used as a key to store the node object.

        :type  alternate: bool.
        :param alternate: The attribute color alternate state, if True,
                          every 2 attribute the color will be slightly
                          darker.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        """
        super(NodeItem, self).__init__()

        self.setZValue(1)

        # Storage
        self.name = name
        self.alternate = alternate
        self.nodePreset = preset
        self.attrPreset = None

        # Attributes storage.
        self.attrs = list()
        self.attrsData = dict()
        self.attrCount = 0

        self.plugs = dict()
        self.sockets = dict()

        # Methods.
        self._createStyle(config)

    @property
    def nodz_instance(self) -> Nodz:
        return _nodz_instance(self)

    @property
    def nodz_scene(self) -> NodeScene:
        return _nodz_scene(self)

    @property
    def scene_nodes(self):
        return self.nodz_scene.nodes

    @property
    def height(self) -> int:
        """
        Increment the final height of the node every time an attribute
        is created.

        """
        if self.attrCount > 0:
            return (
                self.baseHeight
                + self.attrHeight * self.attrCount
                + self.border
                + 0.5 * self.radius
            )
        else:
            return self.baseHeight

    @property
    def pen(self) -> QtGui.QPen:
        """
        Return the pen based on the selection state of the node.

        """
        if self.isSelected():
            return self._penSel
        else:
            return self._pen

    def _createStyle(self, config: dict) -> None:
        """
        Read the node style from the configuration file.

        """
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        # Dimensions.
        self.baseWidth = config["node_width"]
        self.baseHeight = config["node_height"]
        self.attrHeight = config["node_attr_height"]
        self.border = config["node_border"]
        self.radius = config["node_radius"]

        self.nodeCenter = QtCore.QPointF()
        self.nodeCenter.setX(self.baseWidth / 2.0)
        self.nodeCenter.setY(self.height / 2.0)

        self._brush = QtGui.QBrush()
        self._brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self._brush.setColor(
            utils._convertDataToColor(config[self.nodePreset]["bg"])
        )

        self._pen = QtGui.QPen()
        self._pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._pen.setWidth(self.border)
        self._pen.setColor(
            utils._convertDataToColor(config[self.nodePreset]["border"])
        )

        self._penSel = QtGui.QPen()
        self._penSel.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._penSel.setWidth(self.border)
        self._penSel.setColor(
            utils._convertDataToColor(config[self.nodePreset]["border_sel"])
        )

        self._textPen = QtGui.QPen()
        self._textPen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._textPen.setColor(
            utils._convertDataToColor(config[self.nodePreset]["text"])
        )

        self._nodeTextFont = QtGui.QFont(
            config["node_font"],
            config["node_font_size"],
            QtGui.QFont.Weight.Bold,
        )
        self._attrTextFont = QtGui.QFont(
            config["attr_font"],
            config["attr_font_size"],
            QtGui.QFont.Weight.Normal,
        )

        self._attrBrush = QtGui.QBrush()
        self._attrBrush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)

        self._attrBrushAlt = QtGui.QBrush()
        self._attrBrushAlt.setStyle(QtCore.Qt.BrushStyle.SolidPattern)

        self._attrPen = QtGui.QPen()
        self._attrPen.setStyle(QtCore.Qt.PenStyle.SolidLine)

    def _createAttribute(
        self,
        name: str,
        index: int,
        preset: str,
        plug: bool,
        socket: bool,
        dataType: Any,
        plugMaxConnections: int,
        socketMaxConnections: int,
    ) -> None:
        """
        Create an attribute by expanding the node, adding a label and
        connection items.

        :type  name: str.
        :param name: The name of the attribute. The name has to be
                     unique as it is used as a key to store the node
                     object.

        :type  index: int.
        :param index: The index of the attribute in the node.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :type  plug: bool.
        :param plug: Whether or not this attribute can emit connections.

        :type  socket: bool.
        :param socket: Whether or not this attribute can receive
                       connections.

        :type  dataType: type.
        :param dataType: Type of the data represented by this attribute
                         in order to highlight attributes of the same
                         type while performing a connection.

        """
        if name in self.attrs:
            nlog.error(
                "An attribute with the same name already exists on this "
                f"node : {name}"
            )
            nlog.error("Attribute creation aborted !")
            return

        self.attrPreset = preset

        # Create a plug connection item.
        if plug:
            plugInst = PlugItem(
                parent=self,
                attribute=name,
                index=self.attrCount,
                preset=preset,
                dataType=dataType,
                maxConnections=plugMaxConnections,
            )

            self.plugs[name] = plugInst

        # Create a socket connection item.
        if socket:
            socketInst = SocketItem(
                parent=self,
                attribute=name,
                index=self.attrCount,
                preset=preset,
                dataType=dataType,
                maxConnections=socketMaxConnections,
            )

            self.sockets[name] = socketInst

        self.attrCount += 1

        # Add the attribute based on its index.
        if index == -1 or index > self.attrCount:
            self.attrs.append(name)
        else:
            self.attrs.insert(index, name)

        # Store attr data.
        self.attrsData[name] = {
            "name": name,
            "socket": socket,
            "plug": plug,
            "preset": preset,
            "dataType": dataType,
            "plugMaxConnections": plugMaxConnections,
            "socketMaxConnections": socketMaxConnections,
        }

        # Update node height.
        self.update()

    def _deleteAttribute(self, index: int) -> None:
        """
        Remove an attribute by reducing the node, removing the label
        and the connection items.

        :type  index: int.
        :param index: The index of the attribute in the node.

        """
        name = self.attrs[index]

        # Remove socket and its connections.
        if name in self.sockets.keys():
            for connection in self.sockets[name].connections:
                connection._remove()

            self.scene().removeItem(self.sockets[name])
            self.sockets.pop(name)

        # Remove plug and its connections.
        if name in self.plugs.keys():
            for connection in self.plugs[name].connections:
                connection._remove()

            self.scene().removeItem(self.plugs[name])
            self.plugs.pop(name)

        # Reduce node height.
        if self.attrCount > 0:
            self.attrCount -= 1

        # Remove attribute from node.
        if name in self.attrs:
            self.attrs.remove(name)

        self.update()

    def _remove(self) -> None:
        """
        Remove this node instance from the scene.

        Make sure that all the connections to this node are also removed
        in the process

        """
        self.scene_nodes.pop(self.name)

        # Remove all sockets connections.
        for socket in self.sockets.values():
            while len(socket.connections) > 0:
                socket.connections[0]._remove()

        # Remove all plugs connections.
        for plug in self.plugs.values():
            while len(plug.connections) > 0:
                plug.connections[0]._remove()

        # Remove node.
        scene = self.scene()
        scene.removeItem(self)
        scene.update()

    def boundingRect(self) -> QtCore.QRectF:
        """
        The bounding rect based on the width and height variables.

        """
        rect = QtCore.QRect(0, 0, self.baseWidth, self.height).toRectF()
        return rect

    def shape(self) -> QtGui.QPainterPath:
        """
        The shape of the item.

        """
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        """
        Paint the node and attributes.

        """
        # Node base.
        painter.setBrush(self._brush)
        painter.setPen(self.pen)

        painter.drawRoundedRect(
            0, 0, self.baseWidth, self.height, self.radius, self.radius
        )

        # Node label.
        painter.setPen(self._textPen)
        painter.setFont(self._nodeTextFont)

        metrics = QtGui.QFontMetrics(painter.font())
        text_width = metrics.boundingRect(self.name).width() + 14
        text_height = metrics.boundingRect(self.name).height() + 14
        margin = (text_width - self.baseWidth) * 0.5
        textRect = QtCore.QRect(-margin, -text_height, text_width, text_height)

        painter.drawText(
            textRect, QtCore.Qt.AlignmentFlag.AlignCenter, self.name
        )

        # Attributes.
        offset = 0
        for attr in self.attrs:
            nodz_inst = self.nodz_instance
            config = self.nodz_instance.config

            # Attribute rect.
            rect = QtCore.QRect(
                self.border / 2,
                self.baseHeight - self.radius + offset,
                self.baseWidth - self.border,
                self.attrHeight,
            )

            attrData = self.attrsData[attr]
            name = attr

            preset = attrData["preset"]

            # Attribute base.
            self._attrBrush.setColor(
                utils._convertDataToColor(config[preset]["bg"])
            )
            if self.alternate:
                self._attrBrushAlt.setColor(
                    utils._convertDataToColor(
                        config[preset]["bg"], True, config["alternate_value"]
                    )
                )

            self._attrPen.setColor(utils._convertDataToColor([0, 0, 0, 0]))
            painter.setPen(self._attrPen)
            painter.setBrush(self._attrBrush)
            if (offset / self.attrHeight) % 2:
                painter.setBrush(self._attrBrushAlt)

            painter.drawRect(rect)

            # Attribute label.
            painter.setPen(utils._convertDataToColor(config[preset]["text"]))
            painter.setFont(self._attrTextFont)

            # Search non-connectable attributes.
            if nodz_inst.drawingConnection:
                if self == nodz_inst.currentHoveredNode:
                    if not nodz_inst.sourceSlot:
                        raise TypeError("Invalid sourceSlot")
                    if attrData[
                        "dataType"
                    ] != nodz_inst.sourceSlot.dataType or (
                        nodz_inst.sourceSlot.slotType == "plug"
                        and attrData["socket"] is False
                        or nodz_inst.sourceSlot.slotType == "socket"
                        and attrData["plug"] is False
                    ):
                        # Set non-connectable attributes color.
                        painter.setPen(
                            utils._convertDataToColor(
                                config["non_connectable_color"]
                            )
                        )

            textRect = QtCore.QRect(
                rect.left() + self.radius,
                rect.top(),
                rect.width() - 2 * self.radius,
                rect.height(),
            )
            painter.drawText(
                textRect, QtCore.Qt.AlignmentFlag.AlignVCenter, name
            )

            offset += self.attrHeight

    def mousePressEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Keep the selected node on top of the others.

        """
        nodes = self.scene_nodes
        for node in nodes.values():
            node.setZValue(1)

        for item in self.scene().items():
            if isinstance(item, ConnectionItem):
                item.setZValue(1)

        self.setZValue(2)

        super(NodeItem, self).mousePressEvent(event)

    def mouseDoubleClickEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Emit a signal.

        """
        super(NodeItem, self).mouseDoubleClickEvent(event)
        self.nodz_instance.signal_NodeDoubleClicked.emit(self.name)

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        .

        """
        nodz_inst = self.nodz_instance
        if nodz_inst.gridVisToggle:
            if nodz_inst.gridSnapToggle or nodz_inst._nodeSnap:
                gridSize = self.nodz_scene.gridSize

                currentPos = self.mapToScene(
                    event.pos().x() - self.baseWidth / 2,
                    event.pos().y() - self.height / 2,
                )

                snap_x = (
                    round(currentPos.x() / gridSize) * gridSize
                ) - gridSize / 4
                snap_y = (
                    round(currentPos.y() / gridSize) * gridSize
                ) - gridSize / 4
                snap_pos = QtCore.QPointF(snap_x, snap_y)
                self.setPos(snap_pos)

                self.nodz_scene.updateScene()
            else:
                self.nodz_scene.updateScene()
                super(NodeItem, self).mouseMoveEvent(event)

    def mouseReleaseEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        .

        """
        # Emit node moved signal.
        self.nodz_scene.signal_NodeMoved.emit(self.name, self.pos())
        super(NodeItem, self).mouseReleaseEvent(event)

    def hoverLeaveEvent(
        self, event: QtWidgets.QGraphicsSceneHoverEvent
    ) -> None:
        """
        .

        """
        for item in self.nodz_instance.scene().items():
            if isinstance(item, ConnectionItem):
                item.setZValue(0)

        super(NodeItem, self).hoverLeaveEvent(event)


class SlotItem(QtWidgets.QGraphicsItem):
    """
    The base class for graphics item representing attributes hook.

    """

    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        attribute: str,
        preset: str,
        index: int,
        dataType: Any,
        maxConnections: int,
    ) -> None:
        """
        Initialize the class.

        :param parent: The parent item of the slot.
        :type  parent: QtWidgets.QGraphicsItem instance.

        :param attribute: The attribute associated to the slot.
        :type  attribute: String.

        :param index: int.
        :type  index: The index of the attribute in the node.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :param dataType: The data type associated to the attribute.
        :type  dataType: Type.

        """
        super(SlotItem, self).__init__(parent)

        # Status.
        self.setAcceptHoverEvents(True)

        # Storage.
        self.slotType = None
        self.attribute = attribute
        self.preset = preset
        self.index = index
        self.dataType = dataType

        # Style.
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)

        self.pen = QtGui.QPen()
        self.pen.setStyle(QtCore.Qt.PenStyle.SolidLine)

        # Connections storage.
        self.connected_slots = list()
        self.newConnection = None
        self.connections = list()
        self.maxConnections = maxConnections

    @property
    def nodz_instance(self) -> Nodz:
        return _nodz_instance(self)

    def parent_node_item(self) -> NodeItem:
        item = self.parentItem()
        if isinstance(item, NodeItem):
            return item
        raise TypeError(f"Unexpected parent type: {item}")

    def connect(self, item: Any, connection: ConnectionItem) -> None:
        raise NotImplementedError("Sub-Classes MUST implement connect() !")

    def disconnect(self, connection: ConnectionItem) -> None:
        raise NotImplementedError("Sub-Classes MUST implement connect() !")

    def accepts(self, slot_item: SlotItem) -> bool:
        """
        Only accepts plug items that belong to other nodes, and only if
        the max connections count is not reached yet.

        """
        # no plug on plug or socket on socket
        hasPlugItem = isinstance(self, PlugItem) or isinstance(
            slot_item, PlugItem
        )
        hasSocketItem = isinstance(self, SocketItem) or isinstance(
            slot_item, SocketItem
        )
        if not (hasPlugItem and hasSocketItem):
            return False

        # no self connection
        if self.parentItem() == slot_item.parentItem():
            return False

        # no more than maxConnections
        if (
            self.maxConnections > 0
            and len(self.connected_slots) >= self.maxConnections
        ):
            return False

        # no connection with different types
        if slot_item.dataType != self.dataType:
            return False

        # otherwize, all fine.
        return True

    def mousePressEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Start the connection process.

        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.newConnection = ConnectionItem(
                self.center().toPoint(),
                self.mapToScene(event.pos()).toPoint(),
                self,
                None,
            )

            self.connections.append(self.newConnection)
            self.scene().addItem(self.newConnection)

            nodzInst = self.nodz_instance
            nodzInst.drawingConnection = True
            nodzInst.sourceSlot = self
        else:
            super(SlotItem, self).mousePressEvent(event)

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Update the new connection's end point position.

        """
        nodzInst = self.nodz_instance
        config = nodzInst.config
        if nodzInst.drawingConnection:
            mbb = utils._createPointerBoundingBox(
                pointerPos=event.scenePos().toPoint(),
                bbSize=config["mouse_bounding_box"],
            )

            # Get nodes in pointer's bounding box.
            targets = self.scene().items(mbb)

            if any(isinstance(target, NodeItem) for target in targets):
                if self.parentItem() not in targets:
                    for target in targets:
                        if isinstance(target, NodeItem):
                            nodzInst.currentHoveredNode = target
            else:
                nodzInst.currentHoveredNode = None

            # Set connection's end point.
            if not self.newConnection:
                raise RuntimeError("newConnection is invalid.")
            self.newConnection.target_point = self.mapToScene(event.pos())
            self.newConnection.updatePath()
        else:
            super(SlotItem, self).mouseMoveEvent(event)

    def mouseReleaseEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Apply the connection if target_slot is valid.

        """
        nodzInst = self.nodz_instance
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            nodzInst.drawingConnection = False

            if not self.newConnection:
                raise RuntimeError("newConnection is invalid")

            target = self.scene().itemAt(
                event.scenePos().toPoint(), QtGui.QTransform()
            )

            if not isinstance(target, SlotItem):
                self.newConnection._remove()
                super(SlotItem, self).mouseReleaseEvent(event)
                return

            if target.accepts(self):
                self.newConnection.target = target
                self.newConnection.source = self
                self.newConnection.target_point = target.center()
                self.newConnection.source_point = self.center()

                # Perform the ConnectionItem.
                self.connect(target, self.newConnection)
                target.connect(self, self.newConnection)

                self.newConnection.updatePath()
            else:
                self.newConnection._remove()
        else:
            super(SlotItem, self).mouseReleaseEvent(event)

        nodzInst.currentHoveredNode = None

    def shape(self) -> QtGui.QPainterPath:
        """
        The shape of the Slot is a circle.

        """
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        """
        Paint the Slot.

        """
        painter.setBrush(self.brush)
        painter.setPen(self.pen)

        nodzInst = self.nodz_instance
        config = nodzInst.config
        if nodzInst.drawingConnection:
            if self.parentItem() == nodzInst.currentHoveredNode:
                painter.setBrush(
                    utils._convertDataToColor(config["non_connectable_color"])
                )
                if not nodzInst.sourceSlot:
                    raise TypeError("Invalid sourceSlot")
                if self.slotType == nodzInst.sourceSlot.slotType or (
                    self.slotType != nodzInst.sourceSlot.slotType
                    and self.dataType != nodzInst.sourceSlot.dataType
                ):
                    painter.setBrush(
                        utils._convertDataToColor(
                            config["non_connectable_color"]
                        )
                    )
                else:
                    _penValid = QtGui.QPen()
                    _penValid.setStyle(QtCore.Qt.PenStyle.SolidLine)
                    _penValid.setWidth(2)
                    _penValid.setColor(QtGui.QColor(255, 255, 255, 255))
                    painter.setPen(_penValid)
                    painter.setBrush(self.brush)

        painter.drawEllipse(self.boundingRect())

    def center(self) -> QtCore.QPointF:
        """
        Return The center of the Slot.

        """
        rect = self.boundingRect()
        center = QtCore.QPointF(
            rect.x() + rect.width() * 0.5, rect.y() + rect.height() * 0.5
        )

        return self.mapToScene(center)


class PlugItem(SlotItem):
    """
    A graphics item representing an attribute out hook.

    """

    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        attribute: str,
        index: int,
        preset: str,
        dataType: Any,
        maxConnections: int,
    ) -> None:
        """
        Initialize the class.

        :param parent: The parent item of the slot.
        :type  parent: QtWidgets.QGraphicsItem instance.

        :param attribute: The attribute associated to the slot.
        :type  attribute: String.

        :param index: int.
        :type  index: The index of the attribute in the node.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :param dataType: The data type associated to the attribute.
        :type  dataType: Type.

        """
        super(PlugItem, self).__init__(
            parent, attribute, preset, index, dataType, maxConnections
        )

        # Storage.
        self.attributte = attribute
        self.preset = preset
        self.slotType = "plug"

        # Methods.
        self._createStyle(parent)

    def _createStyle(self, parent: QtWidgets.QGraphicsItem) -> None:
        """
        Read the attribute style from the configuration file.

        """
        config = self.nodz_instance.config
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self.brush.setColor(
            utils._convertDataToColor(config[self.preset]["plug"])
        )

    def boundingRect(self) -> QtCore.QRectF:
        """
        The bounding rect based on the width and height variables.

        """
        width = height = self.parent_node_item().attrHeight / 2.0

        nodzInst = self.nodz_instance
        config = nodzInst.config

        x = self.parent_node_item().baseWidth - (width / 2.0)
        y = (
            self.parent_node_item().baseHeight
            - config["node_radius"]
            + self.parent_node_item().attrHeight / 4
            + self.parent_node_item().attrs.index(self.attribute)
            * self.parent_node_item().attrHeight
        )

        rect = QtCore.QRect(x, y, width, height).toRectF()
        return rect

    def connect(self, item: SocketItem, connection: ConnectionItem) -> None:
        """
        Connect to the given socket_item.

        """
        if (
            self.maxConnections > 0
            and len(self.connected_slots) >= self.maxConnections
        ):
            # Already connected.
            self.connections[self.maxConnections - 1]._remove()

        # Populate connection.
        connection.socketItem = item
        connection.plugNode = self.parent_node_item().name
        connection.plugAttr = self.attribute

        # Add socket to connected slots.
        if item in self.connected_slots:
            self.connected_slots.remove(item)
        self.connected_slots.append(item)

        # Add connection.
        if connection not in self.connections:
            self.connections.append(connection)

        # Emit signal.
        self.nodz_instance.signal_PlugConnected.emit(
            connection.plugNode,
            connection.plugAttr,
            connection.socketNode,
            connection.socketAttr,
        )

    def disconnect(self, connection: ConnectionItem) -> None:
        """
        Disconnect the given connection from this plug item.

        """
        # Emit signal.
        self.nodz_instance.signal_PlugDisconnected.emit(
            connection.plugNode,
            connection.plugAttr,
            connection.socketNode,
            connection.socketAttr,
        )

        # Remove connected socket from plug
        if connection.socketItem in self.connected_slots:
            self.connected_slots.remove(connection.socketItem)
        # Remove connection
        self.connections.remove(connection)


class SocketItem(SlotItem):
    """
    A graphics item representing an attribute in hook.

    """

    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        attribute: str,
        index: int,
        preset: str,
        dataType: Any,
        maxConnections: int,
    ) -> None:
        """
        Initialize the socket.

        :param parent: The parent item of the slot.
        :type  parent: QtWidgets.QGraphicsItem instance.

        :param attribute: The attribute associated to the slot.
        :type  attribute: String.

        :param index: int.
        :type  index: The index of the attribute in the node.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :param dataType: The data type associated to the attribute.
        :type  dataType: Type.

        """
        super(SocketItem, self).__init__(
            parent, attribute, preset, index, dataType, maxConnections
        )

        # Storage.
        self.attributte = attribute
        self.preset = preset
        self.slotType = "socket"

        # Methods.
        self._createStyle(parent)

    def _createStyle(self, parent: QtWidgets.QGraphicsItem) -> None:
        """
        Read the attribute style from the configuration file.

        """
        config = self.nodz_instance.config
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self.brush.setColor(
            utils._convertDataToColor(config[self.preset]["socket"])
        )

    def boundingRect(self) -> QtCore.QRectF:
        """
        The bounding rect based on the width and height variables.

        """
        width = height = self.parent_node_item().attrHeight / 2.0

        config = self.nodz_instance.config

        x = -width / 2.0
        y = (
            self.parent_node_item().baseHeight
            - config["node_radius"]
            + (self.parent_node_item().attrHeight / 4)
            + self.parent_node_item().attrs.index(self.attribute)
            * self.parent_node_item().attrHeight
        )

        rect = QtCore.QRect(x, y, width, height).toRectF()
        return rect

    def connect(self, item: PlugItem, connection: ConnectionItem) -> None:
        """
        Connect to the given plug item.

        """
        if (
            self.maxConnections > 0
            and len(self.connected_slots) >= self.maxConnections
        ):
            # Already connected.
            self.connections[self.maxConnections - 1]._remove()

        # Populate connection.
        connection.plugItem = item
        connection.socketNode = self.parent_node_item().name
        connection.socketAttr = self.attribute

        # Add plug to connected slots.
        self.connected_slots.append(item)

        # Add connection.
        if connection not in self.connections:
            self.connections.append(connection)

        # Emit signal.
        self.nodz_instance.signal_SocketConnected.emit(
            connection.plugNode,
            connection.plugAttr,
            connection.socketNode,
            connection.socketAttr,
        )

    def disconnect(self, connection: ConnectionItem) -> None:
        """
        Disconnect the given connection from this socket item.

        """
        # Emit signal.
        self.nodz_instance.signal_SocketDisconnected.emit(
            connection.plugNode,
            connection.plugAttr,
            connection.socketNode,
            connection.socketAttr,
        )

        # Remove connected plugs
        if connection.plugItem in self.connected_slots:
            self.connected_slots.remove(connection.plugItem)
        # Remove connections
        self.connections.remove(connection)


class ConnectionItem(QtWidgets.QGraphicsPathItem):
    """
    A graphics path representing a connection between two attributes.

    """

    def __init__(
        self,
        source_point: QtCore.QPoint,
        target_point: QtCore.QPoint,
        source: SlotItem,
        target: SlotItem | None,
    ) -> None:
        """
        Initialize the class.

        :param sourcePoint: Source position of the connection.
        :type  sourcePoint: QPoint.

        :param targetPoint: Target position of the connection
        :type  targetPoint: QPoint.

        :param source: Source item (plug or socket).
        :type  source: class.

        :param target: Target item (plug or socket).
        :type  target: class.

        """
        super(ConnectionItem, self).__init__()

        self.setZValue(1)

        # Storage.
        self.socketNode: str | None = None
        self.socketAttr: str | None = None
        self.plugNode: str | None = None
        self.plugAttr: str | None = None

        self.source_point = source_point
        self.target_point = target_point
        self.source = source
        self.target = target

        self.plugItem: PlugItem | None = None
        self.socketItem: SocketItem | None = None

        self.movable_point = None

        # Methods.
        self._createStyle()

    @property
    def nodz_instance(self) -> Nodz:
        return _nodz_instance(self)

    def _createStyle(self) -> None:
        """
        Read the connection style from the configuration file.

        """
        if not self.source:
            raise RuntimeError("source is invalid")
        config = self.source.nodz_instance.config
        self.setAcceptHoverEvents(True)
        self.setZValue(-1)

        self._pen = QtGui.QPen(
            utils._convertDataToColor(config["connection_color"])
        )
        self._pen.setWidth(config["connection_width"])

    def _outputConnectionData(self) -> tuple[str, str]:
        """
        .

        """
        return (
            "{0}.{1}".format(self.plugNode, self.plugAttr),
            "{0}.{1}".format(self.socketNode, self.socketAttr),
        )

    def mousePressEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Snap the Connection to the mouse.

        """
        nodzInst = self.nodz_instance

        for item in nodzInst.scene().items():
            if isinstance(item, ConnectionItem):
                item.setZValue(0)

        nodzInst.drawingConnection = True

        d_to_target = (event.pos() - self.target_point).manhattanLength()
        d_to_source = (event.pos() - self.source_point).manhattanLength()
        if d_to_target < d_to_source:
            if not self.target:
                raise RuntimeError("Invalid target")
            self.target_point = event.pos()
            self.movable_point = "target_point"
            self.target.disconnect(self)
            self.target = None
            nodzInst.sourceSlot = self.source
        else:
            if not self.source:
                raise RuntimeError("Invalid source")
            self.source_point = event.pos()
            self.movable_point = "source_point"
            self.source.disconnect(self)
            self.source = None
            nodzInst.sourceSlot = self.target

        self.updatePath()

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Move the Connection with the mouse.

        """
        nodzInst = self.nodz_instance
        config = nodzInst.config

        mbb = utils._createPointerBoundingBox(
            pointerPos=event.scenePos().toPoint(),
            bbSize=config["mouse_bounding_box"],
        )

        # Get nodes in pointer's bounding box.
        targets = self.scene().items(mbb)

        if any(isinstance(target, NodeItem) for target in targets):
            if not nodzInst.sourceSlot:
                raise TypeError("Invalid sourceSlot")
            if nodzInst.sourceSlot.parentItem() not in targets:
                for target in targets:
                    if isinstance(target, NodeItem):
                        nodzInst.currentHoveredNode = target
        else:
            nodzInst.currentHoveredNode = None

        if self.movable_point == "target_point":
            self.target_point = event.pos()
        else:
            self.source_point = event.pos()

        self.updatePath()

    def mouseReleaseEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Create a Connection if possible, otherwise delete it.

        """
        self.nodz_instance.drawingConnection = False

        slot = self.scene().itemAt(
            event.scenePos().toPoint(), QtGui.QTransform()
        )

        if not isinstance(slot, SlotItem):
            self._remove()
            self.updatePath()
            super(ConnectionItem, self).mouseReleaseEvent(event)
            return

        if self.movable_point == "target_point":
            if not self.source:
                raise RuntimeError("Invalid source")
            if slot.accepts(self.source):
                # Plug reconnection.
                self.target = slot
                self.target_point = slot.center()
                plug = self.source
                socket = self.target

                # Reconnect.
                socket.connect(plug, self)

                self.updatePath()
            else:
                self._remove()

        else:
            if not self.target:
                raise RuntimeError("Invalid target")
            if slot.accepts(self.target):
                # Socket Reconnection
                self.source = slot
                self.source_point = slot.center()
                socket = self.target
                plug = self.source

                # Reconnect.
                plug.connect(socket, self)

                self.updatePath()
            else:
                self._remove()

    def _remove(self) -> None:
        """
        Remove this Connection from the scene.

        """
        if self.source is not None:
            self.source.disconnect(self)
        if self.target is not None:
            self.target.disconnect(self)

        scene = self.scene()
        scene.removeItem(self)
        scene.update()

    def updatePath(self) -> None:
        """
        Update the path.

        """
        self.setPen(self._pen)

        path = QtGui.QPainterPath()
        path.moveTo(self.source_point)
        dx = (self.target_point.x() - self.source_point.x()) * 0.5
        dy = self.target_point.y() - self.source_point.y()
        ctrl1 = QtCore.QPointF(
            self.source_point.x() + dx, self.source_point.y() + dy * 0
        )
        ctrl2 = QtCore.QPointF(
            self.source_point.x() + dx, self.source_point.y() + dy * 1
        )
        path.cubicTo(ctrl1, ctrl2, self.target_point)

        self.setPath(path)
