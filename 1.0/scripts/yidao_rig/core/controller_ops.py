# -*- coding: utf-8 -*-
"""Maya controller creation and curve editing operations."""
from __future__ import annotations

import os
import re
from contextlib import contextmanager

try:
    import maya.cmds as cmds
    import maya.api.OpenMaya as om2
except ImportError:
    cmds = om2 = None

from .shape_data import (
    ICONS_DIR, _safe_name, _shape_data, load_custom_shapes, save_custom_shapes,
    _ensure_dirs,
)


def _shape_nodes(node):
    if not cmds or not cmds.objExists(node):
        return []
    return cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True) or []


def _curve_fn(shape):
    selection = om2.MSelectionList()
    selection.add(shape)
    return om2.MFnNurbsCurve(selection.getDagPath(0))


def _copy_curve_cvs(source_shape, target_shape, mirror_axis=None):
    """Fit source geometry into the existing target Shape node.

    Different CV counts are sampled by arc length, not by knot parameter. This
    distributes points according to the visible source contour and is much
    closer for circles, arcs, and custom curves while preserving the target
    node required by AdvancedSkeleton.
    """
    source_cvs = cmds.ls(source_shape + '.cv[*]', flatten=True) or []
    target_cvs = cmds.ls(target_shape + '.cv[*]', flatten=True) or []
    if not source_cvs or not target_cvs:
        raise RuntimeError('源或目标 Shape 没有可用 CV。')
    axis_index = {'X': 0, 'Y': 1, 'Z': 2}.get(mirror_axis) if mirror_axis else None
    source_fn = _curve_fn(source_shape)
    target_count = len(target_cvs)
    source_count = len(source_cvs)
    closed = int(cmds.getAttr(source_shape + '.form')) == 3

    if source_count == target_count:
        points = [list(cmds.pointPosition(cv, local=True)) for cv in source_cvs]
    else:
        try:
            total_length = float(source_fn.length())
            # Closed curves must not sample the same seam twice.
            denominator = target_count if closed else max(1, target_count - 1)
            points = []
            for index in range(target_count):
                distance = total_length * index / float(denominator)
                parameter = source_fn.findParamFromLength(distance)
                point_obj = source_fn.getPointAtParam(parameter, om2.MSpace.kObject)
                points.append([point_obj.x, point_obj.y, point_obj.z])
        except Exception:
            # Fallback for unusual Maya curve APIs: use the source knot domain.
            source_min, source_max = source_fn.knotDomain
            denominator = target_count if closed else max(1, target_count - 1)
            points = []
            for index in range(target_count):
                parameter = source_min + (source_max - source_min) * index / float(denominator)
                point_obj = source_fn.getPointAtParam(parameter, om2.MSpace.kObject)
                points.append([point_obj.x, point_obj.y, point_obj.z])

    for target_cv, point in zip(target_cvs, points):
        if axis_index is not None:
            point[axis_index] *= -1.0
        cmds.xform(target_cv, objectSpace=True, translation=point)


def _set_color(shape_nodes, index):
    for shape in shape_nodes:
        if cmds.nodeType(shape) == 'nurbsCurve':
            cmds.setAttr(shape + '.overrideEnabled', 1)
            cmds.setAttr(shape + '.overrideRGBColors', 0)
            cmds.setAttr(shape + '.overrideColor', max(0, min(31, int(index))))


def _set_icon_preview_style(node):
    """Force preview curves to use thick white lines."""
    for shape in _shape_nodes(node):
        if cmds.nodeType(shape) != 'nurbsCurve':
            continue
        cmds.setAttr(shape + '.overrideEnabled', 1)
        cmds.setAttr(shape + '.overrideRGBColors', 1)
        cmds.setAttr(shape + '.overrideColorRGB', 1.0, 1.0, 1.0, type='double3')
        cmds.setAttr(shape + '.lineWidth', 3.0)


