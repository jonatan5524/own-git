from contextlib import contextmanager
import hashlib
import json
import os
import shutil
from typing import Iterator, Tuple
import zlib

from collections import namedtuple

GIT_DIR = None


@contextmanager
def change_git_dir(new_dir):
    global GIT_DIR
    old_dir = GIT_DIR
    GIT_DIR = f'{new_dir}/.ugit'
    yield
    GIT_DIR = old_dir


def init():
    os.makedirs(GIT_DIR)
    os.makedirs(os.path.join(GIT_DIR, "objects"))


def hash_object(raw_file: bytes, fmt: str = "blob") -> str:
    obj = fmt.encode() + b' ' + str(len(raw_file)).encode() + b'\x00' + raw_file
    object_id = hashlib.sha1(obj).hexdigest()

    path = os.path.join(GIT_DIR, "objects", object_id[0:2], object_id[2:])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(zlib.compress(obj))

    return object_id


def get_object(object_id: str, expected: str = "blob") -> bytes:
    with open(os.path.join(GIT_DIR, "objects", object_id[0:2], object_id[2:]), "rb") as f:
        obj = zlib.decompress(f.read())

    space_index = obj.find(b' ')
    fmt = obj[0:space_index].decode("ascii")

    null_index = obj.find(b'\x00', space_index)
    size = int(obj[space_index:null_index].decode("ascii"))

    content = obj[null_index + 1:]

    assert size == len(content), f"bad length for object: {object_id}"

    if expected is not None:
        assert fmt == expected, f"Expected {expected}, got {fmt}"

    return content


RefValue = namedtuple("RefValue", ["symbolic", "value"])


def update_ref(ref: str, refValue: RefValue, deref: bool = True):
    ref = _get_ref_internal(ref, deref)[0]

    assert refValue.value

    if refValue.symbolic:
        value = f"ref: {refValue.value}"
    else:
        value = refValue.value

    ref_path = os.path.join(GIT_DIR, ref)
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)

    with open(ref_path, "w") as f:
        f.write(value)


def get_ref(ref: str, deref=True) -> RefValue:
    return _get_ref_internal(ref, deref)[1]


def _get_ref_internal(ref: str, deref) -> Tuple[str, RefValue]:
    ref_path = os.path.join(GIT_DIR, ref)
    value = None

    if os.path.isfile(ref_path):
        with open(ref_path, "r") as f:
            value = f.read().strip()

    symbolic = bool(value) and value.startswith("ref:")

    if symbolic:
        value = value.split(":", 1)[1].strip()

        if deref:
            return _get_ref_internal(value, deref)

    return ref, RefValue(symbolic=symbolic, value=value)


def iter_refs(prefix: str = "", deref: bool = True) -> Iterator[Tuple[str, RefValue]]:
    refs = ["HEAD", "MERGE_HEAD"]

    for root, _, filenames in os.walk(os.path.join(GIT_DIR, "refs")):
        root = os.path.relpath(root, GIT_DIR)
        refs.extend(os.path.join(root, name) for name in filenames)

    for refname in refs:
        if not refname.startswith(prefix):
            continue
        ref = get_ref(refname, deref=deref)

        if ref.value:
            yield refname, ref


def delete_ref(ref: str, defer=True):
    ref = _get_ref_internal(ref, defer)[0]
    os.remove(os.path.join(GIT_DIR, ref))


def object_exists(object_id: str) -> bool:
    return os.path.isfile(os.path.join(GIT_DIR, "objects", object_id))


def fetch_object_if_missing(object_id: str, remote_git_dir: str):
    if object_exists(object_id):
        return

    remote_git_dir += "/.ugit"

    os.makedirs(os.path.join(GIT_DIR, "objects",
                object_id[:2]), exist_ok=True)

    shutil.copy(os.path.join(remote_git_dir, "objects", object_id[:2], object_id[2:]),
                os.path.join(GIT_DIR, "objects", object_id[:2], object_id[2:]))


def push_object(object_id: str, remote_git_dir: str):
    remote_git_dir += "/.ugit"

    os.makedirs(os.path.join(remote_git_dir, "objects",
                object_id[:2]), exist_ok=True)

    shutil.copy(os.path.join(GIT_DIR, "objects", object_id[:2], object_id[2:]),
                os.path.join(remote_git_dir, "objects", object_id[:2], object_id[2:]))


@contextmanager
def get_index():
    index = {}

    if os.path.isfile(os.path.join(GIT_DIR, "index")):
        with open(os.path.join(GIT_DIR, "index")) as f:
            index = json.load(f)

    yield index

    with open(os.path.join(GIT_DIR, "index"), "w") as f:
        json.dump(index, f)
