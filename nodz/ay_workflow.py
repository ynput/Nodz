""" AYON workflow based nodes.
"""
import os

from typing import Any, Optional

from qtpy import QtCore

from ayon_workflow.graph_editor.graph import Graph
from ayon_workflow.graph_editor.node import Node, NodeConnection
from ayon_workflow.plugin_system.register_plugins import (
    PluginRegistry
)

import nodz.core as core


class AYNodeItem(core.NodeItem):
    """ core.NodeItem for ayon_workflow interface.
    """

    def __init__(
        self,
        name: str,
        alternate: bool,
        preset: str,
        config: dict,
        py_node: Optional[Node] = str,
    ) -> None:
        super().__init__(
            name,
            alternate,
            preset,
            config,
        )
        self.py_node = py_node

class AYNodz(core.Nodz):
    """ Nodz interface for ayon_workflow.
    """

    def __init__(
        self,
        parent: Any,
        config_path: Optional[str] = None,
        nodeitem_cls: core.NodeItem = AYNodeItem,
        slotitem_cls: core.SlotItem = core.SlotItem,
        plugitem_cls: core.PlugItem = core.PlugItem,
        socketitem_cls: core.SocketItem = core.SocketItem,
        connectionitem_cls: core.ConnectionItem = core.ConnectionItem,
    ):
        self._py_graph = Graph(name="underlying_graph")
        self._plg_list = PluginRegistry().plugin_list()

        super().__init__(
            parent=parent,
            config_path=config_path or core.DEFAULT_CONFIG_PATH,
            nodeitem_cls=nodeitem_cls,
            slotitem_cls=slotitem_cls,
            plugitem_cls=plugitem_cls,
            socketitem_cls=socketitem_cls,
            connectionitem_cls=connectionitem_cls,
        )

    def create_node(
        self,
        node_type: str,
        name: Optional[str] = None,
        preset: str = "node_default",
        position: Optional[QtCore.QPointF] = None,
        alternate: bool = True,
    ) -> AYNodeItem:

        # Create underlying python node.
        py_node = self._py_graph.create_node(node_type, label=name)
        plugin_desc = self._plg_list[node_type]

        node_item = super().create_node(
            py_node.display_name,
            preset=preset,
            position=position,
            alternate=alternate,
        )
        node_item.py_node = py_node

        # Create inputs
        for plg_input in plugin_desc.inputs:
            self.create_attribute(
                node=node_item,
                name=plg_input["name"],
                index=-1,
                preset="attr_preset_1",
                plug=False,
                socket=True,
                data_type=plg_input["type"],
            )

        # Create outputs
        for plg_output in plugin_desc.outputs:
            self.create_attribute(
                node=node_item,
                name=plg_output["name"],
                index=-1,
                preset="attr_preset_3",
                plug=True,
                socket=False,
                data_type=plg_output["type"],
            )

        return node_item

    def delete_node(self, node: AYNodeItem) -> None:
        self._py_graph.delete_node(node.py_node)
        super().delete_node(node)

    def create_connection(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> core.ConnectionItem:
        source_node_item = self.scene_nodes[source_node]
        target_node_item = self.scene_nodes[target_node]

        source_node_item.py_node.connect(
            source_attr,
            target_node_item.py_node,
            target_attr,
        )
        super().create_connection(
            source_node,
            source_attr,
            target_node,
            target_attr,
        )

    def delete_attribute(self, node: AYNodeItem, index: int) -> None:
        raise NotImplementedError("Should not be called directly.")

    def edit_attribute(
        self,
        node: AYNodeItem,
        index: int,
        new_name: Optional[str] = None,
        new_index: Optional[int] = None,
    ) -> None:
        raise NotImplementedError("Should not be called directly.")

    def edit_node(self, node, new_name: Optional[str] = None) -> None:
        if new_name:
            node.py_node.label = new_name

        super().edit_node(node, new_name=new_name)

    def save_graph(self, file_path: str = "path") -> None:
        self._py_graph.export_to_file(file_path)
        self.signal_GraphSaved.emit()

    def load_graph(self, file_path: str = "path") -> None:
        """
        Get all the stored info from the .json file at the given location
        and recreate the graph as saved.

        Args:
            file_path (str): The path of the file to load.
        """
        # Load data.
        if os.path.exists(file_path):
            graph = Graph.import_from_file(file_path)
        else:
            raise FileNotFoundError(f"Invalid path : {file_path}")

        # Create all nodes
        created_nodes_names = {}
        for node in graph.get_nodes():
            nodeitem = self.create_node(node.plugin_ref.name, node.display_name)
            created_nodes_names[node.name] = nodeitem.name

        # Restore all connections
        for node in graph.get_nodes():
            for input_name, node_connect in node.input_connections.items():
                if not isinstance(node_connect, NodeConnection):
                    continue

                self.create_connection(
                    created_nodes_names[node_connect.origin_node_name],
                    node_connect.origin_node_output,
                    created_nodes_names[node.name],
                    input_name,
                )

        self.scene().update()
        self.signal_GraphLoaded.emit()
