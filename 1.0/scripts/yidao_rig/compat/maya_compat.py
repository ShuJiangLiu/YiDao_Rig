# -*- coding: utf-8 -*-
"""Maya API compatibility helpers."""
from __future__ import annotations

try:
    import maya.cmds as cmds
    import maya.OpenMayaUI as omui
except ImportError:
    cmds = omui = None

from .qt_compat import QtWidgets, wrapInstance


def maya_version():
    if not cmds:
        return None
    try:
        return int(str(cmds.about(version=True)).split('.')[0])
    except Exception:
        return None


def maya_version_string():
    if not cmds:
        return 'Outside Maya'
    try:
        return str(cmds.about(version=True))
    except Exception:
        return 'Unknown'


def display_node(node):
    """Show a short name when unique, otherwise the full DAG path."""
    if not node:
        return node
    text = str(node)
    if not cmds:
        return text
    try:
        full = (cmds.ls(text, long=True) or [text])[0]
        short = full.rsplit('|', 1)[-1]
        candidates = cmds.ls(short, long=True) or []
        return short if len(candidates) == 1 else full
    except Exception:
        return text


def display_plug(plug):
    """Format node.attribute using the same unique-name rule."""
    if not plug or '.' not in str(plug):
        return display_node(plug)
    node, attribute = str(plug).rsplit('.', 1)
    return display_node(node) + '.' + attribute


def maya_main_window():
    if not omui or not wrapInstance or not QtWidgets:
        return None
    pointer = omui.MQtUtil.mainWindow()
    if not pointer:
        return None
    return wrapInstance(int(pointer), QtWidgets.QWidget)
