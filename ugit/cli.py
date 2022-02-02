
import argparse
import os
import sys
import textwrap

from . import base
from . import data


def main():
    args = parse_args()
    args.func(args)


def parse_args():
    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(dest="command")
    commands.required = True

    init_parser = commands.add_parser("init")
    init_parser.set_defaults(func=init)

    hash_object_parser = commands.add_parser("hash-object")
    hash_object_parser.set_defaults(func=hash_object)
    hash_object_parser.add_argument("file")

    cat_file_parser = commands.add_parser("cat-file")
    cat_file_parser.set_defaults(func=cat_file)
    cat_file_parser.add_argument("object")

    write_tree_parser = commands.add_parser("write-tree")
    write_tree_parser.set_defaults(func=write_tree)

    read_tree_parser = commands.add_parser("read-tree")
    read_tree_parser.set_defaults(func=read_tree)
    read_tree_parser.add_argument("tree")

    commit_parser = commands.add_parser("commit")
    commit_parser.set_defaults(func=commit)
    commit_parser.add_argument("-m", "--massage", required=True)

    log_parser = commands.add_parser("log")
    log_parser.set_defaults(func=log)
    log_parser.add_argument("oid", nargs="?")

    checkout_parser = commands.add_parser("checkout")
    checkout_parser.set_defaults(func=checkout)
    checkout_parser.add_argument("oid")

    return parser.parse_args()


def init(args: argparse.Namespace):
    data.init()
    print(
        f"Initialized empty ugit repository in {os.path.join(os.getcwd(), data.GIT_DIR)}")


def hash_object(args: argparse.Namespace):
    with open(args.file, "rb") as f:
        print(data.hash_object(f.read()))


def cat_file(args: argparse.Namespace):
    sys.stdout.flush()
    sys.stdout.buffer.write(data.get_object(args.object, expected=None))


def write_tree(args: argparse.Namespace):
    print(base.write_tree())


def read_tree(args: argparse.Namespace):
    base.read_tree(args.tree)


def commit(args: argparse.Namespace):
    print(base.commit(args.massage))


def log(args: argparse.Namespace):
    object_id = args.oid or data.get_head()

    while object_id:
        commit = base.get_commit(object_id)

        print(f"commit {object_id}\n")
        print(textwrap.indent(commit.message, "			"))
        print("")

        object_id = commit.parent


def checkout(args: argparse.Namespace):
    base.checkout(args.oid)
