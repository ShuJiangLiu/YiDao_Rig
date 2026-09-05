# -*- coding: utf-8 -*-
"""Qt interface for safe bind-pose cleanup."""
from __future__ import print_function

from ..compat.qt_compat import (
    QtWidgets, QT_WINDOW, QT_WINDOW_SYSTEM_MENU, QT_WINDOW_CLOSE,
    QT_WINDOW_MINIMIZE, QT_WINDOW_MAXIMIZE, QT_DELETE_ON_CLOSE,
)
from ..compat.maya_compat import maya_main_window
from ..core.bind_pose_ops import (
    cleanup_and_merge_bind_poses, inspect_bind_poses, undo_chunk)
from ..core.ui_state import setup_state

WINDOW_OBJECT = 'yidaoBindPoseWindow'
_STYLE = '''
QDialog { background: #202020; color: #e8e8e8; }
QLabel { color: #cfcfcf; }
QGroupBox { border: 1px solid #3c3c3c; border-radius: 5px; margin-top: 8px; padding: 8px 6px 6px 6px; font-weight: bold; color: #e0e0e0; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QPushButton { background: #353535; border: 1px solid #4d4d4d; border-radius: 3px; padding: 5px 10px; min-height: 28px; color: #ededed; }
QPushButton:hover { background: #454545; border-color: #6b9dcc; }
QPushButton:pressed { background: #2a2a2a; }
QLabel#hintLabel { color: #a9a9a9; font-size: 11px; }
QLabel#statusLabel { color: #ffffff; padding: 3px 2px; }
QLabel#statusLabel[error="true"] { color: #ff6b6b; }
'''


if QtWidgets:
    class BindPoseWindow(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName(WINDOW_OBJECT)
            self.setWindowTitle('Bind Pose Cleanup')
            self.setMinimumSize(500, 170)
            self.setStyleSheet(_STYLE)
            self._build_ui()
            self._save_ui_state = setup_state(self, 'bind_pose')

        def _build_ui(self):
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)
            action_group = QtWidgets.QGroupBox('操作')
            action_layout = QtWidgets.QVBoxLayout(action_group)
            action_layout.setContentsMargins(8, 8, 8, 8)
            scan_button = QtWidgets.QPushButton('检查 Bind Pose')
            cleanup_button = QtWidgets.QPushButton('清理 Bind Pose')
            scan_button.clicked.connect(self._inspect)
            cleanup_button.clicked.connect(self._cleanup)
            action_layout.addWidget(scan_button)
            action_layout.addWidget(cleanup_button)
            root.addWidget(action_group)

            self.status = QtWidgets.QLabel('就绪：可以检查场景中的 Bind Pose')
            self.status.setObjectName('statusLabel')
            root.addWidget(self.status)

        def _set_status(self, text, error=False):
            self.status.setProperty('error', 'true' if error else 'false')
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.status.setText(text)

        def _inspect(self):
            try:
                info = inspect_bind_poses()
                self._set_status(
                    '检查完成：共 %d 个 Bind Pose，其中 %d 个与当前 skinCluster 关联。' %
                    (len(info['all']), len(info['used'])))
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True)

        def _cleanup(self):
            try:
                with undo_chunk('YiDao Bind Pose Cleanup'):
                    result = cleanup_and_merge_bind_poses()
                unused_count = len(result['removed_unused'])
                merged_count = len(result['removed_duplicates'])
                remaining_count = len(result['remaining'])
                if remaining_count > 1:
                    message = (
                        '已清理 %d 个无用节点并合并 %d 个 Bind Pose；仍保留 %d 个，'
                        '未满足安全合并条件。' %
                        (unused_count, merged_count, remaining_count))
                else:
                    message = (
                        '完成：已清理 %d 个无用节点并合并 %d 个 Bind Pose，当前保留 %d 个。' %
                        (unused_count, merged_count, remaining_count))
                if result['unreadable']:
                    message += ' 有 %d 个节点数据无法读取，已保留。' % len(result['unreadable'])
                if result['not_at_pose']:
                    message += ' 有 %d 个节点当前不在 Bind Pose，已保留。' % len(result['not_at_pose'])
                self._set_status(message)
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True)
else:
    BindPoseWindow = None


def show():
    if not QtWidgets:
        raise RuntimeError('无法导入 PySide2/PySide6；请在 Maya 2022-2026 中运行。')
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT:
            widget.close()
            widget.deleteLater()
    window = BindPoseWindow(parent=maya_main_window())
    window.setWindowFlags(QT_WINDOW | QT_WINDOW_SYSTEM_MENU | QT_WINDOW_CLOSE |
                          QT_WINDOW_MINIMIZE | QT_WINDOW_MAXIMIZE)
    window.setAttribute(QT_DELETE_ON_CLOSE, True)
    window.showNormal()
    window.raise_()
    window.activateWindow()
    return window
