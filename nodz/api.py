from typing import Any, Optional
from functools import partial
from enum import Enum
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

from functools import wraps
import time


def timeit(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        nlog.debug(f"Function {func.__name__} Took {total_time:.4f} seconds")
        return result

    return timeit_wrapper


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


class Diff(Enum):
    Same = 0
    Created = 1
    Deleted = 2
    Updated = 3


class ModelAPI:
    def __init__(self, view, scene: NodeScene, adapter: NodzAdapter) -> None:
        self.view = view
        self.scene = scene
        self.adapter = adapter
        self.graph = GraphModel()
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
            partial(self.update_model, ModelEntity.Node, ModelEdit.Update)
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

    @timeit
    def diff_graph(self, new_graph: GraphModel) -> dict[str, list]:
        """Compare two GraphModel objects and return a list of differences."""

        diffs = {"nodes": [], "connections": []}

        # Compare nodes
        for node_id, node1 in self.graph.nodes.items():
            if node_id not in new_graph.nodes:
                diffs["nodes"].append((Diff.Deleted, node_id))
            else:
                node2 = new_graph.nodes[node_id]
                if node1 != node2:
                    diffs["nodes"].append((Diff.Updated, node_id))

        for node_id in new_graph.nodes:
            if node_id not in self.graph.nodes:
                diffs["nodes"].append((Diff.Created, node_id))

        # Compare connections
        for con in self.graph.connections:
            if con not in new_graph.connections:
                diffs["connections"].append((Diff.Deleted, con))

        for con in new_graph.connections:
            if con not in self.graph.connections:
                diffs["connections"].append((Diff.Created, con))

        # print(f">>  diff: {diffs}")
        return diffs

    @timeit
    def update_view(
        self,
        data: Any,
        entity: ModelEntity = ModelEntity.Graph,
        edit: ModelEdit = ModelEdit.Update,
    ):
        # Build a model corresponding on the requested entity type.
        if entity == ModelEntity.Attr:
            model = self.adapter.to_attr_model(data)
        elif entity == ModelEntity.Node:
            model = self.adapter.to_node_model(data)
        elif entity == ModelEntity.Connection:
            model = self.adapter.to_connecttion_model(data)
        elif entity == ModelEntity.Graph:
            model = self.adapter.to_graph_model(data)

        self.scene.signals.blockSignals(True)

        # Send an edit to the graph
        if isinstance(model, NodeModel):
            if edit == ModelEdit.Create:
                self.create_node_from_model(model)
            elif edit == ModelEdit.Update:
                self.update_node_from_model(model)
            elif edit == ModelEdit.Delete:
                self.delete_node_from_model(model.name)
        elif isinstance(model, AttrModel):
            if edit == ModelEdit.Create:
                raise NotImplementedError
            elif edit == ModelEdit.Update:
                raise NotImplementedError
            elif edit == ModelEdit.Delete:
                raise NotImplementedError
        elif isinstance(model, ConnectionModel):
            if edit == ModelEdit.Create:
                self.create_connection_from_model(model)
            elif edit == ModelEdit.Update:
                raise NotImplementedError
            elif edit == ModelEdit.Delete:
                self.delete_connection_from_model(model)
        elif isinstance(model, GraphModel):
            if edit == ModelEdit.Create:
                for node in model.nodes.values():
                    self.create_node_from_model(node)
                for con in model.connections:
                    self.create_connection_from_model(con)
            elif edit == ModelEdit.Update:
                changes = self.diff_graph(model)
                for diff, id in changes["nodes"]:
                    if diff == Diff.Created:
                        self.create_node_from_model(model.nodes[id])
                    elif diff == Diff.Updated:
                        self.update_node_from_model(model.nodes[id])
                    else:
                        self.delete_node_from_model(id)
                for diff, con in changes["connections"]:
                    if diff == Diff.Created:
                        self.create_connection_from_model(con)
                    elif diff == Diff.Deleted:
                        pass
            elif edit == ModelEdit.Delete:
                model = GraphModel()
            # keep a copy for next diff.
            self.graph = deepcopy(model)

        self.scene.signals.blockSignals(False)

    def create_node_from_model(self, model: NodeModel) -> None:
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

    def update_node_from_model(self, model: NodeModel) -> None:
        if model.name not in self.scene.node_names():
            raise NameError(f"Updatable node doesn't exist: {model.name}")
        pos = self.scene.node_by_name(model.name).pos()
        cons = self.scene.evaluate_graph()
        self.delete_node_from_model(model.name)
        self.create_node_from_model(model)
        node_item = self.scene.node_by_name(model.name)
        node_item.setPos(pos)
        for src, dst in cons:
            self.scene.create_connection(*src.split("."), *dst.split("."))
        self.scene.update()

    def delete_node_from_model(self, node_id: str) -> None:
        if node_id not in self.scene.node_names():
            raise NameError(f"Deletable node doesn't exist: {node_id}")
        node_item = self.scene.node_by_name(node_id)
        node_item._remove_connections()
        self.scene.removeItem(node_item)
        self.scene.update()

    def create_connection_from_model(self, model: ConnectionModel) -> None:
        self.scene.create_connection(
            model.plug_node,
            model.plug_attr,
            model.socket_node,
            model.socket_attr,
        )

    def delete_connection_from_model(self, model: ConnectionModel) -> None:
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

    def select_node(self, node_name: str, state: bool) -> None:
        node_item = self.scene.node_by_name(node_name)
        node_item.setSelected(state)

    def load_graph(self, file_path: str) -> None:
        self.scene.signals.blockSignals(True)
        self.scene.load_graph(file_path)
        self.scene.signals.blockSignals(False)

    def update_model(self, entity: ModelEntity, edit: ModelEdit, *data):
        if entity == ModelEntity.Connection:
            con_model = data[0]

            if edit == ModelEdit.Create:
                nlog.debug(f"update_model:  Create CON {con_model}")
                self.graph.connections.append(con_model)
                self.adapter.from_graph_model(self.graph)

            elif edit == ModelEdit.Delete:
                nlog.debug(f"update_model:  Delete CON {con_model}")
                try:
                    idx = self.graph.connections.index(con_model)
                except ValueError:
                    nlog.warning(f"Ignoring unknown: {con_model}")
                    return
                self.graph.connections.pop(idx)
                self.adapter.from_graph_model(self.graph)

        elif entity == ModelEntity.Node:
            if edit == ModelEdit.Create:
                node_model = data[0]
                nlog.debug(f"update_model:  Create NODE {node_model}")
                self.graph.nodes[node_model.name] = node_model
                self.adapter.from_graph_model(self.graph)

            elif edit == ModelEdit.Update:
                nlog.debug(f"update_model:  Update NODE {data}")
                nargs = len(data)
                if nargs == 2:
                    if isinstance(data[0], str) and isinstance(data[1], str):
                        self.graph.rename_node(*data)
                self.adapter.from_graph_model(self.graph)

            elif edit == ModelEdit.Delete:
                nlog.debug(f"update_model:  Delete NODE {data}")
                # IMPLEMENT ME
                self.adapter.from_graph_model(self.graph)