def scale_controller_shapes(targets=None, factor=1.0):
    """Scale selected controller CVs without changing the controller transform."""
    targets = targets or cmds.ls(selection=True, type='transform')
    if not targets:
        raise RuntimeError('请先选择要缩放的控制器。')
    factor = float(factor)
    if factor <= 0:
        raise ValueError('缩放倍率必须大于 0。')
    for target in targets:
        for shape in _shape_nodes(target):
            if cmds.nodeType(shape) != 'nurbsCurve':
                continue
            for cv in cmds.ls(shape + '.cv[*]', flatten=True) or []:
                point = cmds.pointPosition(cv, local=True)
                cmds.xform(cv, objectSpace=True,
                           translation=[point[0] * factor, point[1] * factor, point[2] * factor])


def _axis_rotate(node, axis):
    if axis == 'X':
        cmds.rotate(0, 90, 0, node, relative=True)
    elif axis == 'Z':
        cmds.rotate(90, 0, 0, node, relative=True)


def _unique_offset_name(base):
    """Return a unique offset-group name while keeping the controller name unchanged."""
    candidate = base
    index = 1
    while cmds.ls(candidate, long=True):
        candidate = '%s_%03d' % (base, index)
        index += 1
    return candidate


def _new_curve(data, name):
    curve_nodes = []
    for index, curve in enumerate(data):
        # 统一控制器前方为世界 -Z；创建和替换形状共用此规则。
        points = [[point[0], point[1], -point[2]] for point in curve['points']]
        kwargs = dict(degree=int(curve['degree']), point=points, knot=curve['knots'])
        node = cmds.curve(name=name if index == 0 else name + '_shape%02d' % index, **kwargs)
        curve_nodes.append(node)
    if not curve_nodes:
        raise RuntimeError('形状数据为空。')
    result = curve_nodes[0]
    for extra in curve_nodes[1:]:
        for shape in _shape_nodes(extra):
            cmds.parent(shape, result, shape=True, relative=True)
        cmds.delete(extra)
    return result


def create_controller(name='ctrl', shape='circle', size=1.0, color=13,
                      align=True, create_offset=True, axis=None):
    """Create a controller at the current selection or origin."""
    if not cmds:
        raise RuntimeError('该函数必须在 Maya 中运行。')
    target = (cmds.ls(selection=True, type='transform') or [None])[0]
    # 保留用户输入的控制器名称；Maya 允许不同父级下存在相同短名称。
    # Maya 创建命令会在需要时返回带层级限定的实际节点名。
    name = _safe_name(name) or 'ctrl'
    ctrl = _new_curve(_shape_data(shape), name)
    cmds.scale(float(size), float(size), float(size), ctrl)
    # Controllers are created in world-axis orientation by default.
    cmds.makeIdentity(ctrl, apply=True, translate=True, rotate=True, scale=True)
    if align and target:
        cmds.matchTransform(ctrl, target, position=True, rotation=True)
    _set_color(_shape_nodes(ctrl), color)
    if create_offset:
        offset_name = _unique_offset_name(ctrl + '_offset')
        offset = cmds.createNode('transform', name=offset_name)
        cmds.matchTransform(offset, ctrl)
        parent = cmds.listRelatives(ctrl, parent=True, fullPath=True)
        cmds.parent(ctrl, offset)
        if parent:
            cmds.parent(offset, parent[0])
        return ctrl, offset
    return ctrl, None


def _shape_display_color(shape):
    """Capture the exact viewport color state from a curve shape."""
    if not shape or not cmds.objExists(shape):
        return None
    try:
        enabled = cmds.getAttr(shape + '.overrideEnabled')
        rgb_mode = cmds.getAttr(shape + '.overrideRGBColors')
        index = cmds.getAttr(shape + '.overrideColor')
        rgb = cmds.getAttr(shape + '.overrideColorRGB')
        if isinstance(rgb, (list, tuple)) and rgb and isinstance(rgb[0], (list, tuple)):
            rgb = rgb[0]
        if not isinstance(rgb, (list, tuple)) or len(rgb) < 3:
            rgb = (1.0, 1.0, 1.0)
        return {
            'enabled': int(enabled if enabled is not None else 0),
            'rgb_mode': int(rgb_mode if rgb_mode is not None else 0),
            'index': int(index if index is not None else 0),
            'rgb': tuple(float(value) for value in rgb[:3]),
        }
    except Exception as exc:
        cmds.warning('无法读取控制器颜色 %s：%s' % (shape, exc))
        return None


