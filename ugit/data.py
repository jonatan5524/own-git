import hashlib
import os

GIT_DIR = ".ugit"


def init():
    os.makedirs(GIT_DIR)
    os.makedirs(os.path.join(GIT_DIR, "objects"))


def hash_object(raw_file: bytes, fmt: str = "blob") -> str:
    obj = fmt.encode() + b'\x00' + raw_file
    object_id = hashlib.sha1(obj).hexdigest()

    with open(os.path.join(GIT_DIR, "objects", object_id), "wb") as f:
        f.write(obj)

    return object_id


def get_object(object_id: str, expected: str = "blob") -> bytes:
    with open(os.path.join(GIT_DIR, "objects", object_id), "rb") as f:
        obj = f.read()

    fmt, _, content = obj.partition(b'\x00')
    fmt = fmt.decode()

    if expected is not None:
        assert(fmt == expected, f"Expected {expected}, got {fmt}")

    return content
