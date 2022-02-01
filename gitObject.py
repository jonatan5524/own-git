#!/usr/bin/env python3

import hashlib
import zlib

from gitRepository import GitRepository, repo_file

class GitObject(object):

    repo = None

    def __init__(self, repo: GitRepository, data: bytes = None):
        self.repo = repo

        if data != None:
            self.deserialize(data)

    def serialize(self) -> bytes:
        raise Exception("Unimplemented")

    def deserialize(self, data: bytes):
        raise Exception("Unimplemented")

class GitBlob(GitObject):
	
    fmt = b'blob'

    def serialize(self):
        return self.blobdata

    def deserialize(self, data: bytes):
        self.blobdata = data 

def object_read(repo: GitRepository, sha: str) -> GitObject:
    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        end_type_index = raw.find(b' ')
        type = raw[0:end_type_index]

        end_size_index = raw.find(b'\x00', end_type_index)
        size = int(raw[end_type_index:end_size_index].decode("ascii"))

        if size != len(raw) - end_size_index - 1:
            raise Exception("Malformed object {0}: bad length".format(sha))

        if type == b'commit':
            ctor = GitCommit
        elif type == b'tree':
            ctor = GitTree        
        elif type == b'tag':
            ctor = GitTag        
        elif type == b'blob':
            ctor = GitBlob
        else:
            raise Exception("Uknown type {0} for object {1}".format(type.decode("ascii"), sha))

        return ctor(repo, raw[end_size_index + 1:])
       
def object_find(repo: GitRepository, name: str, fmt = None, follow: bool = True) -> str:
    return name

def object_write(obj: GitObject, actually_write: bool = True) -> str:
    data = obj.serialize()

    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data

    sha = hashlib.sha1(result).hexdigest()

    if actually_write:
        path = repo_file(obj.repo, "objects", sha[0:2], sha[2:], mkdir = actually_write)

        with open(path, "wb") as f:
            f.write(zlib.compress(result))

    return sha