from __future__ import annotations
import os
from typing import Any, Optional
from qtpy import QtGui, QtCore, QtWidgets

from .items import (
    PlugItem,
    SocketItem,
    NodeItem,
    ConnectionItem,
    ItemFactory,
)
from .utils import (
    nlog,
    _convert_data_to_color,
    _load_config,
    _load_data,
    _save_data,
)
from .data_types import NodeModel


class NodeScene(QtWidgets.QGraphicsScene):
    """
    The scene containing all the nodes.
    """

    connection_start = QtCore.Signal(object)  # type: ignore (qtpy)

    def __init__(self, parent, config, signals) -> None:
        """
        Initialize the class.

        Args:
            parent (Nodz): The parent Nodz instance.
        """
        super(NodeScene, self).__init__(parent)

        # General.
        self.config = config
        self.signals = signals
        self.factory = ItemFactory()
        self.grid_size = parent.config["grid_size"]
        self.grid_vis_toggle = True
        self.grid_snap_toggle = False
        self._node_snap = False

        # Nodes storage.
        self._node_dict: dict[str, NodeItem] = dict()

        self.selectionChanged.connect(self.selection_changed)
        self.selectionChanged.connect(self._return_selection)

    def register_factory(self, factory) -> None:
        self.factory = factory

    def addItem(self, item: QtWidgets.QGraphicsItem):
        """Extends QGraphicsScene.addItem to update the _node_dict."""
        if isinstance(item, NodeItem):
            self._node_dict[item.model.name] = item
        super().addItem(item)

    def removeItem(self, item: QtWidgets.QGraphicsItem):
        """Extends QGraphicsScene.removeItem to update the _node_dict."""
        if isinstance(item, NodeItem):
            del self._node_dict[item.model.name]
        super().removeItem(item)

    def clear(self):
        """Extends QGraphicsScene.clear to update the _node_dict."""
        self._node_dict = dict()
        super().clear()

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
            self.signals.Dropped.emit(event.scenePos())

        event.accept()

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Snap the node to the grid if snapping.
        """
        if event.buttons() != QtCore.Qt.MouseButton.LeftButton:
            return super().mouseMoveEvent(event)
        selected = self.selectedItems()

        if not (selected and self.grid_vis_toggle):
            return super().mouseMoveEvent(event)

        if self.grid_snap_toggle or self._node_snap:
            grid_size = self.grid_size
            epos_x = event.scenePos().x()
            epos_y = event.scenePos().y()

            for node_item in selected:
                node_rect = node_item.boundingRect()
                current_pos = QtCore.QPointF(
                    epos_x - node_rect.width() / 2,
                    epos_y - node_rect.height() / 2,
                )
                snap_x = (
                    round(current_pos.x() / grid_size) * grid_size
                ) - grid_size / 4
                snap_y = (
                    round(current_pos.y() / grid_size) * grid_size
                ) - grid_size / 4
                snap_pos = QtCore.QPointF(snap_x, snap_y)
                node_item.setPos(snap_pos)

            self.update_scene()
        else:
            self.update_scene()
            super().mouseMoveEvent(event)

    @QtCore.Slot()  # type: ignore
    def selection_changed(self):
        # Keep the selected node on top of the others.
        for item in self.items():
            if isinstance(item, (NodeItem, ConnectionItem)):
                item.setZValue(1)
        for item in self.selectedItems():
            item.setZValue(2)

    def drawBackground(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRect | QtCore.QRectF,
    ) -> None:
        """
        Draw a grid in the background.

        Args:
            painter (QtGui.QPainter): The painter to draw with.
            rect (QtCore.QRect | QtCore.QRectF): The rectangle to draw in.
        """
        config = self.config

        self._brush = QtGui.QBrush()
        self._brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self._brush.setColor(_convert_data_to_color(config["bg_color"]))

        painter.fillRect(rect, self._brush)

        if self.grid_vis_toggle:
            left_line = rect.left() - rect.left() % self.grid_size
            top_line = rect.top() - rect.top() % self.grid_size
            lines = list()

            i = int(left_line)
            while i < int(rect.right()):
                lines.append(QtCore.QLineF(i, rect.top(), i, rect.bottom()))
                i += self.grid_size

            u = int(top_line)
            while u < int(rect.bottom()):
                lines.append(QtCore.QLineF(rect.left(), u, rect.right(), u))
                u += self.grid_size

            self.pen = QtGui.QPen()
            self.pen.setColor(_convert_data_to_color(config["grid_color"]))
            self.pen.setWidth(0)
            painter.setPen(self.pen)
            painter.drawLines(lines)

    def update_scene(self) -> None:
        """
        Update the connections position.
        """
        for connection in [
            i for i in self.items() if isinstance(i, ConnectionItem)
        ]:
            if connection.target:
                connection.target_point = connection.target.center()
            if connection.source:
                connection.source_point = connection.source.center()
            connection.update_path()

    def _delete_selected_nodes(self) -> None:
        """
        Delete selected nodes.
        """
        for node in self.selectedItems():
            if not isinstance(node, NodeItem):
                raise TypeError(f"Unexpected node type in graph: {node}")
            self.delete_node(node)

    def _return_selection(self) -> None:
        """
        Wrapper to return selected items.
        """
        selected_nodes = list()
        if self.selectedItems():
            for node in self.selectedItems():
                if node in self.node_items():
                    selected_nodes.append(node.model.name)  # type: ignore

        # Emit signal.
        self.signals.NodeSelected.emit(selected_nodes)

    def snap_node_to_grid(self, state: bool):
        self._node_snap = state

    def add_node(
        self, node_item: NodeItem, position: Optional[QtCore.QPointF] = None
    ) -> None:
        """
        Add a node to the scene and position it if possible.

        Args:
            node_item (NodeItem): The node to add.
            position (QtCore.QPointF | None, optional): The node's position.
                Defaults to None (position at scene center).
        """
        self.addItem(node_item)

        # Set node position.
        if (
            not position or position == QtCore.QPointF(-1, -1)
        ) and self.views():
            # Get the center of the view.
            view = self.views()[0]
            position = view.mapToScene(view.viewport().rect().center())
        if position:
            node_item.setPos(position - node_item.node_center)

    ##################################################################
    # API
    ##################################################################

    def api_load_config(self, file_path: str) -> None:
        """
        Set a specific configuration for this instance of Nodz.

        Args:
            file_path (str): The config file path to load.
        """
        self.config = _load_config(file_path)

    # NODES

    def node_by_name(self, name: str) -> NodeItem:
        try:
            return self._node_dict[name]
        except KeyError:
            raise KeyError(f"NodeItem '{name}' is not in the scene !")

    def node_names(self) -> list[str]:
        return list(self._node_dict)

    def node_items(self) -> list[NodeItem]:
        return list(self._node_dict.values())

    def create_node(
        self,
        name: str = "default",
        preset: str = "node_default",
        position: Optional[QtCore.QPointF] = None,
        alternate: bool = True,
        **kwargs,
    ) -> NodeItem:
        """
        Create a new node with a given name, position and color.

        Args:
            name (str): The name of the node.
            preset (str): The preset to use for the node creation.
            position (QPointF): The position of the node in the scene.
            alternate (bool): Whether to use the alternate color.

        Returns:
            NodeItem: The newly created NodeItem object.
        """
        # Check for name clashes
        if name in self.node_names():
            raise NameError(
                f"A node with the same name already exists : {name}"
            )

        node_item = self.factory.create_node_item(
            NodeModel(name, preset, alternate, kwargs=kwargs), self.config
        )
        self.add_node(node_item, position=position)

        # Emit signal.
        self.signals.NodeCreated.emit(node_item.model)

        return node_item

    def delete_node(self, node: NodeItem) -> None:
        """
        Delete the specified node from the view.

        Args:
           node (NodeItem): The Node instance to be deleted.
        """
        if node not in self.node_items():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Node deletion aborted !")
            return

        if node in self.node_items():
            node._remove_connections()
            # Remove node.
            self.removeItem(node)
            self.update()
            # Emit signal.
            self.signals.NodeDeleted.emit(node.model.name)

    def rename_node(self, node, new_name: str) -> None:
        """
        Rename an existing node.

        Args:
            node (NodeItem): The Node instance to be renamed.
            new_name (str, optional): The new name for the given node.
        """
        if node not in self.node_items():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Node edition aborted !")
            return

        old_name = node.model.name

        # Check for name clashes
        if new_name in self.node_names():
            nlog.error(
                f"A node with the same name already exists : {new_name}"
            )
            nlog.error("Node edition aborted !")
            return
        else:
            node.model.name = new_name

        # Replace node data.
        self._node_dict[new_name] = self._node_dict[old_name]
        self._node_dict.pop(old_name)

        # Store new node name in the connections
        if node.sockets:
            for socket in node.sockets.values():
                for connection in socket.connections:
                    connection.socketNode = new_name

        if node.plugs:
            for plug in node.plugs.values():
                for connection in plug.connections:
                    connection.plugNode = new_name

        node.update()

        # Emit signal.
        self.signals.NodeRenamed.emit(old_name, new_name)

    # ATTRS
    def create_attribute(
        self,
        node: NodeItem,
        name: str = "default",
        index: int = -1,
        preset: str = "attr_default",
        plug: bool = True,
        socket: bool = True,
        data_type: Any = None,
        plug_max_connections: int = -1,
        socket_max_connections: int = 1,
        **kwargs,
    ) -> None:
        """
        Create a new attribute with a given name.

        Args:
            node (NodeItem): The node instance that you want to add the
                attribute to.
            name (str): The name for the new attribute.
            index (int): The index position for the new attribute.
            preset (str): The preset for the new attribute.
            plug (bool): Whether to create a plug for the new attribute.
            socket (bool): Whether to create a socket for the new attribute.
            data_type (Any): The data type for the new attribute.
            plug_max_connections (int): The maximum number of connections for
                the plug.
            socket_max_connections (int): The maximum number of connections for
                the socket.
        """
        if node not in self.node_items():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Attribute creation aborted !")
            return

        if name in node.attr_names:
            nlog.error(
                f"An attribute with the same name already exists : {name}"
            )
            nlog.error("Attribute creation aborted !")
            return

        node._create_attribute(
            name=name,
            index=index,
            preset=preset,
            plug=plug,
            socket=socket,
            data_type=data_type,
            plug_max_connections=plug_max_connections,
            socket_max_connections=socket_max_connections,
            **kwargs,
        )

        # Emit signal.
        self.signals.AttrCreated.emit(node.model, name)

    def delete_attribute(self, node: NodeItem, attr_name: str) -> None:
        """
        Delete the specified attribute.

        Args:
            node (NodeItem): The node object from which the attribute will be deleted.
            index (int): The index of the attribute within the node's attributes list.
        """
        if node not in self.node_items():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Attribute deletion aborted !")
            return

        node._delete_attribute(attr_name)

        # Emit signal.
        self.signals.AttrDeleted.emit(node.model, attr_name)

    def edit_attribute(
        self,
        node: NodeItem,
        index: int,
        new_name: Optional[str] = None,
        new_index: Optional[int] = None,
    ) -> None:
        """
        Edit the specified attribute.

        Args:
            node (NodeItem): The node object that contains the attribute to be edited.
            index (int): The index of the attribute to be edited.
            new_name (str): The new name for the attribute.
            new_index (int): The new index for the attribute.
        """
        if node not in self.node_items():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Attribute creation aborted !")
            return

        if new_name is not None:
            if new_name in node.attr_names:
                nlog.error(
                    f"An attribute with the same name already exists : {new_name}"
                )
                nlog.error("Attribute edition aborted !")
                return
            else:
                old_name = node.attr_names[index]

            # Rename in the slot item(s).
            if node.model.attributes[old_name].plug is True:
                node.plugs[old_name].model.attribute = new_name
                node.plugs[new_name] = node.plugs[old_name]
                node.plugs.pop(old_name)
                for connection in node.plugs[new_name].connections:
                    connection.plugAttr = new_name

            if node.model.attributes[old_name].socket is True:
                node.sockets[old_name].model.attribute = new_name
                node.sockets[new_name] = node.sockets[old_name]
                node.sockets.pop(old_name)
                for connection in node.sockets[new_name].connections:
                    connection.socketAttr = new_name

            node.model.sort_attributes()
            self.update()

        if isinstance(new_index, int):
            # move attribute to the new index in the model.
            alist = list(node.model.attributes.keys())
            atname = alist.pop(index)
            alist.insert(
                min(new_index if new_index >= 0 else 9999, len(alist)), atname
            )
            for i, at_name in enumerate(alist):
                node.model.attributes[at_name].index = i
            node.model.sort_attributes()

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
                        if new_name:
                            connection.plugAttr = new_name
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
                        if new_name:
                            connection.socketAttr = new_name
                        connection.updatePath()

            self.update()

        node.update()

        # Emit signal.
        if new_index:
            self.signals.AttrEdited.emit(node.model, index, new_index)
        else:
            self.signals.AttrEdited.emit(node.model, index, index)

    # GRAPH
    def save_graph(self, file_path: str) -> None:
        """
        Get all the current graph infos and store them in a .json file
        at the given location.

        Args:
            file_path (str): The path where you want to save your graph.
        """
        data = dict()

        # Store nodes data.
        data["NODES"] = dict()

        for node_name, node_item in self._node_dict.items():
            data["NODES"][node_name] = node_item.to_dict()

        # Store connections data.
        data["CONNECTIONS"] = self.evaluate_graph()

        # Save data.
        try:
            _save_data(file_path=file_path, data=data)
        except BaseException:
            raise FileNotFoundError(f"Invalid path : {file_path}")

        # Emit signal.
        self.signals.GraphSaved.emit()

    def load_graph(self, file_path: str) -> None:
        """
        Get all the stored info from the .json file at the given location
        and recreate the graph as saved.

        Args:
            file_path (str): The path of the file to load.
        """
        # Load data.
        if os.path.exists(file_path):
            data = _load_data(file_path=file_path)
        else:
            raise FileNotFoundError(f"Invalid path : {file_path}")

        # Apply nodes data.
        nodes_data = data["NODES"]

        for name, d in nodes_data.items():
            del d["name"]
            attr_dict = d.pop("attributes")
            node_item = self.create_node(
                name,
                d.pop("preset"),
                d.pop("position"),
                d.pop("alternate"),
                **d.pop("kwargs"),
            )
            for ad in attr_dict.values():
                self.create_attribute(
                    node_item,
                    name=ad.pop("attribute"),
                    index=ad.pop("index"),
                    preset=ad.pop("preset"),
                    plug=ad.pop("plug"),
                    socket=ad.pop("socket"),
                    data_type=ad.pop("data_type"),
                    plug_max_connections=ad.pop("plug_max_connections"),
                    socket_max_connections=ad.pop("socket_max_connections"),
                    **ad.pop("kwargs"),
                )

        # Apply connections data.
        connections_data = data["CONNECTIONS"]

        for connection in connections_data:
            source = connection[0]
            source_node = source.split(".")[0]
            source_attr = source.split(".")[1]

            target = connection[1]
            target_node = target.split(".")[0]
            target_attr = target.split(".")[1]

            self.create_connection(
                source_node, source_attr, target_node, target_attr
            )

        self.update()

        # Emit signal.
        self.signals.GraphLoaded.emit()

    def create_connection(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> ConnectionItem:
        """
        Create a manual connection.

        Args:
            source_node (str): Source node of the connection.
            source_attr (str): Source attribute of the connection.
            target_node (str): Target node of the connection.
            target_attr (str): Target attribute of the connection.
        """
        plug = self._node_dict[source_node].plugs[source_attr]
        socket = self._node_dict[target_node].sockets[target_attr]

        connection = self.factory.create_connection_item(
            plug.center(), socket.center(), plug, socket
        )

        connection.model.plug_node = plug.parentItem().model.name
        connection.model.plug_attr = plug.model.attribute
        connection.model.socket_node = socket.parentItem().model.name
        connection.model.socket_attr = socket.model.attribute

        plug.connect(socket, connection)
        socket.connect(plug, connection)

        connection.update_path()

        self.addItem(connection)

        return connection

    def evaluate_graph(self) -> list:
        """
        Create a list of connection tuples.
        [("sourceNode.attribute", "TargetNode.attribute"), ...]

        Returns:
            list: List of connections
        """
        data = list()
        for item in self.items():
            if isinstance(item, ConnectionItem):
                data.append(item.to_tuple())

        # Emit Signal
        self.signals.GraphEvaluated.emit()

        return data

    def clear_graph(self) -> None:
        """
        Clear the graph.
        """
        self.clear()
        # Emit signal.
        self.signals.GraphCleared.emit()

    ##################################################################
    # END API
    ##################################################################
