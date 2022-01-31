#!/usr/bin/env python3

import argparse
import collections
import configparser
import hashlib
import os
import re
import sys
import zlib

argparser = argparse.ArgumentParser()

argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True

argsp = argsubparsers.add_parser("init", help = "initialize a new, empty repository.")
argsp.add_argument(
    "path",
    metavar = "directory",
    nargs = "?",
    default = ".",
    help = "Where to create the repository"
)

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

def cmd_init(args):
    repo_create(args.path)

class GitRepository(object):
    
    worktree = None
    gitdir = None
    config = None

    def __init__(self, path: str, force = False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception("Not a Git repository %s" % path)

        self.config = configparser.ConfigParser()
        config_file = repo_file(self, "config")
        
        if config_file and os.path.exists(config_file):
            self.config.read([config_file])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            version = int(self.config.get("core", "repositoryformatversion"))

            if version != 0:
                raise Exception("Unsupported repositoryformatversion %s" % version)

def repo_path(repo: GitRepository, *path: str) -> str:
    return os.path.join(repo.gitdir, *path)

def repo_file(repo: GitRepository, *path: str, mkdir: bool = False) -> str:
    if repo_dir(repo, *path[:-1], mkdir = mkdir):
        return repo_path(repo, *path)

def repo_dir(repo: GitRepository, *path: str, mkdir: bool = False) -> str:
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if(os.path.isdir(path)):
            return path
        else:
            raise Exception("Not a directory %s" % path)

    if mkdir:
        os.makedirs(path)

        return path

    return None

def repo_default_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()

    config.add_section("core")
    config.set("core", "repositoryformatversion", "0")
    config.set("core", "filemode", "false")
    config.set("core", "base", "false")

    return config

def repo_create(path: str) -> GitRepository:
    repo = GitRepository(path, True)

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception("%s is not a directory!" % path)
        
        if os.listdir(repo.worktree):
            raise Exception("%s is not empty!" % path)
    else:
        os.makedirs(repo.worktree)

    assert(repo_dir(repo, "branches", mkdir = True))
    assert(repo_dir(repo, "objects", mkdir = True))
    assert(repo_dir(repo, "refs", "tags", mkdir = True))
    assert(repo_dir(repo, "branches", "heads", mkdir = True))

    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unamed repository: edit this file 'description' to name the repository.\n")

    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo

def repo_find(path: str = ".", required: bool = True) -> GitRepository:
    path = os.realpath(path)

    if os.path.isdir(os.path.oin(path, ".git")):
        return GitRepository(path)

    parent = os.path.realpath(os.path.join(path, ".."))

    if parent == path:
        if required:
            raise Exception("No git directory.")
        else:
            return None

    return repo_find(parent, required)