import os
from typing import Dict, Iterator, Tuple

from numpy import full

from . import data


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


def _iter_tree_entries(object_id: str) -> Iterator[Tuple[str, str, str]]:
    if not object_id:
        return

    tree = data.get_object(object_id, "tree")

    for entry in tree.decode().splitlines():
        fmt, object_id, name = entry.split(" ", 2)
        yield fmt, object_id, name
