import hashlib
import os

GIT_DIR = ".ugit"


def init():
    os.makedirs(GIT_DIR)
    os.makedirs(os.path.join(GIT_DIR, "objects"))


def hash_object(raw_file: bytes) -> str:
    object_id = hashlib.sha1(raw_file).hexdigest()

    with open(os.path.join(GIT_DIR, "objects", object_id), "wb") as f:
        f.write(raw_file)

    return object_id
