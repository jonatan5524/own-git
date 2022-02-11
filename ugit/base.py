
import itertools
import operator
import os
import string
from typing import Deque, Dict, Iterator, Tuple
from collections import deque, namedtuple

from . import data
from . import diff


def init():
    data.init()
    commit("init")
    data.update_ref("HEAD", data.RefValue(
        symbolic=True, value=os.path.join("refs", "heads", "master")))


def create_branch(name: str, object_id: str):
    data.update_ref(os.path.join("refs", "heads", name),
                    data.RefValue(symbolic=False, value=object_id))


def reset(object_id: str):
    data.update_ref("HEAD", data.RefValue(symbolic=False, value=object_id))


def create_tag(name: str, object_id: str):
    data.update_ref(os.path.join("refs", "tags", name),
                    data.RefValue(symbolic=False, value=object_id))


def checkout(name: str):
    object_id = get_object_id(name)
    commit = get_commit(object_id)
    read_tree(commit.tree)

    if is_branch(name):
        head = data.RefValue(
            symbolic=True, value=os.path.join("refs", "heads", name))
    else:
        head = data.RefValue(symbolic=False, value=object_id)

    data.update_ref("HEAD", head, deref=False)


def get_branch_name():
    head = data.get_ref("HEAD", deref=False)

    if not head.symbolic:
        return None

    head = head.value

    assert head.startswith(os.path.join("refs", "heads"))

    return os.path.relpath(head, os.path.join("refs", "heads"))


Commit = namedtuple("Commit", ["tree", "parents", "message"])


def iter_branch_names():
    for refname, _ in data.iter_refs(os.path.join("refs", "heads")):
        yield os.path.relpath(refname, os.path.join("refs", "heads"))


def is_branch(branch: str) -> bool:
    return data.get_ref(os.path.join("refs", "heads", branch)).value is not None


def get_commit(object_id: str) -> Commit:
    parents = []

    commit = data.get_object(object_id, 'commit').decode()
    lines = iter(commit.splitlines())

    for line in itertools.takewhile(operator.truth, lines):
        key, value = line.split(' ', 1)

        if key == 'tree':
            tree = value
        elif key == 'parent':
            parents.append(value)
        else:
            assert False, f'Unknown field {key}'

    message = '\n'.join(lines)
    return Commit(tree=tree, parents=parents, message=message)


def commit(massage: str) -> str:
    commit = f"tree {write_tree()}\n"

    head = data.get_ref("HEAD").value
    if head:
        commit += f"parent {head}\n"

    merge_head = data.get_ref("MERGE_HEAD").value

    if merge_head:
        commit += f"parent {merge_head}\n"
        data.delete_ref("MERGE_HEAD", defer=False)

    commit += "\n"
    commit += f"{massage}\n"

    object_id = data.hash_object(commit.encode(), "commit")

    data.update_ref("HEAD", data.RefValue(symbolic=False, value=object_id))

    return object_id


def write_tree(directory: str = ".") -> str:
    entries = []
    with os.scandir(directory) as dir:
        for entry in dir:
            full_path = os.path.join(directory, entry.name)

            if is_ignored(full_path):
                continue

            if entry.is_file(follow_symlinks=False):
                fmt = "blob"

                with open(full_path, "rb") as f:
                    object_id = data.hash_object(f.read())

            elif entry.is_dir(follow_symlinks=False):
                fmt = "tree"
                object_id = write_tree(full_path)

            entries.append((entry.name, object_id, fmt))

    tree = "".join(f"{fmt} {object_id} {name}\n"
                   for name, object_id, fmt in sorted(entries))

    return data.hash_object(tree.encode(), "tree")


def is_ignored(path: str) -> bool:
    return ".ugit" in path.split("/")


def read_tree(tree_object_id: str):
    _empty_current_directory()

    for path, object_id in get_tree(tree_object_id, base_path="./").items():
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "wb") as f:
            f.write(data.get_object(object_id))


def _empty_current_directory():
    for root, dirnames, filenames in os.walk(".", topdown=False):
        for filename in filenames:
            path = os.path.relpath(os.path.join(root, filename))

            if is_ignored(path) or not os.path.isfile(path):
                continue

            os.remove(path)

        for dirname in dirnames:
            path = os.path.relpath(os.path.join(root, dirname))

            if is_ignored(path):
                continue

            try:
                os.rmdir(path)
            except (FileNotFoundError, OSError):
                pass


def get_tree(object_id: str, base_path: str = "") -> Dict[str, str]:
    result = {}

    for fmt, object_id, name in _iter_tree_entries(object_id):
        assert "/" not in name
        assert name not in ("..", ".")

        path = base_path + name

        if fmt == "blob":
            result[path] = object_id
        elif fmt == "tree":
            result.update(get_tree(object_id, f"{path}/"))
        else:
            assert False, f"Uknown tree entry {fmt}"

    return result


def get_object_id(name: str) -> str:
    if name == "@":
        name = "HEAD"

    ref_to_try = [
        name,
        os.path.join("refs", name),
        os.path.join("refs", "tags", name),
        os.path.join("refs", "heads", name),
    ]

    for ref in ref_to_try:
        if data.get_ref(ref, deref=False).value:
            return data.get_ref(ref).value

    is_hex = all(c in string.hexdigits for c in name)

    if len(name) == 40 and is_hex:
        return name

    assert False, f"Unkown name {name}"


def _iter_tree_entries(object_id: str) -> Iterator[Tuple[str, str, str]]:
    if not object_id:
        return

    tree = data.get_object(object_id, "tree")

    for entry in tree.decode().splitlines():
        fmt, object_id, name = entry.split(" ", 2)
        yield fmt, object_id, name


def iter_commits_and_parents(object_ids: Deque[str]) -> Iterator[str]:
    object_ids = deque(object_ids)
    visited = set()

    while object_ids:
        object_id = object_ids.popleft()

        if not object_id or object_id in visited:
            continue

        visited.add(object_id)

        yield object_id

        commit = get_commit(object_id)
        object_ids.extendleft(commit.parents[:1])
        object_ids.extend(commit.parents[1:])


def get_working_tree() -> Dict[str, str]:
    result = {}

    for root, _, filenames in os.walk("."):
        for filename in filenames:
            path = os.path.relpath(os.path.join(root, filename))

            if is_ignored(path) or not os.path.isfile(path):
                continue

            with open(path, "rb") as f:
                result[path] = data.hash_object(f.read())

    return result


def merge(other: str):
    head = data.get_ref("HEAD").value

    assert head

    commit_head = get_commit(head)
    commit_other = get_commit(other)

    data.update_ref("MERGE_HEAD", data.RefValue(symbolic=False, value=other))

    read_tree_merged(commit_head.tree, commit_other.tree)
    print("Merged in working tree\nPlease commit")


def read_tree_merged(tree_head: str, tree_other: str):
    _empty_current_directory()

    for path, blob in diff.merge_trees(get_tree(tree_head), get_tree(tree_other)).items():
        os.makedirs(f"./{os.path.dirname(path)}", exist_ok=True)

        with open(path, "wb") as f:
            f.write(blob)
