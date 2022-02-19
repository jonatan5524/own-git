import os

from typing import Dict
from . import data
from . import base

REMOTE_REFS_BASE = 'refs/heads/'
LOCAL_REFS_BASE = 'refs/remote/'


def fetch(remote_path: str):
    refs = _get_remote_refs(remote_path, REMOTE_REFS_BASE)

    for object_id in base.iter_objects_in_commits(refs.values()):
        data.fetch_object_if_missing(object_id, remote_path)

    for remote_name, value in refs.items():
        refname = os.path.relpath(remote_name, REMOTE_REFS_BASE)
        data.update_ref(os.path.join(LOCAL_REFS_BASE, refname),
                        data.RefValue(symbolic=False, value=value))


def _get_remote_refs(remote_path: str, prefix: str = '') -> Dict[str, str]:
    with data.change_git_dir(remote_path):
        return {refname: ref.value for refname, ref in data.iter_refs(prefix)}
