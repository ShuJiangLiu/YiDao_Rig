# -*- coding: utf-8 -*-
"""Precision joint mirroring operations for Maya 2022-2026."""
from __future__ import print_function

# -*- coding: utf-8 -*-
"""
精准镜像骨骼工具 (Mirror Joints Exact)
=======================================

功能与 Maya 自带的 mirrorJoint 一致（镜像结果逐属性对齐），
但彻底避免其浮点数误差。

误差原理
--------
Maya 自带的 mirrorJoint 在计算镜像变换时会经过矩阵"分解-合成"，
引入 1e-13 ~ 1e-15 量级的误差，导致镜像侧出现 -4.44e-16、
-2.22e-16 之类的脏数值（本应为 0）。

本工具的核心思路
----------------
镜像（沿某一轴向翻转）在数学上只是"取负"操作，而浮点数取负是
**无损**的（只翻转符号位，尾数完全不变）。

经与 mirrorJoint 实测对比，Maya 的镜像规则为（行向量 MMatrix 约定）：

* **链根骨骼**（父级不在镜像集合内）：
      Behavior    : W' = D·W·S，D = diag(-1,-1,-1,1)，S = 反射矩阵
      Orientation : W' = 只镜像位置分量，旋转不变
      本地 L' = W'·[父级世界矩阵]⁻¹
* **子级 Behavior**：本地 L' = D·L·D
      → 平移 (-tx, -ty, -tz) 三轴全取负，旋转/缩放原样复制
      → 位级精确，无任何矩阵分解
* **子级 Orientation**：世界矩阵取 position-mirror，
      本地 = W'·[已镜像父级的世界矩阵]⁻¹

精度说明
--------
* 子级骨骼（占大多数）：只做 复制+取负，位级精确，无任何误差。
* 链根骨骼（Behavior 模式）：位置 = 源本地矩阵平移的符号翻转（+180° yaw）；
  欧拉角分解误差 ~1e-16，比 mirrorJoint 的 ~1e-13 低三个数量级。
* 本工具镜像的是**骨骼本地坐标系**（与 mirrorJoint 一致：在父级本地帧中反射）。
----
    from tools import mirror_joints_tool
    mirror_joints_tool.run()          # 打开界面

或者不用界面，直接在脚本里调用（可做成 shelf 按钮）：

    from tools import mirror_joints_tool
    mirror_joints_tool.mirror_selected(
        plane='YZ',            # 镜像平面: XY / YZ / XZ（与 Maya UI 顺序一致）
        behavior=True,         # True=行为镜像(同 mirrorJoint -mb)
        search='L_',           # 命名搜索字符串
        replace='R_',          # 替换字符串
        hierarchy=True,        # 是否镜像整个层级
    )
"""

try:
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
except ImportError:
    cmds = om = None

from ..compat.maya_compat import display_node

# 镜像平面 -> 被取负的轴向分量索引 (0=X, 1=Y, 2=Z)
_PLANE_AXIS = {'YZ': 0, 'XZ': 1, 'XY': 2}

# Maya rotateOrder 枚举与 MEulerRotation 枚举一一对应
_ROT_ORDERS = (
    [
        om.MEulerRotation.kXYZ,
        om.MEulerRotation.kYZX,
        om.MEulerRotation.kZXY,
        om.MEulerRotation.kXZY,
        om.MEulerRotation.kYXZ,
        om.MEulerRotation.kZYX,
    ] if om else []
)

_EPS = 1e-7  # 判断 rotate / rotateAxis 是否为 0 的容差


# ----------------------------------------------------------------------
# 底层精确读写（全部使用 API 原始存储值：距离=cm, 角度=弧度，不做单位换算）
# ----------------------------------------------------------------------

def _get_dag(node):
    """返回节点的 MDagPath"""
    sel = om.MSelectionList()
    sel.add(node)
    return sel.getDagPath(0)


