# -*- coding: utf-8 -*-
"""Qt UI for YiDao Rig naming operations."""
from __future__ import print_function

from ..compat.qt_compat import (
    QtWidgets, QT_WINDOW, QT_WINDOW_SYSTEM_MENU, QT_WINDOW_CLOSE,
    QT_WINDOW_MINIMIZE, QT_WINDOW_MAXIMIZE, QT_DELETE_ON_CLOSE,
)
from ..compat.maya_compat import cmds, maya_main_window
from ..core.naming_ops import (
    search_replace, rename_hierarchy_chain, chain_base_from_selection,
    undo_chunk)
from ..core.ui_state import setup_state


WINDOW_OBJECT = 'yidaoNamingWindow'
_STYLE = '''
QDialog { background: #202020; color: #e8e8e8; }
QLabel { color: #cfcfcf; }
QGroupBox { border: 1px solid #3c3c3c; border-radius: 5px; margin-top: 8px; padding: 8px 6px 6px 6px; font-weight: bold; color: #e0e0e0; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QSpinBox { background: #292929; border: 1px solid #4a4a4a; border-radius: 3px; padding: 4px 6px; color: #f0f0f0; min-height: 22px; }
QLineEdit:focus, QSpinBox:focus { border: 1px solid #6b9dcc; }
QPushButton { background: #353535; border: 1px solid #4d4d4d; border-radius: 3px; padding: 5px 10px; min-height: 28px; color: #ededed; }
QPushButton:hover { background: #454545; border-color: #6b9dcc; }
QPushButton:pressed { background: #2a2a2a; }
QCheckBox { color: #d8d8d8; spacing: 6px; }
QLabel#hintLabel { color: #a9a9a9; font-size: 11px; }
QLabel#statusLabel { color: #ffffff; padding: 3px 2px; }
QLabel#statusLabel[error="true"] { color: #ff6b6b; }
'''


