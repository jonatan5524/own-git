import os
import subprocess

from collections import defaultdict
from typing import Dict, Iterator, List, Tuple
from tempfile import NamedTemporaryFile as Temp

from . import data


def diff_trees(tree_from: Dict[str, str], tree_to: Dict[str, str]) -> bytes:
    output = b""

    for path, object_from, object_to in compare_trees(tree_from, tree_to):
        if object_from != object_to:
            output += bytes(path, "ascii") + b"\n"
            output += diff_blobs(object_from, object_to)

    return output


def compare_trees(*trees: Dict[str, str]) -> Iterator[Tuple[str, str]]:
    entries = defaultdict(lambda: [None] * len(trees))

    for index, tree in enumerate(trees):
        for path, object_id in tree.items():
            entries[path][index] = object_id

    for path, object_ids in entries.items():
        yield (path, *object_ids)


def diff_blobs(object_from: str, object_to: str, path: str = "blob") -> bytes:
    with Temp() as file_from, Temp() as file_to:
        for object_id, f in ((object_from, file_from), (object_to, file_to)):
            if object_id:
                f.write(data.get_object(object_id))
                f.flush()

        with subprocess.Popen(
            ["diff", "--unified", "--show-c-function",
             "--label", os.path.join("a", path), file_from.name,
             "--label", os.path.join("b", path), file_to.name],
            stdout=subprocess.PIPE
        ) as proc:
            output, _ = proc.communicate()

        return output


def iter_changed_files(tree_from: str, tree_to: str) -> Iterator[Tuple[str, str]]:
    for path, object_from, object_to in compare_trees(tree_from, tree_to):
        if object_from != object_to:
            action = (
                "new file" if not object_from else
                "deleted" if not object_to else
                "modified"
            )

            yield path, action