def _plug(node, attr):
    sel = om.MSelectionList()
    sel.add(node)
    dep = om.MFnDependencyNode(sel.getDependNode(0))
    return dep.findPlug(attr, False)


def _get_raw_double3(node, attr):
    """读取 double3 属性的内部原始值（距离为 cm，角度为弧度）"""
    p = _plug(node, attr)
    return [p.child(i).asDouble() for i in range(3)]


def _set_raw_double3(node, attr, values):
    """写入 double3 属性的内部原始值，跳过 locked 的分量"""
    p = _plug(node, attr)
    for i in range(3):
        c = p.child(i)
        if not c.isLocked:
            c.setDouble(float(values[i]))


def _is_zero3(values):
    return all(abs(v) < _EPS for v in values)


def _clean_neg_zero(v):
    """把 -0.0 规范为 0.0"""
    return 0.0 if v == 0.0 else v


# ----------------------------------------------------------------------
# 矩阵工具
# ----------------------------------------------------------------------

def _reflection_matrix(plane):
    """镜像平面的反射矩阵 S（法向轴分量取负）"""
    rows = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    rows[_PLANE_AXIS[plane]][_PLANE_AXIS[plane]] = -1.0
    return om.MMatrix(rows)


def _flip_basis_matrix():
    """Behavior 链根的 180 度翻转矩阵 D = diag(-1,-1,-1,1)"""
    return om.MMatrix([[-1.0, 0.0, 0.0, 0.0],
                       [0.0, -1.0, 0.0, 0.0],
                       [0.0, 0.0, -1.0, 0.0],
                       [0.0, 0.0, 0.0, 1.0]])


def _local_matrix(joint):
    """返回骨骼本地矩阵（父级坐标空间）"""
    dag = _get_dag(joint)
    return om.MFnTransform(dag).transformation().asMatrix()


def _mirror_position_matrix(m, plane):
    """只镜像矩阵的位置分量（法向轴取负），旋转部分保持不变"""
    tm = om.MTransformationMatrix(m)
    t = tm.translation(om.MSpace.kTransform)
    comps = [t.x, t.y, t.z]
    comps[_PLANE_AXIS[plane]] = -comps[_PLANE_AXIS[plane]]
    tm.setTranslation(om.MVector(*comps), om.MSpace.kTransform)
    return tm.asMatrix()


def _decompose_local(local, rotate_order):
    """分解本地矩阵 -> (translate[3], euler_rad[3], scale[3])"""
    tm = om.MTransformationMatrix(local)
    euler = tm.rotation()
    euler.reorderIt(_ROT_ORDERS[rotate_order])
    t = tm.translation(om.MSpace.kTransform)
    s = tm.scale(om.MSpace.kTransform)
    return [t.x, t.y, t.z], [euler.x, euler.y, euler.z], list(s)


# ----------------------------------------------------------------------
# 核心：镜像数值计算
# ----------------------------------------------------------------------

def mirror_child_behavior(src):
    """
    Behavior 模式子级骨骼（父级也被镜像）。

        平移   (-tx, -ty, -tz)   —— 三轴全部取负，无损
        旋转   原样复制           —— 无损
        缩放   原样复制           —— 无损

    行为依据：世界空间 `W'_each = D·W·S` 约定下，
    子级本地矩阵 `L' = D·L·D`（D = diag(-1,-1,-1,1)，行向量乘法约定）。
    旋转部分共轭抵消；平移三轴全部取负。与平面无关。
    
    返回 (translate, joint_orient, scale, fast_path)，弧度/cm 原始单位。
    fast_path=False 表示骨骼带有 rotate/rotateAxis，需一次矩阵分解
    把总旋转合并进 jointOrient（误差 ~1e-16）。
    """
    t = _get_raw_double3(src, 'translate')
    jo = _get_raw_double3(src, 'jointOrient')
    s = _get_raw_double3(src, 'scale')
    r = _get_raw_double3(src, 'rotate')
    ra = _get_raw_double3(src, 'rotateAxis')

    t_out = [-_clean_neg_zero(v) for v in t]

    if _is_zero3(r) and _is_zero3(ra):
        return (t_out, [_clean_neg_zero(v) for v in jo], s, True)

    L = _local_matrix(src)
    _, total_r, s_out = _decompose_local(
        L, cmds.getAttr(src + '.rotateOrder'))
    return (t_out, [_clean_neg_zero(v) for v in total_r], s_out, False)


