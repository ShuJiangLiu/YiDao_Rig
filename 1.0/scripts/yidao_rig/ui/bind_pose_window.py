# -*- coding: utf-8 -*-
"""Qt interface for safe bind-pose cleanup."""
from __future__ import print_function

from ..compat.qt_compat import (
    QtWidgets, QT_WINDOW, QT_WINDOW_SYSTEM_MENU, QT_WINDOW_CLOSE,
    QT_WINDOW_MINIMIZE, QT_WINDOW_MAXIMIZE, QT_DELETE_ON_CLOSE,
)
from ..compat.maya_compat import maya_main_window
from ..core.bind_pose_ops import (
    cleanup_and_merge_bind_poses, cleanup_unused_bind_poses,
    inspect_bind_poses, undo_chunk)
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
            self.setMinimumSize(500, 280)
            self.setStyleSheet(_STYLE)
            self._build_ui()
            self._save_ui_state = setup_state(self, 'bind_pose')

        def _build_ui(self):
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)
            info = QtWidgets.QLabel(
                '清理场景中可以确认未被当前 skinCluster 使用的 Bind Pose 节点。\n'
                '“清理并合并”只处理骨骼成员兼容且共同矩阵一致的 Bind Pose。')
            info.setWordWrap(True)
            root.addWidget(info)

            action_group = QtWidgets.QGroupBox('清理操作')
            action_layout = QtWidgets.QVBoxLayout(action_group)
            action_layout.setContentsMargins(8, 8, 8, 8)
            scan_button = QtWidgets.QPushButton('检查 Bind Pose')
            cleanup_button = QtWidgets.QPushButton('清理无用 Bind Pose')
            merge_button = QtWidgets.QPushButton('清理并合并相同 Bind Pose')
            scan_button.clicked.connect(self._inspect)
            cleanup_button.clicked.connect(self._cleanup)
            merge_button.clicked.connect(self._cleanup_and_merge)
            action_layout.addWidget(scan_button)
            action_layout.addWidget(cleanup_button)
            action_layout.addWidget(merge_button)
            root.addWidget(action_group)

            hint = QtWidgets.QLabel(
                '如果清理后仍有多个有效 Bind Pose，说明它们可能分别服务于不同绑定关系。')
            hint.setObjectName('hintLabel')
            hint.setWordWrap(True)
            root.addWidget(hint)

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
                    '检查完成：共 %d 个，使用中 %d 个，可清理 %d 个。' %
                    (len(info['all']), len(info['used']), len(info['unused'])))
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True)

        def _cleanup(self):
            try:
                with undo_chunk('YiDao Bind Pose Cleanup'):
                    result = cleanup_unused_bind_poses()
                removed_count = len(result['removed'])
                remaining_count = len(result['remaining'])
                if remaining_count > 1:
                    message = (
                        '已清理 %d 个无用节点；仍保留 %d 个有效 Bind Pose，'
                        '未强制合并。' % (removed_count, remaining_count))
                else:
                    message = (
                        '完成：已清理 %d 个无用 Bind Pose，当前保留 %d 个。' %
                        (removed_count, remaining_count))
                self._set_status(message)
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True)

        def _cleanup_and_merge(self):
            try:
                with undo_chunk('YiDao Bind Pose Cleanup and Merge'):
                    result = cleanup_and_merge_bind_poses()
                removed_count = (len(result['removed_unused']) +
                                 len(result['removed_duplicates']))
                remaining_count = len(result['remaining'])
                if remaining_count > 1:
                    message = (
                        '已处理 %d 个节点；仍保留 %d 个 Bind Pose，'
                        '因骨骼系统或绑定姿势不同未合并。' %
                        (removed_count, remaining_count))
                else:
                    message = (
                        '完成：已清理并合并 %d 个节点，当前保留 %d 个 Bind Pose。' %
                        (removed_count, remaining_count))
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
