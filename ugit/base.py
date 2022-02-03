import os
import string
from typing import Deque, Dict, Iterator, Set, Tuple
from collections import deque, namedtuple

from . import data


def create_tag(name: str, object_id: str):
    data.update_ref(os.path.join("refs", "tags", name), object_id)


def checkout(object_id: str):
    commit = get_commit(object_id)
    read_tree(commit.tree)
    data.update_ref("HEAD", object_id)


Commit = namedtuple("Commit", ["tree", "parent", "message"])


def get_commit(object_id: str) -> Commit:
    parent = None

    commit = data.get_object(object_id, "commit").decode()
    lines = commit.splitlines()

    for line in lines:
        if " " not in line:
            break

        key, value = line.split(" ", 1)

        if key == "tree":
            tree = value
        elif key == "parent":
            parent = value
        else:
            assert False, f"Uknown field {key}"

    if parent == None:
        line = lines[lines.index(line) + 1]

    return Commit(tree=tree, parent=parent, message=line)


def commit(massage: str) -> str:
    commit = f"tree {write_tree()}\n"

    head = data.get_ref("HEAD")
    if head:
        commit += f"parent {head}"

    commit += "\n"
    commit += f"{massage}\n"

    object_id = data.hash_object(commit.encode(), "commit")

    data.update_ref("HEAD", object_id)

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
        if data.get_ref(ref):
            return data.get_ref(ref)

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
        object_ids.appendleft(commit.parent)
