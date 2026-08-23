# -*- coding: utf-8 -*-
"""Select the influence joints used by the selected skinned meshes."""
from __future__ import print_function

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None


def _selected_meshes():
    meshes = []
    for node in cmds.ls(selection=True, long=True) or []:
        if cmds.nodeType(node) == 'mesh':
            meshes.append(node)
        else:
            meshes.extend(cmds.listRelatives(
                node, shapes=True, noIntermediate=True,
                type='mesh', fullPath=True) or [])
    return list(dict.fromkeys(meshes))


def _skin_clusters(mesh):
    history = cmds.listHistory(mesh, pruneDagObjects=True) or []
    return [node for node in history if cmds.nodeType(node) == 'skinCluster']


def _long_influence(name):
    matches = cmds.ls(name, long=True) or []
    return matches[0] if matches else name


def select_weight_joints(meshes=None):
    """Select all influence objects in the selected meshes' skinClusters."""
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    meshes = meshes or _selected_meshes()
    if not meshes:
        raise RuntimeError('请先选择一个带有 skinCluster 的模型。')
    influences = []
    skipped = []
    for mesh in meshes:
        clusters = _skin_clusters(mesh)
        if not clusters:
            skipped.append(mesh)
            continue
        for cluster in clusters:
            for influence in cmds.skinCluster(
                    cluster, query=True, influence=True) or []:
                influence = _long_influence(influence)
                if influence not in influences:
                    influences.append(influence)
    if not influences:
        raise RuntimeError('所选模型没有找到 skinCluster 或权重骨骼。')
    cmds.select(influences, replace=True)
    return influences, skipped
