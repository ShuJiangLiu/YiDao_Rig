# -*- coding: utf-8 -*-
"""Select skinned models that contain any selected influence joint."""
from __future__ import print_function

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None


def _selected_joints():
    return cmds.ls(selection=True, type='joint', long=True) or []


def _long_nodes(nodes):
    result = []
    for node in nodes or []:
        matches = cmds.ls(node, long=True) or []
        result.extend(matches or [node])
    return list(dict.fromkeys(result))


def _model_transforms(geometry):
    if cmds.nodeType(geometry) == 'mesh':
        return cmds.listRelatives(
            geometry, parent=True, fullPath=True) or []
    if cmds.nodeType(geometry) == 'transform':
        return [geometry]
    return []


def _cluster_models(cluster):
    try:
        geometry = cmds.skinCluster(
            cluster, query=True, geometry=True) or []
    except Exception:
        geometry = []
    models = []
    for item in geometry:
        models.extend(_model_transforms(item))
    return _long_nodes(models)


def select_weighted_models(joints=None):
    """Select every model whose skinCluster contains a selected joint."""
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    joints = _long_nodes(joints) if joints else _selected_joints()
    joints = [joint for joint in joints
              if cmds.nodeType(joint) == 'joint']
    if not joints:
        raise RuntimeError('请先选择一个或多个权重骨骼。')
    joint_set = set(joints)
    models = []
    for cluster in cmds.ls(type='skinCluster', long=True) or []:
        try:
            influences = cmds.skinCluster(
                cluster, query=True, influence=True) or []
        except Exception:
            continue
        influences = set(_long_nodes(influences))
        if not joint_set.intersection(influences):
            continue
        for model in _cluster_models(cluster):
            if model not in models:
                models.append(model)
    if not models:
        raise RuntimeError('没有找到包含所选权重骨骼的模型。')
    cmds.select(models, replace=True)
    return joints, models
