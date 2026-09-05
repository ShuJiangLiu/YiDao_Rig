# -*- coding: utf-8 -*-
"""Safe inspection and cleanup for Maya bind-pose nodes."""
from __future__ import print_function

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None


def _is_bind_pose(node):
    """Return whether a dagPose node is marked as a bind pose."""
    try:
        value = cmds.getAttr(node + '.bindPose')
        return bool(value)
    except Exception:
        try:
            return bool(cmds.dagPose(node, query=True, bindPose=True))
        except Exception:
            return False


def list_bind_poses():
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    return [node for node in (cmds.ls(type='dagPose', long=True) or [])
            if _is_bind_pose(node)]


def _pose_members(pose):
    try:
        members = cmds.dagPose(pose, query=True, members=True) or []
        return set(cmds.ls(members, long=True) or members), True
    except Exception:
        return set(), False


def _direct_skin_connections(pose):
    try:
        connections = cmds.listConnections(
            pose, source=False, destination=True, type='skinCluster') or []
        return set(connections), True
    except Exception:
        return set(), False


def used_bind_poses():
    """Find poses conservatively associated with active skinClusters."""
    poses = list_bind_poses()
    used = set()
    uncertain = False
    for pose in poses:
        connections, known = _direct_skin_connections(pose)
        if not known:
            uncertain = True
        if connections:
            used.add(pose)

    influences = set()
    for cluster in cmds.ls(type='skinCluster', long=True) or []:
        try:
            cluster_influences = cmds.skinCluster(
                cluster, query=True, influence=True) or []
            influences.update(cmds.ls(
                cluster_influences, long=True) or cluster_influences)
        except Exception:
            uncertain = True
    # Query each pose's members once instead of querying dagPose once per
    # influence. Shared influences conservatively mark the pose as used.
    for pose in poses:
        members, known = _pose_members(pose)
        if not known:
            uncertain = True
        if members.intersection(influences):
            used.add(pose)
    if uncertain:
        # A failed association query must never make a pose look unused.
        return set(poses)
    return set(used)


def inspect_bind_poses():
    poses = list_bind_poses()
    used = used_bind_poses()
    unused = [pose for pose in poses if pose not in used]
    active = [pose for pose in poses if pose in used]
    return {'all': poses, 'used': active, 'unused': unused}


def _pose_matrix_signature(pose):
    """Return a comparable member/matrix signature, or None if unreadable."""
    try:
        members = cmds.dagPose(pose, query=True, members=True) or []
        members = [
            (cmds.ls(member, long=True) or [member])[0]
            for member in members]
        indices = cmds.getAttr(
            pose + '.worldMatrix', multiIndices=True) or []
        matrices = [cmds.getAttr(
            '%s.worldMatrix[%d]' % (pose, index)) for index in indices]
    except Exception:
        return None
    if members and matrices and not isinstance(matrices[0], (list, tuple)):
        if len(matrices) == len(members) * 16:
            matrices = [matrices[index:index + 16]
                        for index in range(0, len(matrices), 16)]
        elif len(members) == 1 and len(matrices) == 16:
            matrices = [matrices]
    if len(members) != len(matrices):
        return None

    def normalize(value):
        if isinstance(value, (list, tuple)):
            return tuple(normalize(item) for item in value)
        if isinstance(value, float):
            return round(value, 8)
        return value

    return tuple(sorted(zip(members, map(normalize, matrices))))


def _skeleton_root(node):
    """Return the top joint/transform in the member's DAG hierarchy."""
    current = node
    while True:
        try:
            parents = cmds.listRelatives(
                current, parent=True, fullPath=True) or []
        except Exception:
            return None
        if not parents:
            return current
        parent = parents[0]
        try:
            if cmds.nodeType(parent) != 'joint':
                return current
        except Exception:
            return None
        current = parent


def _pose_skeleton_key(pose):
    members, known = _pose_members(pose)
    if not known or not members:
        return None
    roots = set()
    for member in members:
        root = _skeleton_root(member)
        if not root:
            return None
        roots.add(root)
    return tuple(sorted(roots))


