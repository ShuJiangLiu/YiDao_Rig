# -*- coding: utf-8 -*-
"""Transform and joint attribute cleanup operations."""
from __future__ import print_function

try:
    import maya.cmds as cmds
    import maya.api.OpenMaya as om2
except ImportError:
    cmds = om2 = None


# Strict tolerances: retain Maya floating-point noise protection while making
# transform screening and constraint pose validation more precise.
_MATRIX_ERROR_TOLERANCE = 1.0e-7
_TRANSFORM_TOLERANCE = 1.0e-8


def _set_double3(node, attr, values):
    plug = node + '.' + attr
    if cmds.getAttr(plug, lock=True):
        return False
    cmds.setAttr(plug, float(values[0]), float(values[1]), float(values[2]), type='double3')
    return True


def _get_dag(node):
    selection = om2.MSelectionList()
    selection.add(node)
    return selection.getDagPath(0)


def _matrix_to_joint_orient(node):
    """Bake the evaluated local rotation directly into jointOrient.

    Maya commands expose rotation attributes in degrees, while OpenMaya
    returns Euler angles in radians. The previous implementation mixed these
    units and also delegated to makeIdentity, which could inspect constrained
    descendants. This method only changes the current joint's rotation stack.
    """
    dag = _get_dag(node)
    local_matrix = om2.MFnTransform(dag).transformation().asMatrix()
    tm = om2.MTransformationMatrix(local_matrix)
    rotation = tm.rotation()
    rotation_orders = (om2.MEulerRotation.kXYZ, om2.MEulerRotation.kYZX,
                       om2.MEulerRotation.kZXY, om2.MEulerRotation.kXZY,
                       om2.MEulerRotation.kYXZ, om2.MEulerRotation.kZYX)
    order = int(cmds.getAttr(node + '.rotateOrder'))
    if 0 <= order < len(rotation_orders):
        rotation.reorderIt(rotation_orders[order])
    scale = cmds.getAttr(node + '.scale')[0]
    # A shear/non-uniform scale can make a unique rotation decomposition
    # impossible. Refuse rather than silently changing the joint matrix.
    if any(abs(float(value)) < 1.0e-8 for value in scale):
        raise RuntimeError('Scale 包含 0，无法安全烘焙')
    values = tuple(float(value) * 180.0 / 3.141592653589793
                   for value in (rotation.x, rotation.y, rotation.z))
    cmds.setAttr(node + '.rotate', 0.0, 0.0, 0.0, type='double3')
    cmds.setAttr(node + '.rotateAxis', 0.0, 0.0, 0.0, type='double3')
    cmds.setAttr(node + '.jointOrient', values[0], values[1], values[2],
                 type='double3')


def _matrix_rotation_degrees(matrix, rotate_order):
    tm = om2.MTransformationMatrix(matrix)
    euler = tm.rotation()
    orders = (om2.MEulerRotation.kXYZ, om2.MEulerRotation.kYZX,
              om2.MEulerRotation.kZXY, om2.MEulerRotation.kXZY,
              om2.MEulerRotation.kYXZ, om2.MEulerRotation.kZYX)
    if 0 <= int(rotate_order) < len(orders):
        euler.reorderIt(orders[int(rotate_order)])
    factor = 180.0 / 3.141592653589793
    return tuple(float(v) * factor for v in (euler.x, euler.y, euler.z))


def _constraint_targets(constraint):
    if cmds.nodeType(constraint) == 'orientConstraint':
        return cmds.orientConstraint(constraint, query=True, targetList=True) or []
    return cmds.parentConstraint(constraint, query=True, targetList=True) or []


def _rotation_matrix(values, rotate_order):
    radians = tuple(float(value) * 3.141592653589793 / 180.0
                    for value in values)
    return om2.MEulerRotation(radians[0], radians[1], radians[2],
                              int(rotate_order)).asMatrix()


def _offset_plug(constraint):
    ctype = cmds.nodeType(constraint)
    if ctype == 'orientConstraint':
        return constraint + '.offset'
    targets = _constraint_targets(constraint)
    if len(targets) != 1:
        raise RuntimeError('%s 暂只支持单目标 parentConstraint，当前有 %d 个目标' %
                           (constraint, len(targets)))
    return constraint + '.target[0].targetOffsetRotate'


