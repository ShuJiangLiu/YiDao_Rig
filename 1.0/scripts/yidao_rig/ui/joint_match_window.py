# -*- coding: utf-8 -*-
"""Qt UI for explicit source/target Joint Match."""
from __future__ import print_function

from ..compat.qt_compat import (
    QtCore, QtWidgets, QT_WINDOW, QT_WINDOW_SYSTEM_MENU, QT_WINDOW_CLOSE,
    QT_WINDOW_MINIMIZE, QT_WINDOW_MAXIMIZE, QT_DELETE_ON_CLOSE,
)
from ..compat.maya_compat import cmds, maya_main_window
from ..core.joint_match_ops import match_joint_roots, undo_chunk
from ..core.ui_state import setup_state

WINDOW_OBJECT = 'yidaoJointMatchWindow'
_STYLE = '''
QDialog { background: #202020; color: #e8e8e8; }
QLabel { color: #cfcfcf; }
QGroupBox { border: 1px solid #3c3c3c; border-radius: 5px; margin-top: 8px; padding: 8px 6px 6px 6px; font-weight: bold; color: #e0e0e0; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QListWidget, QLineEdit { background: #292929; border: 1px solid #4a4a4a; border-radius: 3px; padding: 4px 6px; color: #f0f0f0; }
QListWidget { min-height: 105px; }
QPushButton { background: #353535; border: 1px solid #4d4d4d; border-radius: 3px; padding: 5px 10px; min-height: 26px; color: #ededed; }
QPushButton:hover { background: #454545; border-color: #6b9dcc; }
QCheckBox { color: #d8d8d8; spacing: 6px; }
'''


if QtWidgets:
    class JointMatchWindow(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName(WINDOW_OBJECT)
            self.setWindowTitle('Joint Match')
            self.setMinimumSize(700, 520)
            self.setStyleSheet(_STYLE)
            self._build_ui()
            self._save_ui_state = setup_state(self, 'joint_match')

        def _build_ui(self):
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)
            info = QtWidgets.QLabel(
                '左侧加载源骨骼，右侧加载目标骨骼。工具通过相同骨骼名称和层级进行匹配，\n'
                '目标可以来自引用文件并带有命名空间。')
            info.setWordWrap(True)
            root.addWidget(info)

            columns = QtWidgets.QHBoxLayout()
            self.source_list, source_box = self._make_column('源骨骼（无命名空间）')
            self.target_list, target_box = self._make_column('目标骨骼（可带命名空间）')
            columns.addWidget(source_box)
            columns.addWidget(target_box)
            root.addLayout(columns)

            mode = QtWidgets.QGroupBox('匹配范围')
            mode_layout = QtWidgets.QVBoxLayout(mode)
            self.hierarchy_check = QtWidgets.QCheckBox('匹配整条骨骼链（包含子骨骼）')
            self.hierarchy_check.setChecked(True)
            mode_layout.addWidget(self.hierarchy_check)
            root.addWidget(mode)

            attrs = QtWidgets.QGroupBox('匹配属性')
            attrs_layout = QtWidgets.QHBoxLayout(attrs)
            self.translation_check = QtWidgets.QCheckBox('Translation')
            self.translation_check.setChecked(True)
            self.rotation_check = QtWidgets.QCheckBox('Rotation')
            self.rotation_check.setChecked(True)
            self.scale_check = QtWidgets.QCheckBox('Scale')
            self.scale_check.setChecked(False)
            for widget in (self.translation_check, self.rotation_check, self.scale_check):
                attrs_layout.addWidget(widget)
            attrs_layout.addStretch()
            root.addWidget(attrs)

            button = QtWidgets.QPushButton('匹配骨骼链')
            button.setMinimumHeight(38)
            button.clicked.connect(self._match)
            root.addWidget(button)
            self.status = QtWidgets.QLabel('就绪：请分别加载源骨骼和目标骨骼')
            self.status.setObjectName('statusLabel')
            self.status.setStyleSheet('QLabel#statusLabel { color: #ffffff; padding: 3px 2px; } QLabel#statusLabel[error="true"] { color: #ff4d4d; }')
            root.addWidget(self.status)

        def _make_column(self, title):
            box = QtWidgets.QGroupBox(title)
            layout = QtWidgets.QVBoxLayout(box)
            listing = QtWidgets.QListWidget()
            listing.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            add = QtWidgets.QPushButton('从当前选择加载')
            clear = QtWidgets.QPushButton('清除')
            add.clicked.connect(lambda: self._load_current(listing))
            clear.clicked.connect(listing.clear)
            layout.addWidget(listing)
            buttons = QtWidgets.QHBoxLayout()
            buttons.addWidget(add)
            buttons.addWidget(clear)
            layout.addLayout(buttons)
            return listing, box

        def _load_current(self, listing):
            selection = cmds.ls(selection=True, type='joint', long=True) or []
            if not selection:
                self._set_status('失败：请先在 Maya 中选择一根骨骼作为骨骼链根', error=True)
                return
            listing.clear()
            root = selection[0]
            item = QtWidgets.QListWidgetItem(root)
            item.setData(QtCore.Qt.UserRole, root)
            listing.addItem(item)
            listing.setCurrentRow(0)
            self.status.setText('已加载：' + root)

        def _loaded_root(self, listing):
            item = listing.currentItem()
            return item.data(QtCore.Qt.UserRole) if item else None

        def _set_status(self, text, error=False):
            self.status.setProperty('error', 'true' if error else 'false')
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.status.setText(text)

        def _match(self):
            source = self._loaded_root(self.source_list)
            target = self._loaded_root(self.target_list)
            try:
                with undo_chunk('YiDao Joint Match'):
                    matched, warnings = match_joint_roots(
                        source, target,
                        hierarchy=self.hierarchy_check.isChecked(),
                        translation=self.translation_check.isChecked(),
                        rotation=self.rotation_check.isChecked(),
                        scale=self.scale_check.isChecked())
                for warning in warnings:
                    cmds.warning(warning)
                self._set_status('完成：匹配 %d 根，警告 %d 条' %
                                 (len(matched), len(warnings)), error=bool(warnings))
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True)
                cmds.warning(str(exc))
else:
    JointMatchWindow = None


def show():
    if not QtWidgets:
        raise RuntimeError('无法导入 PySide2/PySide6；请在 Maya 2022-2026 中运行。')
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT:
            widget.close()
            widget.deleteLater()
    window = JointMatchWindow(parent=maya_main_window())
    window.setWindowFlags(QT_WINDOW | QT_WINDOW_SYSTEM_MENU | QT_WINDOW_CLOSE |
                          QT_WINDOW_MINIMIZE | QT_WINDOW_MAXIMIZE)
    window.setAttribute(QT_DELETE_ON_CLOSE, True)
    window.showNormal()
    window.raise_()
    window.activateWindow()
    return window