def _is_at_pose(pose):
    try:
        mismatches = cmds.dagPose(pose, query=True, atPose=True) or []
        return not mismatches, True
    except Exception:
        return False, False


def _rewire_pose_skin_connections(old_pose, new_pose):
    """Move explicit skinCluster message connections to the merged pose."""
    try:
        destinations = cmds.listConnections(
            old_pose + '.message', source=False, destination=True,
            plugs=True) or []
    except Exception:
        return False
    for destination in destinations:
        node = destination.split('.', 1)[0]
        try:
            if cmds.nodeType(node) != 'skinCluster':
                continue
            cmds.connectAttr(
                new_pose + '.message', destination, force=True)
        except Exception:
            return False
    return True


def merge_identical_bind_poses():
    """Merge active poses from one skeleton while preserving bind data.

    Maya's ``dagPose.worldMatrix`` multi attribute cannot be read reliably in
    every Maya version.  Instead, require every pose to report ``atPose``.
    That query is Maya's own validation that each stored member matrix matches
    the current scene.  The missing members can then be added to one pose
    without inventing or overwriting any stored bind values.
    """
    info = inspect_bind_poses()
    groups = {}
    unreadable = []
    not_at_pose = []
    for pose in info['used']:
        key = _pose_skeleton_key(pose)
        members, members_known = _pose_members(pose)
        if key is None or not members_known:
            unreadable.append(pose)
            continue
        at_pose, known = _is_at_pose(pose)
        if not known:
            unreadable.append(pose)
            continue
        if not at_pose:
            not_at_pose.append(pose)
            continue
        groups.setdefault(key, []).append((pose, members))

    removed = []
    for entries in groups.values():
        if len(entries) < 2:
            continue
        canonical, canonical_members = max(
            entries, key=lambda item: len(item[1]))
        canonical_data = set(canonical_members)
        all_members = set()
        for _pose, members in entries:
            all_members.update(members)

        # Every pose in this group has already been checked with atPose.
        # Therefore the current scene contains the correct stored values for
        # any members that are missing from the canonical pose.
        missing = all_members.difference(canonical_data)
        if missing:
            previous_selection = cmds.ls(selection=True, long=True) or []
            try:
                cmds.select(list(missing), replace=True)
                cmds.dagPose(
                    addToPose=True, selection=True, name=canonical)
            except Exception:
                unreadable.extend(pose for pose, _members in entries)
                continue
            finally:
                if previous_selection:
                    cmds.select(previous_selection, replace=True)
                else:
                    cmds.select(clear=True)

        for duplicate, _duplicate_members in entries:
            if duplicate == canonical:
                continue
            if not _rewire_pose_skin_connections(duplicate, canonical):
                continue
            try:
                cmds.delete(duplicate)
                removed.append(duplicate)
            except Exception:
                pass
    return {
        'removed': removed,
        'unreadable': unreadable,
        'not_at_pose': not_at_pose,
        'remaining': list_bind_poses(),
    }


def cleanup_and_merge_bind_poses():
    """Remove unused poses, then merge identical active poses."""
    cleanup = cleanup_unused_bind_poses()
    merged = merge_identical_bind_poses()
    return {
        'removed_unused': cleanup['removed'],
        'removed_duplicates': merged['removed'],
        'unreadable': merged['unreadable'],
        'not_at_pose': merged['not_at_pose'],
        'remaining': merged['remaining'],
    }


def cleanup_unused_bind_poses():
    """Delete only bind poses not associated with active skinClusters."""
    info = inspect_bind_poses()
    unused = info['unused']
    if unused:
        cmds.delete(unused)
    remaining = list_bind_poses()
    return {
        'removed': unused,
        'remaining': remaining,
        'used': [pose for pose in remaining if pose in info['used']],
    }


def undo_chunk(label):
    class _Chunk(object):
        def __enter__(self):
            cmds.undoInfo(openChunk=True, chunkName=label)
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            cmds.undoInfo(closeChunk=True)
    return _Chunk()
