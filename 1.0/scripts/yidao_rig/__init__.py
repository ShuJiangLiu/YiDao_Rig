# -*- coding: utf-8 -*-
"""YiDao Rig Maya package."""

__version__ = '1.0.0'


def show_controller_tool():
    from .tools import controller_tool
    return controller_tool.show()


def show_mirror_joints():
    from .tools import mirror_joints_tool
    return mirror_joints_tool.run()


def show_attribute_cleanup():
    from .tools import attribute_cleanup_tool
    return attribute_cleanup_tool.run()


def show_attribute_connection():
    from .tools import attribute_connection_tool
    return attribute_connection_tool.run()


def show_joint_match():
    from .tools import joint_match_tool
    return joint_match_tool.run()


def show_skin_weight_tool():
    from .tools import skin_weight_tool
    return skin_weight_tool.run()


def show_select_weight_joints():
    from .tools import select_weight_joints_tool
    return select_weight_joints_tool.run()


def show_naming():
    from .tools import naming_tool
    return naming_tool.run()


def reload_all_tools():
    from .launcher import reload_all_tools as _reload_all_tools
    return _reload_all_tools()


# Compatibility alias retained for existing shelf buttons and scripts.
def reload_controller_tool():
    return reload_all_tools()
