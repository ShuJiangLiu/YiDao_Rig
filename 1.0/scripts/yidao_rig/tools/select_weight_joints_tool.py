# -*- coding: utf-8 -*-
"""Direct command for selecting skinCluster influence joints."""
from ..core.select_weight_joints_ops import select_weight_joints

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None


def run():
    try:
        influences, skipped = select_weight_joints()
        message = '[YiDao Rig] Selected %d weight joints.' % len(influences)
        if skipped:
            message += ' Skipped %d meshes without skinCluster.' % len(skipped)
        print(message)
        return influences, skipped
    except Exception as exc:
        if cmds:
            cmds.warning(str(exc))
        return [], []
