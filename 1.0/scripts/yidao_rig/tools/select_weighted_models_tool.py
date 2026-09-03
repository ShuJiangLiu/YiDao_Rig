# -*- coding: utf-8 -*-
"""Direct command for selecting models by influence joints."""
from ..core.select_weighted_models_ops import select_weighted_models

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None


def run():
    try:
        joints, models = select_weighted_models()
        print('[YiDao Rig] 已根据 %d 个权重骨骼选中 %d 个模型。' %
              (len(joints), len(models)))
        return joints, models
    except Exception as exc:
        if cmds:
            cmds.warning(str(exc))
        return [], []