def mirror_root_values(joint, plane, behavior):
    """
    链根骨骼镜像。

    * 平移：以父骨骼世界位置为镜像中心做平面反射（任意父级均适用）
    * 旋转：
        - 父级为 world（无父级）：父级本地帧 D·L·S（等价于世界空间）
        - 父级为其他骨骼/组：世界空间 D·W·S·P⁻¹
    """
    axis = _PLANE_AXIS[plane]

    # --- 平移：以父骨骼世界位置为镜像中心做平面反射 ---
    Cw = cmds.xform(joint, q=True, worldSpace=True, translation=True)
    parents = cmds.listRelatives(joint, parent=True) or []
    if parents:
        Pw = cmds.xform(parents[0], q=True, worldSpace=True, translation=True)
    else:
        Pw = (0.0, 0.0, 0.0)

    mirrored_world = list(Cw)
    mirrored_world[axis] = 2.0 * Pw[axis] - Cw[axis]
    offset = om.MVector(mirrored_world[0] - Pw[0],
                        mirrored_world[1] - Pw[1],
                        mirrored_world[2] - Pw[2])
    if parents:
        W_par = _get_dag(parents[0]).inclusiveMatrix()
        tm_par = om.MTransformationMatrix(W_par)
        R_par_inv = tm_par.rotation().asMatrix().inverse()
        local_t_vec = offset * R_par_inv
        local_t = [local_t_vec.x, local_t_vec.y, local_t_vec.z]
    else:
        local_t = [offset.x, offset.y, offset.z]

    # --- 旋转 ---
    has_non_identity_parent = bool(parents)
    if has_non_identity_parent and behavior:
        W = _get_dag(joint).inclusiveMatrix()
        W2 = _flip_basis_matrix() * W * _reflection_matrix(plane)
        L2 = W2 * W_par.inverse()
    elif has_non_identity_parent:
        # orientation + non-identity parent
        W = _get_dag(joint).inclusiveMatrix()
        W2 = _mirror_position_matrix(W, plane)
        L2 = W2 * W_par.inverse()
    elif behavior:
        L2 = _flip_basis_matrix() * _local_matrix(joint) * _reflection_matrix(plane)
    else:
        L2 = _mirror_position_matrix(_local_matrix(joint), plane)

    _, r, s = _decompose_local(L2, cmds.getAttr(joint + '.rotateOrder'))
    t = [_clean_neg_zero(v) for v in local_t]
    r = [_clean_neg_zero(v) for v in r]
    return t, r, s


def apply_local_values(joint, translate, joint_orient, scale, rotate_order):
    """把镜像结果写入目标骨骼，并清空 rotate / rotateAxis"""
    if not _plug(joint, 'rotateOrder').isLocked:
        cmds.setAttr(joint + '.rotateOrder', rotate_order)
    _set_raw_double3(joint, 'rotate', [0.0, 0.0, 0.0])
    _set_raw_double3(joint, 'rotateAxis', [0.0, 0.0, 0.0])
    _set_raw_double3(joint, 'translate', translate)
    _set_raw_double3(joint, 'jointOrient', joint_orient)
    _set_raw_double3(joint, 'scale', scale)


# ----------------------------------------------------------------------
# 层级与命名
# ----------------------------------------------------------------------

