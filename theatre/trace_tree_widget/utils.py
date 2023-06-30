# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing

if typing.TYPE_CHECKING:
    from theatre.trace_tree_widget.state_node import StateNode


def autolayout(node: "StateNode",
               align: typing.Literal['top', 'bottom', 'center'] = 'top'):
    pos = node.pos
    children: typing.Iterable["StateNode"] = node.getOutputs()
    xpos = pos.x() + node.grNode.width * 1.5
    ypos = pos.y()
    vspacing = node.grNode.height * 1.5

    if align == 'top':
        baseline = ypos
    elif align == "center":
        baseline = ypos - vspacing * len(children) / 2
    else:
        baseline = ypos - vspacing * len(children)

    for i, child in enumerate(children):
        child.setPos(xpos, baseline + vspacing * i)
        child.updateConnectedEdges()
        autolayout(child)
