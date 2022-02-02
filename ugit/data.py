import hashlib
import os
import zlib

GIT_DIR = ".ugit"


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