def _apply_shape_display_color(shape, values):
    """Apply saved color after parenting the new shape and deleting the old one."""
    if not values or not cmds.objExists(shape) or cmds.nodeType(shape) != 'nurbsCurve':
        return
    # Set the mode and value first; enable override last so Maya cannot retain
    # the duplicated source shape's display color.
    cmds.setAttr(shape + '.overrideRGBColors', int(values['rgb_mode']))
    if values['rgb_mode']:
        cmds.setAttr(shape + '.overrideColorRGB', *values['rgb'], type='double3')
    else:
        cmds.setAttr(shape + '.overrideColor', int(values['index']))
    cmds.setAttr(shape + '.overrideEnabled', int(values['enabled']))


def replace_shape(targets=None, shape='circle', append=False):
    """Replace selected controller shapes with the exact requested shape."""
    targets = targets or cmds.ls(selection=True, type='transform')
    if not targets:
        raise RuntimeError('请先选择控制器。')
    if append:
        raise RuntimeError('当前替换模式不支持追加 Shape。')
    for target in targets:
        old_shapes = _shape_nodes(target)
        colors = [_shape_display_color(item) for item in old_shapes]
        temp = _new_curve(_shape_data(shape), '__YiDaoReplaceShapeTemp')
        try:
            temp_shapes = [item for item in _shape_nodes(temp)
                           if cmds.nodeType(item) == 'nurbsCurve']
            for item in temp_shapes:
                cmds.parent(item, target, shape=True, relative=True)
            cmds.delete(temp)
            for old_shape in old_shapes:
                if cmds.objExists(old_shape):
                    cmds.delete(old_shape)
            final_shapes = [item for item in _shape_nodes(target)
                            if cmds.nodeType(item) == 'nurbsCurve']
            for index, item in enumerate(final_shapes):
                if colors:
                    _apply_shape_display_color(
                        item, colors[min(index, len(colors) - 1)])
        finally:
            if cmds.objExists(temp):
                cmds.delete(temp)


def replace_shape_from_reference(selection=None):
    """Copy the first selected controller's shape to subsequently selected targets.

    Maya ordered selection is used: the first controller is the reference and
    remains unchanged; every later selected controller receives a duplicate of
    its curve shape. Each target keeps its own display color.
    """
    if selection is None:
        # orderedSelection 已经隐含当前选择；不要同时传 selection=True，
        # 否则 Maya 会生成互斥的 -sl/-os 选项并报：
        # Only one of -sl/-hl/-lv flags may be specified。
        selection = cmds.ls(orderedSelection=True, type='transform') or []
    if len(selection) < 2:
        raise RuntimeError('请先选择形状正确的控制器，再加选需要替换的控制器。')
    source = selection[0]
    targets = selection[1:]
    source_shapes = [s for s in _shape_nodes(source)
                     if cmds.nodeType(s) == 'nurbsCurve']
    if not source_shapes:
        raise RuntimeError('第一个选择的控制器不包含 nurbsCurve shape。')

    for target in targets:
        if target == source:
            continue
        old_shapes = _shape_nodes(target)
        colors = [_shape_display_color(item) for item in old_shapes]
        temp = cmds.duplicate(source, returnRootsOnly=True,
                              name=target.split('|')[-1] + '_replaceShapeTemp')[0]
        try:
            temp_shapes = [item for item in _shape_nodes(temp)
                           if cmds.nodeType(item) == 'nurbsCurve']
            for item in temp_shapes:
                cmds.parent(item, target, shape=True, relative=True)
            for old_shape in old_shapes:
                if cmds.objExists(old_shape):
                    cmds.delete(old_shape)
            final_shapes = [item for item in _shape_nodes(target)
                            if cmds.nodeType(item) == 'nurbsCurve']
            for index, item in enumerate(final_shapes):
                if colors:
                    _apply_shape_display_color(
                        item, colors[min(index, len(colors) - 1)])
        finally:
            if cmds.objExists(temp):
                cmds.delete(temp)
    return source, targets


