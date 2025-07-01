from qtpy import QtWidgets

from ayon_workflow.plugin_system import register_plugins

import nodz.ay_workflow as ay_nodz


try:
    app = QtWidgets.QApplication([])
except BaseException:
    app = None

register_plugins.register_plugins()


nodz = ay_nodz.AYNodz(None)
nodz.initialize()
nodz.show()

######################################################################
# Test API
######################################################################

# Node A
nodeA = nodz.create_node("NoOp", preset="node_preset_1")
nodeB = nodz.create_node("Print", preset="node_preset_1")
nodeC = nodz.create_node("NoOp", preset="node_preset_1")
nodeD = nodz.create_node("Random Number", preset="node_preset_1")
nodeE = nodz.create_node("NoOp", preset="node_preset_1")
nodeF = nodz.create_node("Fail", name="Error !", preset="node_preset_1")

# Connection creation
nodz.create_connection(nodeA.name, "untouched_input", nodeB.name, "input_str")
nodz.create_connection(nodeA.name, "untouched_input", nodeC.name, "input")
nodz.create_connection(nodeD.name, "result", nodeA.name, "input")
nodz.create_connection(nodeC.name, "untouched_input", nodeF.name, "message")

# Nodes Edition
nodz.edit_node(node=nodeC, new_name="renamed node (noOp)")

# Nodes Deletion
nodz.delete_node(node=nodeE)


# Graph
temp_file = "temp_graph.json"
nodz.save_graph(file_path=temp_file)
nodz.clear_graph()
nodz.load_graph(file_path=temp_file)
nodz._layout_graph()

if app:
    # command line stand alone test... run our own event loop
    app.exec_()
