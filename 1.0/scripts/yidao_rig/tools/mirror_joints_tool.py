# -*- coding: utf-8 -*-
"""Backward-compatible Mirror Joints entry point."""
from ..core.joint_mirror_ops import mirror_joints, mirror_selected
from ..ui.mirror_joints_window import MirrorJointsWindow, run

__all__ = ['mirror_joints', 'mirror_selected', 'MirrorJointsWindow', 'run']
