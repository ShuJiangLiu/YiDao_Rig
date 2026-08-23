# -*- coding: utf-8 -*-
"""Qt UI for transform attribute connection management."""
from __future__ import print_function

from ..compat.qt_compat import (QtCore, QtWidgets, QT_WINDOW,
                                 QT_WINDOW_SYSTEM_MENU, QT_WINDOW_CLOSE,
                                 QT_WINDOW_MINIMIZE, QT_WINDOW_MAXIMIZE,
                                 QT_DELETE_ON_CLOSE)
from ..compat.maya_compat import cmds, maya_main_window
from ..core.ui_state import setup_state
from ..core.attribute_connection_ops import (disconnect_selected,
    reconnect_saved, saved_connection_count, saved_connection_summary,
    undo_chunk)

WINDOW_OBJECT = 'yidaoAttributeConnectionWindow'
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
    class AttributeConnectionWindow(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName(WINDOW_OBJECT)
            self.setWindowTitle('Attribute Connection')
            self.setMinimumSize(480, 330)
            self.setSizeGripEnabled(True)
            self.setStyleSheet(_STYLE)
            self._build_ui()
            self._save_ui_state = setup_state(self, 'attribute_connection')

        def _build_ui(self):
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(8)
            intro = QtWidgets.QLabel(
                '管理当前选择的骨骼或控制器的 Transform 输入连接。\n'
                '支持约束、Set Driven Key 和普通属性直接连接，并重建原约束 Offset。')
            intro.setWordWrap(True)
            layout.addWidget(intro)

            scope_group = QtWidgets.QGroupBox('处理范围')
            scope_layout = QtWidgets.QVBoxLayout(scope_group)
            scope_layout.setContentsMargins(8, 6, 8, 6)
            scope_layout.addWidget(QtWidgets.QLabel(
                'Translate / Rotate / Scale（包含 XYZ 子属性）'))
            hint = QtWidgets.QLabel(
                '断开时记录约束目标、权重并删除约束节点；重连时按原类型重建并开启 Maintain Offset。')
            hint.setObjectName('hintLabel')
            hint.setWordWrap(True)
            scope_layout.addWidget(hint)
            layout.addWidget(scope_group)

            action_group = QtWidgets.QGroupBox('连接操作')
            action_layout = QtWidgets.QVBoxLayout(action_group)
            action_layout.setContentsMargins(8, 6, 8, 8)
            action_layout.setSpacing(6)
            self.info = QtWidgets.QLabel('当前没有连接记录')
            self.info.setWordWrap(True)
            self.info.setObjectName('hintLabel')
            action_layout.addWidget(self.info)
            self.disconnect_button = QtWidgets.QPushButton('一键断开（记录连接状态）')
            self.reconnect_button = QtWidgets.QPushButton('一键重连（保持原连接与 Offset）')
            self.disconnect_button.setObjectName('disconnectButton')
            self.reconnect_button.setObjectName('reconnectButton')
            self.disconnect_button.setMinimumHeight(36)
            self.reconnect_button.setMinimumHeight(36)
            self.disconnect_button.clicked.connect(self._disconnect)
            self.reconnect_button.clicked.connect(self._reconnect)
            action_layout.addWidget(self.disconnect_button)
            action_layout.addWidget(self.reconnect_button)
            layout.addWidget(action_group)
            self.status = QtWidgets.QLabel('就绪：请选择骨骼或控制器')
            self.status.setObjectName('statusLabel')
            layout.addWidget(self.status)

        def _set_status(self, text, error=False):
            self.status.setProperty('error', 'true' if error else 'false')
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.status.setText(text)

        def _disconnect(self):
            try:
                with undo_chunk('YiDao Disconnect Transform Connections'):
                    state = disconnect_selected()
                summary = saved_connection_summary()
                self.info.setText('已记录 %d 个对象、%d 条连接；现在可以编辑断开后的属性。' %
                                  (len(state), saved_connection_count()))
                self._set_status('断开完成（约束节点已删除）：约束 %d，Set Driven Key %d，直接连接 %d' %
                                 (summary['constraint'], summary['setDrivenKey'],
                                  summary['direct']))
            except Exception as exc:
                self._set_status('断开失败：' + str(exc), error=True)
                if cmds:
                    cmds.warning(str(exc))

        def _reconnect(self):
            try:
                with undo_chunk('YiDao Reconnect Transform Connections'):
                    restored, warnings = reconnect_saved()
                if warnings:
                    self._set_status('重连完成：%d 个对象；有 %d 条警告' %
                                     (len(restored), len(warnings)), error=True)
                    for warning in warnings:
                        if cmds:
                            cmds.warning(warning)
                else:
                    self.info.setText('连接记录已恢复，约束节点已按原类型重建并开启 Maintain Offset。')
                    self._set_status('重连完成：%d 个对象' % len(restored))
            except Exception as exc:
                self._set_status('重连失败：' + str(exc), error=True)
                if cmds:
                    cmds.warning(str(exc))
else:
    AttributeConnectionWindow = None


def show():
    if not QtWidgets:
        raise RuntimeError('无法导入 PySide2/PySide6；请在 Maya 2022-2026 中运行。')
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT:
            widget.close()
            widget.deleteLater()
    window = AttributeConnectionWindow(parent=maya_main_window())
    window.setWindowFlags(QT_WINDOW | QT_WINDOW_SYSTEM_MENU | QT_WINDOW_CLOSE |
                          QT_WINDOW_MINIMIZE | QT_WINDOW_MAXIMIZE)
    window.setAttribute(QT_DELETE_ON_CLOSE, True)
    window.showNormal()
    window.raise_()
    window.activateWindow()
    return window