def mirror_shape(axis='X', targets=None, negative=True):
    """Mirror CVs on the selected controllers in their local space."""
    targets = targets or cmds.ls(selection=True, type='transform')
    if not targets:
        raise RuntimeError('请先选择控制器。')
    axis_index = {'X': 0, 'Y': 1, 'Z': 2}[axis]
    multiplier = -1.0 if negative else 1.0
    for target in targets:
        for shape in _shape_nodes(target):
            if cmds.nodeType(shape) != 'nurbsCurve':
                continue
            cvs = cmds.ls(shape + '.cv[*]', flatten=True) or []
            for cv in cvs:
                point = cmds.pointPosition(cv, local=True)
                point[axis_index] *= multiplier
                cmds.xform(cv, objectSpace=True, translation=point)


def _mirror_counterpart_name(short_name):
    """Return the opposite-side name for common left/right suffix patterns."""
    patterns = (
        (r'(_)([lL])(_)', lambda m: m.group(1) + ('R' if m.group(2).isupper() else 'r') + m.group(3)),
        (r'(_)([rR])(_)', lambda m: m.group(1) + ('L' if m.group(2).isupper() else 'l') + m.group(3)),
        (r'(_)([lL])$', lambda m: m.group(1) + ('R' if m.group(2).isupper() else 'r')),
        (r'(_)([rR])$', lambda m: m.group(1) + ('L' if m.group(2).isupper() else 'l')),
    )
    for pattern, replacement in patterns:
        if re.search(pattern, short_name):
            return re.sub(pattern, replacement, short_name, count=1)
    return None


def _find_mirror_counterpart(source):
    """Find the opposite-side transform using the source short name."""
    short_name = source.split('|')[-1]
    counterpart = _mirror_counterpart_name(short_name)
    if not counterpart:
        raise RuntimeError('无法从名称中识别左右标记：%s' % short_name)
    source_parent = cmds.listRelatives(source, parent=True, fullPath=True) or []
    if source_parent:
        sibling_path = source_parent[0] + '|' + counterpart
        matches = cmds.ls(sibling_path, long=True, type='transform') or []
        if matches:
            return matches[0]
    matches = cmds.ls(counterpart, long=True, type='transform') or []
    if not matches:
        raise RuntimeError('找不到对应控制器：%s' % counterpart)
    if len(matches) > 1:
        raise RuntimeError('对应控制器不唯一：%s（请通过上层组区分）' % counterpart)
    return matches[0]


def _curve_data_from_shape(shape, axis_index):
    data = []
    for cv in cmds.ls(shape + '.cv[*]', flatten=True) or []:
        point = cmds.pointPosition(cv, local=True)
        point[axis_index] *= -1.0
        data.append([point[0], point[1], point[2]])
    return data


def mirror_shape_to_counterpart(axis='X', targets=None):
    """Copy a selected controller's mirrored shape to its L/R counterpart.

    The controller transforms and names are untouched. Only the target curve
    shapes are replaced. Supported name markers include ``_l``, ``_r``,
    ``_L``, ``_R``, ``_l_`` and ``_r_``.
    """
    targets = targets or cmds.ls(selection=True, type='transform', long=True)
    if len(targets) != 1:
        raise RuntimeError('请只选择一个控制器进行左右镜像。')
    source = targets[0]
    destination = _find_mirror_counterpart(source)
    axis_index = {'X': 0, 'Y': 1, 'Z': 2}.get(axis)
    if axis_index is None:
        raise RuntimeError('镜像轴只能是 X、Y 或 Z。')

    source_shapes = [s for s in _shape_nodes(source) if cmds.nodeType(s) == 'nurbsCurve']
    if not source_shapes:
        raise RuntimeError('所选对象不包含 nurbsCurve shape。')
    old_shapes = _shape_nodes(destination)
    colors = [_shape_display_color(item) for item in old_shapes]
    temp = cmds.duplicate(source, returnRootsOnly=True,
                          name=destination.split('|')[-1] + '_mirrorShapeTemp')[0]
    try:
        temp_shapes = [item for item in _shape_nodes(temp)
                       if cmds.nodeType(item) == 'nurbsCurve']
        for item in temp_shapes:
            for cv in cmds.ls(item + '.cv[*]', flatten=True) or []:
                point = list(cmds.pointPosition(cv, local=True))
                point[axis_index] *= -1.0
                cmds.xform(cv, objectSpace=True, translation=point)
            cmds.parent(item, destination, shape=True, relative=True)
        for old_shape in old_shapes:
            if cmds.objExists(old_shape):
                cmds.delete(old_shape)
        final_shapes = [item for item in _shape_nodes(destination)
                        if cmds.nodeType(item) == 'nurbsCurve']
        for index, item in enumerate(final_shapes):
            if colors:
                _apply_shape_display_color(
                    item, colors[min(index, len(colors) - 1)])
    finally:
        if cmds.objExists(temp):
            cmds.delete(temp)
    return source, destination


