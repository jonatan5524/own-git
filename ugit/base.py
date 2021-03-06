
from genericpath import exists
import itertools
import operator
import os
import string
from typing import Deque, Dict, Iterator, List, Tuple
from collections import deque, namedtuple

from . import data
from . import diff


def init():
    data.init()
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
    read_tree(commit.tree, update_working=True)

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


def write_tree() -> str:
    index_as_tree = {}

    with data.get_index() as index:
        for path, object_id in index.items():
            dirpath, filename = os.path.split(path)

            current = index_as_tree

            for direname in dirpath:
                current = current.setdefault(direname, {})

            current[filename] = object_id

    def write_tree_recursive(tree_dict: Dict[str, str]) -> str:
        entries = []

        for name, value in tree_dict.items():
            if type(value) is dict:
                type_ = 'tree'

                object_id = write_tree_recursive(value)
            else:
                type_ = 'blob'
                object_id = value

            entries.append((name, object_id, type_))

        tree = ''.join(f'{type_} {object_id} {name}\n'
                       for name, object_id, type_ in sorted(entries))

        return data.hash_object(tree.encode(), "tree")

    return write_tree_recursive(index_as_tree)


def is_ignored(path: str) -> bool:
    return ".ugit" in path.split("/")


def read_tree(tree_object_id: str, update_working: bool = False):
    with data.get_index() as index:
        index.clear()
        index.update(get_tree(tree_object_id))

        if update_working:
            _checkout_index(index)


def read_tree_merged(tree_base: str, tree_head: str, tree_other: str, update_working: bool = False):
    with data.get_index() as index:
        index.clear()
        index.update(diff.merge_trees(
            get_tree(tree_base),
            get_tree(tree_head),
            get_tree(tree_other)
        ))

        if update_working:
            _checkout_index(index)


def _checkout_index(index):
    _empty_current_directory()

    for path, object_id in index.items():
        os.makedirs(os.path.dirname(os.path.join("./", path)), exist_ok=True)

        with open(path, "wb") as f:
            f.write(data.get_object(object_id, "blob"))


def get_index_tree():
    with data.get_index() as index:
        return index


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


def iter_objects_in_commits(object_ids: List[str]) -> Iterator[str]:
    visited = set()

    def iter_object_in_tree(object_id: str):
        visited.add(object_id)

        yield object_id

        for type_, object_id, _ in _iter_tree_entries(object_id):
            if object_id not in visited:
                if type_ == "tree":
                    yield from iter_object_in_tree(object_id)
                else:
                    visited.add(object_id)
                    yield object_id

    for object_id in iter_commits_and_parents(object_ids):
        yield object_id

        commit = get_commit(object_id)

        if commit.tree not in visited:
            yield from iter_object_in_tree(commit.tree)


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

    merge_base = get_merge_base(other, head)
    commit_other = get_commit(other)

    if merge_base == head:
        read_tree(commit_other.tree, update_working=True)
        data.update_ref('HEAD', data.RefValue(symbolic=False, value=other))
        print('Fast-forward merge, no need to commit')

        return

    data.update_ref("MERGE_HEAD", data.RefValue(symbolic=False, value=other))

    commit_base = get_commit(merge_base)
    commit_head = get_commit(head)

    read_tree_merged(commit_base.tree, commit_head.tree,
                     commit_other.tree, update_working=True)
    print("Merged in working tree\nPlease commit")


def get_merge_base(object_id: str, second_object_id: str) -> str:
    parents = set(iter_commits_and_parents({object_id}))

    for oid in iter_commits_and_parents({second_object_id}):
        if oid in parents:
            return oid


def is_ancestor_of(commit: str, maybe_ancestor: str) -> bool:
    return maybe_ancestor in iter_commits_and_parents({commit})


def add(filenames: List[str]):
    def add_file(filename: str):
        filename = os.path.relpath(filename)

        with open(filename, 'rb') as f:
            object_id = data.hash_object(f.read())

        index[filename] = object_id

    def add_directory(dirname: str):
        for root, _, filename in os.walk(dirname):
            for filename in filenames:
                path = os.path.relpath(os.path.join(root, filename))

                if is_ignored(path) or not os.path.isfile(path):
                    continue

                add_file(path)

    with data.get_index() as index:
        for name in filenames:
            if os.path.isfile(name):
                add_file(name)
            elif os.path.isdir(name):
                add_directory(name)