def _list_joint_hierarchy(root):
    """按父先子后顺序返回完整DAG路径的骨骼层级。"""
    result = []
    roots = cmds.ls(root, long=True, type='joint') or []
    if not roots:
        return result

    def walk(j):
        long_j = (cmds.ls(j, long=True, type='joint') or [j])[0]
        result.append(long_j)
        for child in (cmds.listRelatives(long_j, children=True,
                                         type='joint', fullPath=True) or []):
            walk(child)

    walk(roots[0])
    return result


def _mirror_name(name, search, replace):
    """长名/短名都只替换最后一段"""
    short = name.split('|')[-1]
    if search not in short:
        return None
    return short.replace(search, replace, 1)


def _copy_joint_attributes(src, dst):
    """新建目标骨骼时复制显示/标注属性"""
    for attr in ('radius', 'segmentScaleCompensate'):
        if not _plug(dst, attr).isLocked:
            cmds.setAttr(dst + '.' + attr, cmds.getAttr(src + '.' + attr))
    # side 左右互换: 1=Left <-> 2=Right，其他原样复制
    side = cmds.getAttr(src + '.side')
    side_map = {1: 2, 2: 1}
    cmds.setAttr(dst + '.side', side_map.get(side, side))
    cmds.setAttr(dst + '.type', cmds.getAttr(src + '.type'))
    if cmds.getAttr(src + '.type') == 18:  # Other
        cmds.setAttr(dst + '.otherType', cmds.getAttr(src + '.otherType'),
                     type='string')


def _unique_joint_name(name):
    """Always return a scene-unique mirrored root-joint name."""
    if not cmds.objExists(name):
        return name
    index = 1
    candidate = '%s_%03d' % (name, index)
    while cmds.objExists(candidate):
        index += 1
        candidate = '%s_%03d' % (name, index)
    return candidate


# ----------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------