def flip_shape(axis='X', targets=None, degrees=90.0):
    """Rotate selected controller curve CVs 90 degrees around a local axis."""
    targets = targets or cmds.ls(selection=True, type='transform')
    if not targets:
        raise RuntimeError('请先选择控制器。')
    if axis not in ('X', 'Y', 'Z'):
        raise RuntimeError('翻转轴只能是 X、Y 或 Z。')
    axis_rotation = {'X': (degrees, 0.0, 0.0),
                     'Y': (0.0, degrees, 0.0),
                     'Z': (0.0, 0.0, degrees)}[axis]
    for target in targets:
        for shape in _shape_nodes(target):
            if cmds.nodeType(shape) != 'nurbsCurve':
                continue
            cmds.rotate(*axis_rotation, shape + '.cv[*]', relative=True,
                        objectSpace=True)



def capture_icon(target=None, path=None, width=256, height=256, color_index=16):
    target = target or (cmds.ls(selection=True, type='transform') or [None])[0]
    if not target:
        raise RuntimeError('请先选择控制器。')
    _ensure_dirs()
    path = path or os.path.join(ICONS_DIR, _safe_name(target) + '.png')
    old_selection = cmds.ls(selection=True) or []
    preview = None
    try:
        # 使用临时副本进行截图：统一白色，并避免原控制器的选中高亮变成绿色。
        preview = cmds.duplicate(target, returnRootsOnly=True, name='__controllerToolPreview__')[0]
        # duplicate 已经在原父层级下创建；不再重复 parent 到 world，避免 Maya 警告。
        _set_icon_preview_style(preview)
        # 将预览对象移到原点，并按最大包围盒维度归一化，保证主体铺满图标。
        bbox = cmds.exactWorldBoundingBox(preview)
        center = [(bbox[0] + bbox[3]) * 0.5, (bbox[1] + bbox[4]) * 0.5, (bbox[2] + bbox[5]) * 0.5]
        cmds.move(-center[0], -center[1], -center[2], preview, relative=True, worldSpace=True)
        bbox = cmds.exactWorldBoundingBox(preview)
        bbox_size = max(abs(bbox[3] - bbox[0]), abs(bbox[4] - bbox[1]), abs(bbox[5] - bbox[2]), 0.001)
        # 4.8 对应较大的图标主体，占据接近整个 256x256 画布。
        normalize_factor = 4.8 / bbox_size
        cmds.scale(normalize_factor, normalize_factor, normalize_factor, preview, relative=True)
        cmds.makeIdentity(preview, apply=True, scale=True)
        cmds.select(preview, replace=True)
        panel = cmds.getPanel(withFocus=True)
        if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
            panels = cmds.getPanel(visiblePanels=True) or []
            panel = next((p for p in panels if cmds.getPanel(typeOf=p) == 'modelPanel'), None)
        if not panel:
            raise RuntimeError('找不到可用的 Maya 视图面板。')
        cmds.modelEditor(panel, edit=True, displayAppearance='smoothShaded', grid=False)
        # 先将焦点切到模型面板，再使用当前面板执行 viewFit。
        # 某些 Maya 2024 版本会把 viewFit 的 panel 参数错误解析为对象参数，
        # 因此这里不传 panel，避免出现 “No object matches name: modelPanelX”。
        cmds.setFocus(panel)
        # 与内置线稿图标保持接近的主体占比；副本尺寸与原控制器完全一致。
        cmds.viewFit(fitFactor=0.55)
        # 清除选择后再 playblast，避免 Maya 的绿色选中高亮写入图标。
        cmds.select(clear=True)
        cmds.playblast(completeFilename=os.path.abspath(path), forceOverwrite=True, format='image',
                       compression='png', widthHeight=(int(width), int(height)), frame=1,
                       viewer=False, showOrnaments=False, offScreen=True, percent=100)
        if not os.path.isfile(os.path.abspath(path)):
            raise RuntimeError('Maya 截图命令已执行，但没有生成 PNG 文件：%s' % os.path.abspath(path))
    finally:
        if preview and cmds.objExists(preview):
            cmds.delete(preview)
        if old_selection:
            cmds.select(old_selection, replace=True)
        else:
            cmds.select(clear=True)
    return path


