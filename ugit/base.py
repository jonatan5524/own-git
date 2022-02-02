import os

from numpy import full

from . import data


def write_tree(directory: str = "."):
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


def is_ignored(path: str):
    return ".ugit" in path.split("/")