if QtWidgets:
    class NamingWindow(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName(WINDOW_OBJECT)
            self.setWindowTitle('Naming')
            self.setMinimumSize(520, 500)
            self.setStyleSheet(_STYLE)
            self._build_ui()
            self._save_ui_state = setup_state(self, 'naming')

        def _build_ui(self):
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)
            intro = QtWidgets.QLabel(
                '提供普通查找替换和层级链顺序命名。操作范围由“包含所选对象的子层级”控制。')
            intro.setWordWrap(True)
            root.addWidget(intro)

            scope_group = QtWidgets.QGroupBox('处理范围')
            scope_layout = QtWidgets.QVBoxLayout(scope_group)
            scope_layout.setContentsMargins(8, 6, 8, 6)
            self.hierarchy_check = QtWidgets.QCheckBox('包含所选对象的子层级')
            self.hierarchy_check.setChecked(False)
            scope_layout.addWidget(self.hierarchy_check)
            scope_hint = QtWidgets.QLabel(
                '关闭：只处理当前选择；开启：查找替换和层级链命名都会处理子层级。')
            scope_hint.setObjectName('hintLabel')
            scope_hint.setWordWrap(True)
            scope_layout.addWidget(scope_hint)
            root.addWidget(scope_group)

            replace_group = QtWidgets.QGroupBox('查找和替换')
            replace_layout = QtWidgets.QGridLayout(replace_group)
            replace_layout.setContentsMargins(8, 6, 8, 6)
            replace_layout.addWidget(QtWidgets.QLabel('查找'), 0, 0)
            self.search_edit = QtWidgets.QLineEdit()
            self.search_edit.setPlaceholderText('例如：_L')
            replace_layout.addWidget(self.search_edit, 0, 1)
            replace_layout.addWidget(QtWidgets.QLabel('替换为'), 1, 0)
            self.replace_edit = QtWidgets.QLineEdit()
            self.replace_edit.setPlaceholderText('例如：_R')
            replace_layout.addWidget(self.replace_edit, 1, 1)
            replace_button = QtWidgets.QPushButton('执行查找和替换')
            replace_button.setMinimumHeight(36)
            replace_button.clicked.connect(self._replace)
            replace_layout.addWidget(replace_button, 2, 0, 1, 2)
            root.addWidget(replace_group)

            chain_group = QtWidgets.QGroupBox('层级链顺序命名')
            chain_layout = QtWidgets.QGridLayout(chain_group)
            chain_layout.setContentsMargins(8, 6, 8, 6)
            chain_layout.addWidget(QtWidgets.QLabel('基础名称'), 0, 0)
            self.base_edit = QtWidgets.QLineEdit()
            self.base_edit.setPlaceholderText('留空使用根骨骼名称')
            chain_layout.addWidget(self.base_edit, 0, 1, 1, 3)
            chain_layout.addWidget(QtWidgets.QLabel('分隔符'), 1, 0)
            self.separator_edit = QtWidgets.QLineEdit('_')
            self.separator_edit.setMaximumWidth(70)
            chain_layout.addWidget(self.separator_edit, 1, 1)
            chain_layout.addWidget(QtWidgets.QLabel('起始编号'), 1, 2)
            self.start_spin = QtWidgets.QSpinBox()
            self.start_spin.setRange(0, 9999)
            self.start_spin.setValue(0)
            chain_layout.addWidget(self.start_spin, 1, 3)
            chain_layout.addWidget(QtWidgets.QLabel('编号位数'), 2, 0)
            self.digits_spin = QtWidgets.QSpinBox()
            self.digits_spin.setRange(1, 8)
            self.digits_spin.setValue(2)
            chain_layout.addWidget(self.digits_spin, 2, 1)
            chain_hint = QtWidgets.QLabel(
                '支持骨骼、控制器组等任意 Transform 层级。示例：arm_00、arm_01、arm_02……')
            chain_hint.setObjectName('hintLabel')
            chain_layout.addWidget(chain_hint, 2, 2, 1, 2)
            chain_button = QtWidgets.QPushButton('重命名所选层级链')
            chain_button.setMinimumHeight(36)
            chain_button.clicked.connect(self._rename_chain)
            chain_layout.addWidget(chain_button, 3, 0, 1, 4)
            chain_layout.setColumnStretch(1, 1)
            chain_layout.setColumnStretch(3, 1)
            root.addWidget(chain_group)

            self.status = QtWidgets.QLabel('就绪：请选择对象或层级链')
            self.status.setObjectName('statusLabel')
            root.addWidget(self.status)

        def _set_status(self, text, error=False):
            self.status.setProperty('error', 'true' if error else 'false')
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.status.setText(text)

        def _replace(self):
            try:
                with undo_chunk('YiDao Naming Search Replace'):
                    renamed = search_replace(
                        self.search_edit.text(), self.replace_edit.text(),
                        hierarchy=self.hierarchy_check.isChecked())
                self._set_status('完成：重命名 %d 个对象' % len(renamed))
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True)
                if cmds:
                    cmds.warning(str(exc))

        def _rename_chain(self):
            try:
                base = self.base_edit.text().strip()
                if not base:
                    base = chain_base_from_selection()
                    if base:
                        self.base_edit.setText(base)
                with undo_chunk('YiDao Naming Hierarchy Chain'):
                    renamed = rename_hierarchy_chain(
                        base_name=base,
                        separator=self.separator_edit.text(),
                        start_index=self.start_spin.value(),
                        digits=self.digits_spin.value(),
                        include_children=self.hierarchy_check.isChecked())
                self._set_status('完成：按父子顺序重命名 %d 个层级节点' % len(renamed))
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True)
                if cmds:
                    cmds.warning(str(exc))
else:
    NamingWindow = None


def show():
    if not QtWidgets:
        raise RuntimeError('无法导入 PySide2/PySide6；请在 Maya 2022-2026 中运行。')
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT:
            widget.close()
            widget.deleteLater()
    window = NamingWindow(parent=maya_main_window())
    window.setWindowFlags(QT_WINDOW | QT_WINDOW_SYSTEM_MENU | QT_WINDOW_CLOSE |
                          QT_WINDOW_MINIMIZE | QT_WINDOW_MAXIMIZE)
    window.setAttribute(QT_DELETE_ON_CLOSE, True)
    window.showNormal()
    window.raise_()
    window.activateWindow()
    return window
