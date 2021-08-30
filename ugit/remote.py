import os
from . import data  # pylint: disable=relative-beyond-top-level

REMOTE_REFS_BASE = 'refs/heads'
LOCAL_REFS_BASE = 'refs/remote'


def fetch(remote_path):
    print('Will fetch the following refs:')
    # get remote refs
    refs = _get_remote_refs(remote_path, REMOTE_REFS_BASE)

    # update local refs
    for remote_name, value in refs.items():
        refname = os.path.relpath(remote_name, REMOTE_REFS_BASE)
        data.update_ref(f'{LOCAL_REFS_BASE}/{refname}',
                        data.RefValue(symbolic=False, value=value))


def _get_remote_refs(remote_path, prefix=''):
    with data.change_git_dir(remote_path):
        return {refname: ref.value for refname, ref in data.iter_refs(prefix)}