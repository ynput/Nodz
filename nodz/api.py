from typing import Any, Optional
from functools import partial
from enum import Flag, auto
from copy import deepcopy
from .data_types import (
    ModelEntity,
    ModelEdit,
    AttrModel,
    NodeModel,
    ConnectionModel,
    GraphModel,
    NodzAdapter,
)
from .scene import NodeScene
from .utils import nlog
from qtpy import QtCore


class CoreAPI:
    def __init__(self, view, scene: NodeScene) -> None:
        self.view = view
        self.scene = scene

    def load_config(self, file_path: str) -> None:
        self.scene.api_load_config(file_path)

    def create_node(
        self,
        name: str = "default",
        preset: str = "node_default",
        position: Optional[QtCore.QPointF] = None,
        alternate: bool = True,
        **kwargs,
    ) -> str:
        return self.scene.create_node(
            name, preset, position, alternate, **kwargs
        ).model.name

    def delete_node(self, node_name: str) -> None:
        self.scene.delete_node(self.scene.node_by_name(node_name))

    def edit_node(self, node_name: str, new_name: str) -> str:
        node = self.scene.node_by_name(node_name)
        self.scene.rename_node(node, new_name)
        return node.model.name

    def create_attribute(
        self,
        node_name: str,
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
        self.scene.create_attribute(
            self.scene.node_by_name(node_name),
            name,
            index,
            preset,
            plug,
            socket,
            data_type,
            plug_max_connections,
            socket_max_connections,
            **kwargs,
        )

    def delete_attribute(self, node_name: str, attr_name: str) -> None:
        self.scene.delete_attribute(
            self.scene.node_by_name(node_name), attr_name
        )

    def edit_attribute(
        self,
        node_name: str,
        index: int,
        new_name: Optional[str] = None,
        new_index: Optional[int] = None,
    ) -> None:
        self.scene.edit_attribute(
            self.scene.node_by_name(node_name), index, new_name, new_index
        )

    def save_graph(self, file_path: str) -> None:
        self.scene.save_graph(file_path)

    def load_graph(self, file_path: str) -> None:
        self.scene.load_graph(file_path)

    def create_connection(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> None:
        self.scene.create_connection(
            source_node, source_attr, target_node, target_attr
        )

    def evaluate_graph(self) -> list:
        return self.scene.evaluate_graph()

    def clear_graph(self):
        self.scene.clear_graph()


class Diff(Flag):
    Same = auto()
    Created = auto()
    Deleted = auto()
    Updated = auto()
    PositionChanged = auto()
    AttributesChanged = auto()


class ModelAPI:
    def __init__(
        self, view, scene: NodeScene, adapter: Optional[NodzAdapter] = None
    ) -> None:
        self.view = view
        self.scene = scene
        self.adapter = adapter
        self.graph = GraphModel()
        self._reference_graph = deepcopy(self.graph)

        if self.adapter:
            # connect signals
            self.scene.signals.PlugConnected.connect(
                partial(
                    self.update_model, ModelEntity.Connection, ModelEdit.Create
                )
            )
            self.scene.signals.PlugDisconnected.connect(
                partial(
                    self.update_model, ModelEntity.Connection, ModelEdit.Delete
                )
            )
            self.scene.signals.NodeCreated.connect(
                partial(self.update_model, ModelEntity.Node, ModelEdit.Create)
            )
            self.scene.signals.NodeDeleted.connect(
                partial(self.update_model, ModelEntity.Node, ModelEdit.Delete)
            )
            self.scene.signals.NodeRenamed.connect(
                partial(self.update_model, ModelEntity.Node, ModelEdit.Update)
            )
            self.scene.signals.NodeMoved.connect(
                partial(
                    self.update_model, ModelEntity.Node, ModelEdit.Position
                )
            )
            self.scene.signals.AttrCreated.connect(
                partial(self.update_model, ModelEntity.Node, ModelEdit.Update)
            )
            self.scene.signals.AttrDeleted.connect(
                partial(self.update_model, ModelEntity.Node, ModelEdit.Update)
            )
            self.scene.signals.AttrEdited.connect(
                partial(self.update_model, ModelEntity.Node, ModelEdit.Update)
            )
            self.scene.signals.NodeLayoutChanged.connect(
                partial(self.update_model, ModelEntity.Graph, ModelEdit.Layout)
            )

    @property
    def reference_graph(self):
        return self._reference_graph

    @reference_graph.setter
    def reference_graph(self, value):
        self._reference_graph = deepcopy(value)

    def _diff_graph(self, new_graph: GraphModel) -> dict[str, list]:
        """Compare two GraphModel objects and return a list of differences."""

        diffs = {"nodes": [], "connections": []}

        # Compare nodes
        for node_id, node1 in self.reference_graph.nodes.items():
            if node_id not in new_graph.nodes:
                diffs["nodes"].append((Diff.Deleted, node_id))
            else:
                node2 = new_graph.nodes[node_id]
                if node1 != node2:
                    status = Diff.Updated
                    if node1.position != node2.position:
                        nlog.debug(
                            f"   >  diff: {node2.name} position changed."
                        )
                        status |= Diff.PositionChanged
                    if node1.attributes != node2.attributes:
                        nlog.debug(
                            f"   >  diff: {node2.name} attributes changed."
                        )
                        status |= Diff.AttributesChanged
                    diffs["nodes"].append((status, node_id))

        for node_id in new_graph.nodes:
            if node_id not in self.reference_graph.nodes:
                diffs["nodes"].append((Diff.Created, node_id))

        # Compare connections
        for con in self.reference_graph.connections:
            if con not in new_graph.connections:
                diffs["connections"].append((Diff.Deleted, con))

        for con in new_graph.connections:
            if con not in self.reference_graph.connections:
                diffs["connections"].append((Diff.Created, con))

        return diffs

    def update_view(
        self,
        client_data: Any,
        entity: ModelEntity = ModelEntity.Graph,
        edit: ModelEdit = ModelEdit.Update,
    ):
        # Build a model corresponding on the requested entity type.
        if entity == ModelEntity.Attr:
            nodz_model = self.adapter.to_attr_model(client_data)
        elif entity == ModelEntity.Node:
            nodz_model = self.adapter.to_node_model(client_data)
        elif entity == ModelEntity.Connection:
            nodz_model = self.adapter.to_connecttion_model(client_data)
        elif entity == ModelEntity.Graph:
            nodz_model = self.adapter.to_graph_model(client_data)

        self.scene.signals.blockSignals(True)

        # Send an edit to the graph
        if isinstance(nodz_model, NodeModel):
            if edit == ModelEdit.Create:
                self._create_node_from_model(nodz_model)
            elif edit == ModelEdit.Update:
                self._update_node_from_model(nodz_model, Diff.Updated)
            elif edit == ModelEdit.Delete:
                self._delete_node_from_model(nodz_model.name)
            elif edit == ModelEdit.Position:
                self.scene.node_by_name(nodz_model.name).setPos(
                    nodz_model.position
                )

        elif isinstance(nodz_model, AttrModel):
            if edit == ModelEdit.Create:
                raise NotImplementedError
            elif edit == ModelEdit.Update:
                raise NotImplementedError
            elif edit == ModelEdit.Delete:
                raise NotImplementedError

        elif isinstance(nodz_model, ConnectionModel):
            if edit == ModelEdit.Create:
                self._create_connection_from_model(nodz_model)
            elif edit == ModelEdit.Update:
                raise NotImplementedError(
                    "Updating connections is NOT supported."
                )
            elif edit == ModelEdit.Delete:
                self._delete_connection_from_model(nodz_model)

        elif isinstance(nodz_model, GraphModel):
            if edit == ModelEdit.Create:
                for node in nodz_model.nodes.values():
                    self._create_node_from_model(node)
                for con in nodz_model.connections:
                    self._create_connection_from_model(con)
            elif edit == ModelEdit.Update:
                # nlog.info(">  update graph")
                changes = self._diff_graph(nodz_model)  # diff models
                for diff, id in changes["nodes"]:
                    if Diff.Created in diff:
                        self._create_node_from_model(nodz_model.nodes[id])
                    elif Diff.Updated in diff:
                        self._update_node_from_model(
                            nodz_model.nodes[id], diff
                        )
                    elif Diff.Deleted in diff:
                        self._delete_node_from_model(id)
                for diff, con in changes["connections"]:
                    if diff == Diff.Created:
                        self._create_connection_from_model(con)
                    elif diff == Diff.Deleted:
                        self._delete_connection_from_model(con)
            elif edit == ModelEdit.Delete:
                nodz_model = GraphModel()
                self.view.api.clear_graph()
            # keep a copy for next diff.
            self.reference_graph = deepcopy(nodz_model)

        self.scene.signals.blockSignals(False)

    def _create_node_from_model(self, model: NodeModel) -> None:
        # Check for name clashes
        if model.name in self.scene.node_names():
            raise NameError(
                f"A node with the same name already exists: {model.name}"
            )
        node_item = self.scene.factory.create_node_item(
            model, self.scene.config
        )
        self.scene.add_node(node_item, position=model.position)
        for attr in model.attributes.values():
            node_item._create_attribute(
                attr.attribute,
                attr.index,
                attr.preset,
                attr.plug,
                attr.socket,
                attr.data_type,
                attr.plug_max_connections,
                attr.socket_max_connections,
                **attr.kwargs,
            )
        node_item.update()

    def _update_node_from_model(self, model: NodeModel, diff: Diff) -> None:
        if model.name not in self.scene.node_names():
            raise NameError(f"Updatable node doesn't exist: {model.name}")
        # store current pos and connections to this node.
        pos = self.scene.node_by_name(model.name).pos()
        cons = [
            c
            for c in self.scene.evaluate_graph()
            if any([cc.startswith(f"{model.name}.") for cc in c])
        ]
        self._delete_node_from_model(model.name)
        self._create_node_from_model(model)
        node_item = self.scene.node_by_name(model.name)
        node_item.setPos(pos)
        for src, dst in cons:
            self.scene.create_connection(*src.split("."), *dst.split("."))
        self.scene.update()

    def _delete_node_from_model(self, node_id: str) -> None:
        if node_id not in self.scene.node_names():
            raise NameError(f"Deletable node doesn't exist: {node_id}")
        node_item = self.scene.node_by_name(node_id)
        node_item._remove_connections()
        self.scene.removeItem(node_item)
        self.scene.update()

    def _create_connection_from_model(self, model: ConnectionModel) -> None:
        self.scene.create_connection(
            model.plug_node,
            model.plug_attr,
            model.socket_node,
            model.socket_attr,
        )

    def _delete_connection_from_model(self, model: ConnectionModel) -> None:
        plug_item = self.scene.node_by_name(model.plug_node)
        socket_item = self.scene.node_by_name(model.socket_node)

        if model.plug_attr in plug_item.plugs.keys():
            con_item = plug_item.plugs[model.plug_attr]
            for con in con_item.connections:
                con._remove()
            self.scene.removeItem(con_item)
            plug_item.plugs.pop(model.plug_attr)
            plug_item.update()

        if model.socket_attr in socket_item.sockets.keys():
            con_item = socket_item.sockets[model.socket_attr]
            for con in con_item.connections:
                con._remove()
            self.scene.removeItem(con_item)
            socket_item.sockets.pop(model.socket_attr)
            socket_item.update()

    def select_node(
        self, node_name: str, state: bool, clear_selection=True
    ) -> None:
        node_item = self.scene.node_by_name(node_name)
        if clear_selection:
            for item in self.scene.selectedItems():
                item.setSelected(False)
        node_item.setSelected(state)

    def load_graph(self, file_path: str) -> None:
        self.scene.signals.blockSignals(True)
        self.scene.load_graph(file_path)
        self.scene.signals.blockSignals(False)

    def update_model(
        self, entity: ModelEntity, edit: ModelEdit, *data
    ) -> None:
        # get a fresh copy of the client's data
        client_model = self.adapter.to_graph_model(self.adapter.client_model)

        if entity == ModelEntity.Connection:
            con_model = data[0]

            if edit == ModelEdit.Create:
                nlog.debug(f"update_model:  Create CON {con_model}")
                client_model.add_connection(con_model)
                self.adapter.from_graph_model(client_model)

            elif edit == ModelEdit.Delete:
                nlog.debug(f"update_model:  Delete CON {con_model}")
                try:
                    idx = client_model.connections.index(con_model)
                except ValueError:
                    nlog.warning(f"Ignoring unknown: {con_model}")
                    return
                client_model.connections.pop(idx)
                self.adapter.from_graph_model(client_model)

        elif entity == ModelEntity.Node:
            if edit == ModelEdit.Create:
                node_model = data[0]
                nlog.debug(f"update_model:  Create NODE {node_model}")
                client_model.nodes[node_model.name] = node_model
                self.adapter.from_graph_model(client_model)

            elif edit == ModelEdit.Update:
                nlog.debug(f"update_model:  Update NODE {data}")
                nargs = len(data)
                if nargs == 2:
                    if isinstance(data[0], str) and isinstance(data[1], str):
                        client_model.rename_node(*data)
                    elif isinstance(data[0], NodeModel) and isinstance(
                        data[1], str
                    ):
                        client_model.nodes[data[1]] = data[0]
                    else:
                        nlog.warning(f"Unimplemented node update: {data}")
                self.adapter.from_graph_model(client_model)

            elif edit == ModelEdit.Delete:
                nlog.debug(f"update_model:  Delete NODE {data}")
                if len(data) == 1 and isinstance(data[0], str):
                    client_model.nodes.pop(data[0])
                else:
                    raise ValueError(f"Unexpected data: {data}")
                self.adapter.from_graph_model(client_model)

            elif edit == ModelEdit.Position:
                nlog.debug(f"update_model:  Position NODE {data}")
                model, pos = data
                client_model.nodes[model.name].position = pos

        elif entity == ModelEntity.Graph:
            if edit == ModelEdit.Create:
                pass
            elif edit == ModelEdit.Update:
                pass
            elif edit == ModelEdit.Delete:
                pass
            elif edit == ModelEdit.Layout:
                for node_name, pos in data[0].items():
                    client_model.nodes[node_name].position = pos
                self.adapter.from_graph_model(client_model)
