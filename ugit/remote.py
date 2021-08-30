from . import data  # pylint: disable=relative-beyond-top-level


def fetch(remote_path):
    print('Will fetch the following refs:')
    with data.change_git_dir(remote_path):
        for refname, _ in data.iter_refs('refs/heads'):
            print(f'- {refname}')