def _keep_constraint_and_zero_rotate(node, constraint, local_rotation):
    """Change only the supported constraint offset so its rotate output is zero."""
    plug = _offset_plug(constraint)
    old_offset = cmds.getAttr(plug)[0]
    offset_matrix = _rotation_matrix(old_offset, 0)
    joint_orient = _rotation_matrix(
        cmds.getAttr(node + '.jointOrient')[0],
        cmds.getAttr(node + '.rotateOrder'))
    rotate_axis = _rotation_matrix(
        cmds.getAttr(node + '.rotateAxis')[0],
        cmds.getAttr(node + '.rotateOrder'))
    constraint_rotation = rotate_axis.inverse() * joint_orient.inverse() * local_rotation
    new_offset = offset_matrix * constraint_rotation.inverse()
    values = _matrix_rotation_degrees(new_offset, 0)
    cmds.setAttr(plug, values[0], values[1], values[2], type='double3')


def _rotation_to_joint_orient(node):
    """Bake rotation while preserving supported constraint connections.

    The constraint remains connected. Maya's own maintainOffset edit is used
    to recompute the offset from the unchanged evaluated pose, avoiding a
    hand-written offset matrix whose multiplication order differs between
    orientConstraint and parentConstraint.
    """
    locked = any(cmds.getAttr(node + '.' + attr, lock=True)
                 for attr in ('rotateX', 'rotateY', 'rotateZ',
                              'jointOrientX', 'jointOrientY', 'jointOrientZ'))
    if locked:
        raise RuntimeError('rotate 或 jointOrient 属性被锁定')
    supported = {'orientConstraint', 'parentConstraint'}
    attrs = ('rotate', 'rotateX', 'rotateY', 'rotateZ')
    constraints, non_constraint, seen = [], [], set()
    for attr in attrs:
        for source in (cmds.listConnections(
                node + '.' + attr, source=True, destination=False,
                plugs=True) or []):
            source_node = source.split('.')[0]
            if source in seen:
                continue
            seen.add(source)
            ctype = cmds.nodeType(source_node)
            if ctype in supported:
                constraints.append(source_node)
            elif ctype:
                non_constraint.append(source)
    if non_constraint:
        raise RuntimeError('Rotate 被其他属性连接，已跳过（仅支持 orientConstraint 和 parentConstraint）：%s' %
                           ', '.join(non_constraint))
    constraints = list(dict.fromkeys(constraints))
    before = om2.MMatrix(cmds.xform(node, query=True, worldSpace=True, matrix=True))
    states = []
    try:
        # Temporarily block only the supported constraints. Constraint nodes do
        # not support the "Has No Effect" nodeState (1); Maya warns and changes
        # it to Blocked. Use the supported Blocked state (2) directly. The
        # connection remains intact and no disconnectAttr is used.
        for constraint in constraints:
            if not cmds.attributeQuery('nodeState', node=constraint, exists=True):
                raise RuntimeError('%s 没有可用的 nodeState，已跳过' % constraint)
            targets = _constraint_targets(constraint)
            if len(targets) != 1:
                raise RuntimeError('%s 暂只支持单目标约束' % constraint)
            states.append((constraint, cmds.getAttr(constraint + '.nodeState')))
            cmds.setAttr(constraint + '.nodeState', 2)

        local_matrix = om2.MFnTransform(_get_dag(node)).transformation().asMatrix()
        values = _matrix_rotation_degrees(
            local_matrix, cmds.getAttr(node + '.rotateOrder'))
        _set_double3(node, 'rotate', (0.0, 0.0, 0.0))
        _set_double3(node, 'rotateAxis', (0.0, 0.0, 0.0))
        _set_double3(node, 'jointOrient', values)

        # With constraints disabled, current pose is still the original pose.
        # Recalculate each supported constraint's Maintain Offset in-place.
        for constraint in constraints:
            targets = _constraint_targets(constraint)
            if cmds.nodeType(constraint) == 'orientConstraint':
                cmds.orientConstraint(targets[0], node, edit=True,
                                      maintainOffset=True)
            else:
                cmds.parentConstraint(targets[0], node, edit=True,
                                      maintainOffset=True)
    finally:
        for constraint, state in states:
            if cmds.objExists(constraint):
                cmds.setAttr(constraint + '.nodeState', state)
    after = om2.MMatrix(cmds.xform(node, query=True, worldSpace=True, matrix=True))
    error = max(abs(float(a) - float(b)) for a, b in zip(before, after))
    if error > _MATRIX_ERROR_TOLERANCE:
        raise RuntimeError('烘焙改变了世界矩阵（误差 %.3g，允许误差 %.1e）' %
                           (error, _MATRIX_ERROR_TOLERANCE))
    return True


