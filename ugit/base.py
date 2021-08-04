import os

from . import data


def write_tree(directory='.'):
    '''Write directory to store recurisvely.'''
    with os.scandir(directory) as it:
        for entry in it:
            full = f'{directory}/{entry.name}'
            if is_ignored(full):
                continue
            if entry.is_file(follow_symlinks=False):
                with open(full, 'rb') as f:
                    hashed = data.hash_object(f.read())
                    print(hashed, full)
            elif entry.is_dir(follow_symlinks=False):
                write_tree(full)


def is_ignored(path):
    return '.ugit' in path.split('/')