def capture_viewport_icon(path=None, width=256, height=256, panel=None):
    """Capture the current Maya model viewport as a custom-shape icon.

    The active camera, framing, shading, colors, and visible scene remain as
    shown in Maya. No duplicate object, viewFit, camera, or selection change
    is performed.
    """
    if not cmds:
        raise RuntimeError('该函数必须在 Maya 中运行。')
    _ensure_dirs()
    path = path or os.path.join(ICONS_DIR, 'controller_viewport.png')
    panel = panel or cmds.getPanel(withFocus=True)
    if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
        panels = cmds.getPanel(visiblePanels=True) or []
        panel = next((item for item in panels
                      if cmds.getPanel(typeOf=item) == 'modelPanel'), None)
    if not panel:
        raise RuntimeError('找不到可用的 Maya 视口面板。')
    result = cmds.playblast(
        completeFilename=os.path.abspath(path), forceOverwrite=True,
        format='image', compression='png', widthHeight=(int(width), int(height)),
        frame=1, viewer=False, showOrnaments=False, offScreen=True,
        percent=100, editorPanelName=panel)
    if not os.path.isfile(os.path.abspath(path)):
        raise RuntimeError('Maya 视口截图失败：%s' % os.path.abspath(path))
    return os.path.abspath(path)


def add_custom_shape(name=None, target=None, icon_path=None):
    """Save the selected controller shape with an optional internal name.

    The UI can omit ``name``; in that case a unique internal key is generated.
    The key is only used for persistence and is not required to be shown to
    users.
    """
    target = target or (cmds.ls(selection=True, type='transform') or [None])[0]
    if not target:
        raise RuntimeError('请先选择一个曲线控制器。')
    shapes = _shape_nodes(target)
    curves = []
    for shape in shapes:
        if cmds.nodeType(shape) != 'nurbsCurve':
            continue
        selection = om2.MSelectionList()
        selection.add(shape)
        dag_path = selection.getDagPath(0)
        fn = om2.MFnNurbsCurve(dag_path)
        points = fn.cvPositions(om2.MSpace.kObject)
        curves.append({'degree': fn.degree, 'points': [[p.x, p.y, p.z] for p in points],
                       'knots': list(fn.knots())})
    if not curves:
        raise RuntimeError('选择对象不包含 nurbsCurve shape。')
    data = load_custom_shapes()
    if not name:
        index = 1
        while 'custom_%03d' % index in data:
            index += 1
        name = 'custom_%03d' % index
    key = _safe_name(name)
    while key in data:
        index = 1
        while '%s_%03d' % (key, index) in data:
            index += 1
        key = '%s_%03d' % (key, index)
    data[key] = {'displayName': name, 'curves': curves, 'icon': icon_path or ''}
    save_custom_shapes(data)
    return key


@contextmanager
def undo_chunk(label):
    if cmds:
        cmds.undoInfo(openChunk=True, chunkName=label)
    try:
        yield
    finally:
        if cmds:
            cmds.undoInfo(closeChunk=True)