def _non_default(values, defaults, tolerance=_TRANSFORM_TOLERANCE):
    return any(abs(float(value) - float(default)) > tolerance
               for value, default in zip(values, defaults))


def _format_transform_values(values, tolerance):
    """Format displayed values at the same precision used by the tolerance."""
    if tolerance <= 0.0:
        decimals = 6
    else:
        import math
        decimals = max(0, int(math.ceil(-math.log10(float(tolerance)))))
    rounded = []
    for value in values:
        number = round(float(value), decimals)
        if abs(number) <= tolerance:
            number = 0.0
        rounded.append(number)
    return tuple(rounded)


def find_non_default_transforms(targets=None, tolerance=_TRANSFORM_TOLERANCE):
    """Find selected transform nodes whose Translate/Rotate/Scale are non-default."""
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    targets = targets or cmds.ls(selection=True, long=True, type='transform') or []
    if not targets:
        raise RuntimeError('请先选择需要筛查的对象。')
    offenders = []
    details = []
    for node in targets:
        if not cmds.objExists(node):
            continue
        translate = cmds.getAttr(node + '.translate')[0]
        rotate = cmds.getAttr(node + '.rotate')[0]
        scale = cmds.getAttr(node + '.scale')[0]
        non_default = []
        if _non_default(translate, (0.0, 0.0, 0.0), tolerance):
            non_default.append('Translate=%s' %
                               (_format_transform_values(translate, tolerance),))
        if _non_default(rotate, (0.0, 0.0, 0.0), tolerance):
            non_default.append('Rotate=%s' %
                               (_format_transform_values(rotate, tolerance),))
        if _non_default(scale, (1.0, 1.0, 1.0), tolerance):
            non_default.append('Scale=%s' %
                               (_format_transform_values(scale, tolerance),))
        if non_default:
            offenders.append(node)
            details.append('%s：%s' % (node, ', '.join(non_default)))
    cmds.select(offenders, replace=True)
    return offenders, details


def cleanup_attributes(targets=None, translate=True, rotate=True, scale=True,
                       zero_joint_orient=False, bake_joint_rotation=False):
    """Set selected transform attributes directly, without freezing transforms."""
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    targets = targets or cmds.ls(selection=True, long=True, type='transform') or []
    if not targets:
        raise RuntimeError('请先选择需要清理属性的对象。')
    changed = []
    warnings = []
    for node in targets:
        if not cmds.objExists(node):
            continue
        is_joint = cmds.nodeType(node) == 'joint'
        if is_joint and bake_joint_rotation:
            try:
                # Ordinary joints and constraint-driven joints are supported;
                # other incoming rotate connections are rejected by the core.
                _rotation_to_joint_orient(node)
            except Exception as exc:
                warnings.append('%s：%s' % (node, exc))
                continue
        elif rotate:
            _set_double3(node, 'rotate', (0.0, 0.0, 0.0))
        if translate:
            _set_double3(node, 'translate', (0.0, 0.0, 0.0))
        if scale:
            _set_double3(node, 'scale', (1.0, 1.0, 1.0))
        if is_joint and zero_joint_orient and not bake_joint_rotation:
            _set_double3(node, 'jointOrient', (0.0, 0.0, 0.0))
        changed.append(node)
    return changed, warnings


def undo_chunk(label):
    class _Chunk(object):
        def __enter__(self):
            cmds.undoInfo(openChunk=True, chunkName=label)
            return self
        def __exit__(self, exc_type, exc_value, traceback):
            cmds.undoInfo(closeChunk=True)
    return _Chunk()
