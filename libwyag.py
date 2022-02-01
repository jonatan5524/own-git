#!/usr/bin/env python3

import argparse
from io import BufferedReader
import sys

from gitObject import GitBlob, object_find, object_read, object_write
from gitRepository import GitRepository, repo_create, repo_find

argparser = argparse.ArgumentParser()

argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True

def main(argv = sys.argv[1:]):
    args = argparser.parse_args(argv)

    if args.command == "add":
        cmd_add(args)
    elif args.command == "cat-file":
        cmd_cat_file(args)
    elif args.command == "checkout":
        cmd_checkout(args)
    elif args.command == "commit":
        cmd_commit(args)
    elif args.command == "hash-object":
        cmd_hash_object(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "log":
        cmd_log(args)
    elif args.command == "ls-tree":
        cmd_ls_tree(args)
    elif args.command == "merge":
        cmd_merge(args)
    elif args.command == "rebase":
        cmd_rebase(args)
    elif args.command == "rev-parse":
        cmd_rev_parse(args)
    elif args.command == "rm":
        cmd_rm(args)
    elif args.command == "show-ref":
        cmd_show_ref(args)
    elif args.command == "tag":
        cmd_tag(args)

argsp = argsubparsers.add_parser("init", help = "initialize a new, empty repository.")
argsp.add_argument(
    "path",
    metavar = "directory",
    nargs = "?",
    default = ".",
    help = "Where to create the repository"
)

def cmd_init(args: argparse.Namespace):
    repo_create(args.path)

argsp = argsubparsers.add_parser("cat-file", help = "Provide content of repository objects")
argsp.add_argument(
    "type",
    metavar = "type",
    choices = ["blob", "commit", "tag", "tree"],
    help = "Specify the type"
)
argsp.add_argument(
    "object",
    metavar = "object",
    help = "The object to display"
)

def cmd_cat_file(args: argparse.Namespace):
    repo = repo_find()
    cat_file(repo, args.object, fmt = args.type.encode())

def cat_file(repo: GitRepository, obj: str, fmt = None):
    git_object = object_read(repo, object_find(repo, obj, fmt = fmt))
    sys.stdout.buffer.write(git_object.serialize())

argsp = argsubparsers.add_parser(
    "hash-object",
    help = "Compute object ID and optionally creates a blob from a file"
)
argsp.add_argument(
    "-t",
    metavar = "type",
    dest = "type",
    choices = ["blob", "commit", "tag", "tree"],
    default = "blob",
    help = "Specift the type"
)
argsp.add_argument(
    "-w",
    dest = "write",
    action = "store_true",
    help = "Actually write the object into the database"
)
argsp.add_argument(
    "path",
    help = "Read the object from <file>"
)

def cmd_hash_object(args: argparse.Namespace):
    if args.write:
        repo = GitRepository(".")
    else:
        repo = None

    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)

def object_hash(fd: BufferedReader, type: str, repo: GitRepository = None) -> str:
    data = fd.read()

    if type == b'commit':
        obj = GitCommit(repo, data)
    elif type == b'tree':
        obj = GitTree(repo, data)  
    elif type == b'tag':
        obj = GitTag(repo, data)
    elif type == b'blob':
        obj = GitBlob(repo, data)
    else:
        raise Exception("Unkown type %s!" % fmt)

    return object_write(obj, repo != None)
        
    