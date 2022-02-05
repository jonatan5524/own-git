
import argparse
import subprocess
import os
import sys
import textwrap
from typing import Dict

from . import base
from . import data
from . import diff


def main():
    args = parse_args()
    args.func(args)


def parse_args():
    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(dest="command")
    commands.required = True

    oid = base.get_object_id

    init_parser = commands.add_parser("init")
    init_parser.set_defaults(func=init)

    hash_object_parser = commands.add_parser("hash-object")
    hash_object_parser.set_defaults(func=hash_object)
    hash_object_parser.add_argument("file")

    cat_file_parser = commands.add_parser("cat-file")
    cat_file_parser.set_defaults(func=cat_file)
    cat_file_parser.add_argument("object", default="@", type=oid)

    write_tree_parser = commands.add_parser("write-tree")
    write_tree_parser.set_defaults(func=write_tree)

    read_tree_parser = commands.add_parser("read-tree")
    read_tree_parser.set_defaults(func=read_tree)
    read_tree_parser.add_argument("tree", default="@", type=oid)

    commit_parser = commands.add_parser("commit")
    commit_parser.set_defaults(func=commit)
    commit_parser.add_argument("-m", "--massage", required=True)

    log_parser = commands.add_parser("log")
    log_parser.set_defaults(func=log)
    log_parser.add_argument("oid", type=oid, default="@", nargs="?")

    checkout_parser = commands.add_parser("checkout")
    checkout_parser.set_defaults(func=checkout)
    checkout_parser.add_argument("commit")

    tag_parser = commands.add_parser("tag")
    tag_parser.set_defaults(func=tag)
    tag_parser.add_argument("name")
    tag_parser.add_argument("oid", default="@", type=oid, nargs="?")

    k_parser = commands.add_parser("k")
    k_parser.set_defaults(func=k)

    branch_parser = commands.add_parser("branch")
    branch_parser.set_defaults(func=branch)
    branch_parser.add_argument("name", nargs="?")
    branch_parser.add_argument("start_point", default="@", type=oid, nargs="?")

    status_parser = commands.add_parser("status")
    status_parser.set_defaults(func=status)

    reset_parser = commands.add_parser("reset")
    reset_parser.set_defaults(func=reset)
    reset_parser.add_argument("commit", type=oid)

    show_parser = commands.add_parser("show")
    show_parser.set_defaults(func=show)
    show_parser.add_argument("oid", default="@", type=oid, nargs="?")

    diff_parser = commands.add_parser("diff")
    diff_parser.set_defaults(func=diff_cmd)
    diff_parser.add_argument("commit", default="@", type=oid, nargs="?")

    return parser.parse_args()


def init(args: argparse.Namespace):
    base.init()
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
    refs = {}

    for refname, ref in data.iter_refs():
        refs.setdefault(ref.value, []).append(refname)

    for object_id in base.iter_commits_and_parents({args.oid}):
        commit = base.get_commit(object_id)
        _print_commit(object_id, commit, refs.get(object_id))

        object_id = commit.parent


def checkout(args: argparse.Namespace):
    base.checkout(args.commit)


def tag(args: argparse.Namespace):
    base.create_tag(args.name, args.oid)


def k(args: argparse.Namespace):
    dot = "digraph commits {\n"

    object_ids = set()

    for refname, ref in data.iter_refs(deref=False):
        dot += f'"{refname}" [shape = note]\n'
        dot += f'"{refname}" -> {ref.value}'

        if not ref.symbolic:
            object_ids.add(ref.value)

    for object_id in base.iter_commits_and_parents(object_ids):
        commit = base.get_commit(object_id)
        dot += f'"{object_id}" [shape=box style=filled label="{object_id[:10]}"]\n'

        if commit.parent:
            dot += f'"{object_id}" -> "{commit.parent}"\n'

    dot += "}"
    print(dot)

    with subprocess.Popen(
        ["dot", "-Tx11", "/dev/stdin"],
            stdin=subprocess.PIPE) as proc:
        proc.communicate(dot.encode())


def branch(args: argparse.Namespace):
    if not args.name:
        current = base.get_branch_name()

        for branch in base.iter_branch_names():
            prefix = "*" if branch == current else ' '
            print(f"{prefix} {branch}")
    else:
        base.create_branch(args.name, args.start_point)
        print(f"Branch {args.name} create at {args.start_point[:10]}")


def status(args: argparse.Namespace):
    head = base.get_object_id("@")
    branch = base.get_branch_name()

    if branch:
        print(f"On branch {branch}")
    else:
        print(f"HEAD detached at {head[:10]}")

    print("\nChanges to be commited:\n")
    head_tree = head and base.get_commit(head).tree

    for path, action in diff.iter_changed_files(base.get_tree(head_tree), base.get_working_tree()):
        print(f"{action:>12}: {path}")


def reset(args: argparse.Namespace):
    base.reset(args.commit)


def show(args: argparse.Namespace):
    if not args.oid:
        return

    commit = base.get_commit(args.oid)
    parent_tree = None

    if commit.parent:
        parent_tree = base.get_commit(commit.parent).tree

    _print_commit(args.oid, commit)
    result = diff.diff_trees(
        base.get_tree(parent_tree),
        base.get_tree(commit.tree)
    )

    sys.stdout.flush()
    sys.stdout.buffer.write(result)


def _print_commit(object_id: str, commit: base.Commit, refs: Dict[str, str] = None):
    refs_str = f"({', '.join(refs)})" if refs else ""

    print(f"commit {object_id}{refs_str}\n")
    print(textwrap.indent(commit.message, "			"))
    print("")


def diff_cmd(args: argparse.Namespace):
    tree = args.commit and base.get_commit(args.commit).tree

    result = diff.diff_trees(base.get_tree(tree), base.get_working_tree())

    sys.stdout.flush()
    sys.stdout.buffer.write(result)
