# -*- coding: utf-8 -*-
"""Read-only diagnostic report for Maya bindPose nodes.

Run in Maya's Python tab with:
    execfile(r'.../diagnose_bind_poses.py')
or call diagnose_bind_poses() after importing this module.
"""
from __future__ import print_function

import maya.cmds as cmds


def _long_nodes(nodes):
    result = []
    for node in nodes or []:
        matches = cmds.ls(node, long=True) or []
        result.extend(matches or [node])
    return list(dict.fromkeys(result))


def _bind_poses():
    result = []
    for pose in cmds.ls(type='dagPose', long=True) or []:
        try:
            if cmds.getAttr(pose + '.bindPose'):
                result.append(pose)
        except Exception:
            pass
    return result


def _matrix_value(pose, index):
    value = cmds.getAttr('%s.worldMatrix[%d]' % (pose, index))
    while (isinstance(value, (list, tuple)) and len(value) == 1 and
           isinstance(value[0], (list, tuple))):
        value = value[0]
    return value


def _pose_data(pose):
    members = cmds.dagPose(pose, query=True, members=True) or []
    members = _long_nodes(members)
    indices = cmds.getAttr(
        pose + '.worldMatrix', multiIndices=True) or []
    matrices = [_matrix_value(pose, index) for index in indices]
    if len(members) != len(matrices):
        return None
    return dict(zip(members, matrices))


def _skeleton_root(node):
    current = node
    while True:
        parents = cmds.listRelatives(
            current, parent=True, fullPath=True) or []
        if not parents or cmds.nodeType(parents[0]) != 'joint':
            return current
        current = parents[0]


def _pose_roots(data):
    return set(_skeleton_root(member) for member in data)


def _is_at_pose(pose):
    try:
        return not bool(cmds.dagPose(
            pose, query=True, atPose=True) or []), True
    except Exception:
        return False, False


def _matrix_equal(first, second, tolerance=0.00001):
    if len(first) != len(second):
        return False
    return all(abs(a - b) <= tolerance
               for a, b in zip(first, second))


def _skin_info():
    clusters = []
    influences = set()
    for cluster in cmds.ls(type='skinCluster', long=True) or []:
        try:
            joints = _long_nodes(cmds.skinCluster(
                cluster, query=True, influence=True) or [])
            geometry = cmds.skinCluster(
                cluster, query=True, geometry=True) or []
        except Exception as exc:
            print('skinCluster 读取失败: %s (%s)' % (cluster, exc))
            continue
        influences.update(joints)
        clusters.append((cluster, set(joints), geometry))
    return clusters, influences


def diagnose_bind_poses():
    poses = _bind_poses()
    clusters, all_influences = _skin_info()
    reports = {}

    print('\n========== Bind Pose 诊断开始 ==========')
    print('Bind Pose 数量: %d' % len(poses))
    print('skinCluster 数量: %d' % len(clusters))

    for pose in poses:
        try:
            data = _pose_data(pose)
        except Exception as exc:
            print('\n[%s]' % pose)
            print('状态: 无法读取成员或保存矩阵 (%s)' % exc)
            reports[pose] = None
            continue

        if data is None:
            print('\n[%s]' % pose)
            print('状态: 成员数量与 worldMatrix 数量不一致')
            reports[pose] = None
            continue

        roots = _pose_roots(data)
        direct_clusters = cmds.listConnections(
            pose + '.message', source=False, destination=True,
            type='skinCluster') or []
        used_by_influence = set(data).intersection(all_influences)
        at_pose, at_pose_known = _is_at_pose(pose)
        reports[pose] = {
            'data': data,
            'roots': roots,
            'at_pose': at_pose,
            'at_pose_known': at_pose_known,
        }

        print('\n[%s]' % pose)
        print('成员数量: %d' % len(data))
        print('骨架根节点:')
        for root in sorted(roots):
            print('  %s' % root)
        print('直接关联 skinCluster: %s' % (direct_clusters or '无'))
        print('与当前 skinCluster 影响骨骼重合数量: %d' %
              len(used_by_influence))
        if at_pose_known:
            print('当前是否处于该 Bind Pose: %s' %
                  ('是' if at_pose else '否'))
        else:
            print('当前是否处于该 Bind Pose: 无法判断')

    print('\n========== 两两兼容性诊断 ==========')
    for index in range(len(poses)):
        for other_index in range(index + 1, len(poses)):
            first = poses[index]
            second = poses[other_index]
            report_a = reports.get(first)
            report_b = reports.get(second)
            print('\n%s  <->  %s' % (first, second))

            if not report_a or not report_b:
                print('结果: 无法判断，至少一个 Bind Pose 数据不可读')
                continue

            data_a = report_a['data']
            data_b = report_b['data']
            roots_same = report_a['roots'] == report_b['roots']
            members_a = set(data_a)
            members_b = set(data_b)
            members_compatible = (
                members_a.issuperset(members_b) or
                members_b.issuperset(members_a))
            common = members_a.intersection(members_b)
            matrices_same = all(_matrix_equal(data_a[member], data_b[member])
                                for member in common)
            poses_known_and_current = (
                report_a['at_pose_known'] and report_b['at_pose_known'] and
                report_a['at_pose'] and report_b['at_pose'])

            print('骨架根节点相同: %s' % ('是' if roots_same else '否'))
            print('成员集合可包含: %s' %
                  ('是' if members_compatible else '否'))
            print('共同骨骼数量: %d' % len(common))
            print('共同骨骼保存矩阵一致: %s' %
                  ('是' if matrices_same else '否'))
            print('两个节点当前都处于保存姿势: %s' %
                  ('是' if poses_known_and_current else '否'))

            can_merge = (roots_same and members_compatible and
                         matrices_same and poses_known_and_current)
            print('诊断结论: %s' %
                  ('可以作为合并候选' if can_merge else '暂不建议合并'))

    print('\n========== Bind Pose 诊断结束 ==========\n')
    return reports


if __name__ == '__main__':
    diagnose_bind_poses()