def mirror_joints(roots, plane='YZ', behavior=True,
                  search='L_', replace='R_', hierarchy=True):
    """
    镜像一组骨骼，返回 (成功列表, 警告列表)。

    roots      : 骨骼名称列表
    plane      : 'XY' / 'YZ' / 'XZ'
    behavior   : True=行为镜像（对应 mirrorJoint -mb，左右动画对称）
                 False=仅镜像位置，保持旋转不变
    search     : 命名搜索字符串，如 'L_'、'_l'
    replace    : 替换字符串，如 'R_'、'_r'
    hierarchy  : True 时镜像整个子层级
    """
    if plane not in _PLANE_AXIS:
        raise ValueError("plane 必须是 'XY' / 'YZ' / 'XZ'")

    # 1. 收集所有源骨骼（父先子后，去重，排除重复子树）
    sources = []
    seen = set()
    for root in roots:
        nodes = _list_joint_hierarchy(root) if hierarchy else [root]
        for n in nodes:
            if n not in seen:
                seen.add(n)
                sources.append(n)

    if not sources:
        return [], ['没有选择任何骨骼']

    done = []
    warnings = []
    mapping = {}  # src -> dst

    # 2. 始终新建目标骨骼。与 Maya mirrorJoint 的命名方式一致：
    #    只有镜像链根骨骼在名称冲突时添加后缀，子骨骼不沿用该后缀。
    #    例如已有 B 链时生成 B_root_001 -> B_child -> B_end。
    root_suffix_names = {}
    for src in sources:
        dst_name = _mirror_name(src, search, replace)
        if dst_name is None:
            warnings.append('跳过（命名中找不到 "%s"）: %s' %
                            (search, display_node(src)))
            continue

        src_parent = cmds.listRelatives(src, parent=True, fullPath=True) or []
        src_parent = [(cmds.ls(src_parent[0], long=True) or src_parent)[0]] if src_parent else []
        is_chain_root = not src_parent or src_parent[0] not in sources
        if is_chain_root:
            unique_name = _unique_joint_name(dst_name)
            root_suffix_names[src] = unique_name
        else:
            # The parent relationship and Maya DAG namespace provide the
            # context for the child. Do not append the root's numeric suffix.
            unique_name = dst_name
        create_parent = None
        if not is_chain_root:
            source_parent = src_parent[0]
            create_parent = mapping.get(source_parent)
            # The destination parent is newly created and uniquely named.
            # Keep child names unchanged, matching Maya mirrorJoint behavior:
            # only the mirrored chain root receives a numeric suffix.
        dst = cmds.createNode('joint', name=unique_name, parent=create_parent)
        if is_chain_root and unique_name != dst_name:
            warnings.append('目标根骨骼已存在，已创建为: %s' %
                            display_node(unique_name))
        _copy_joint_attributes(src, dst)
        mapping[src] = dst

    # 3. 设置父子关系（父级在镜像集合内 -> 挂到镜像父级；
    #    否则挂到源骨骼的同一个父节点下）
    for src in sources:
        dst = mapping.get(src)
        if dst is None:
            continue
        src_parent = cmds.listRelatives(src, parent=True, fullPath=True)
        if src_parent:
            src_parent = (cmds.ls(src_parent[0], long=True) or src_parent)[0]
        else:
            src_parent = None

        if src_parent in mapping:
            # Internal children were created with createNode(parent=...). Do
            # not issue a second parent command: Maya can report the child as
            # already parented when long/short DAG names are normalized.
            continue

        # Only a chain root may need to retain an external source parent.
        dst_parent = src_parent
        cur_parent = cmds.listRelatives(dst, parent=True, fullPath=True)
        cur_parent = (cmds.ls(cur_parent[0], long=True) or cur_parent)[0] if cur_parent else None
        if cur_parent != dst_parent:
            if dst_parent:
                cmds.parent(dst, dst_parent)
            else:
                cmds.parent(dst, world=True)

    # 4. 按父先子后顺序写入精确镜像数值
    for src in sources:
        dst = mapping.get(src)
        if dst is None:
            continue
        src_parent = cmds.listRelatives(src, parent=True, fullPath=True)
        is_chain_root = not (src_parent and src_parent[0] in mapping)
        rot_order = cmds.getAttr(src + '.rotateOrder')

        if is_chain_root:
            t, jo, s = mirror_root_values(src, plane, behavior)
            fast = True
        elif behavior:
            t, jo, s, fast = mirror_child_behavior(src)
        else:
            #  Orientation 子级：世界位置镜像，本地相对于已镜像的父级计算
            W_src = _get_dag(src).inclusiveMatrix()
            W_desired = _mirror_position_matrix(W_src, plane)
            dst_parent = mapping[src_parent[0]]
            P_dst = _get_dag(dst_parent).inclusiveMatrix()
            local = W_desired * P_dst.inverse()
            t, jo, s = _decompose_local(local, rot_order)
            t = [_clean_neg_zero(v) for v in t]
            jo = [_clean_neg_zero(v) for v in jo]
            fast = False

        apply_local_values(dst, t, jo, s, rot_order)
        if not fast:
            warnings.append(
                '%s 带有 rotate/rotateAxis，已合并到 jointOrient'
                '（误差 ~1e-16）' % src)
        done.append(dst)

    return done, warnings


def mirror_selected(plane='YZ', behavior=True, search='L_',
                    replace='R_', hierarchy=True):
    """镜像当前选择的骨骼，返回目标骨骼列表"""
    sel = cmds.ls(selection=True, type='joint', long=False) or []
    if not sel:
        cmds.warning('请先选择要镜像的骨骼')
        return []
    done, warnings = mirror_joints(sel, plane, behavior,
                                   search, replace, hierarchy)
    for w in warnings:
        cmds.warning(w)
    if done:
        cmds.select(done, replace=True)
        print('// 镜像完成 %d 根骨骼: %s' % (len(done), ', '.join(done)))
    return done


