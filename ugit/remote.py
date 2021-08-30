from . import data  # pylint: disable=relative-beyond-top-level


def fetch(remote_path):
    print('Will fetch the following refs:')
    for refname, _ in _get_remote_refs(remote_path, 'refs/heads').items():
        print(f'- {refname}')


def _get_remote_refs(remote_path, prefix=''):
    with data.change_git_dir(remote_path):
        return {refname: ref.value for refname, ref in data.iter_refs(prefix)}
