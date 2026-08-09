# -*- coding: utf-8 -*-
"""Optional Maya startup hook for YiDao Rig.

This file intentionally does not open a window automatically. It only makes
the launcher available after Maya starts.
"""
from __future__ import print_function

try:
    import yidao_rig
    print('[YiDao Rig] Ready. Run yidao_rig.show_controller_tool()')
except Exception as exc:
    print('[YiDao Rig] Startup import skipped: %s' % exc)
