import os
import itertools
import operator
import string

from collections import namedtuple

from . import data


def write_tree(directory='.'):
    '''Write directory to store recurisvely.'''
    entries = []
    with os.scandir(directory) as it:
        for entry in it:
            full = f'{directory}/{entry.name}'
            if is_ignored(full):
                continue
            if entry.is_file(follow_symlinks=False):
                type_ = 'blob'
                with open(full, 'rb') as f:
                    oid = data.hash_object(f.read())
            elif entry.is_dir(follow_symlinks=False):
                type_ = 'tree'
                oid = write_tree(full)
            entries.append((entry.name, oid, type_))
    tree = ''.join(f'{type_} {oid} {name}\n' for name,
                   oid, type_ in sorted(entries))
    return data.hash_object(tree.encode(), 'tree')


def _iter_tree_entries(oid):
    '''Iterate hash object tree.'''
    if not oid:
        return
    tree = data.get_object(oid, 'tree')
    for entry in tree.decode().splitlines():
        type_, oid, name = entry.split(' ', 2)
        yield type_, oid, name


def get_tree(oid, base_path=''):
    '''Get tree from hash object oid.'''
    result = {}
    for type_, oid, name in _iter_tree_entries(oid):
        assert '/' not in name
        assert name not in ('..', '.')
        path = base_path + name
        if type_ == 'blob':
            result[path] = oid
        elif type_ == 'tree':
            result.update(get_tree(oid, f'{path}/'))
        else:
            raise Exception(f'Unknown tree entry {type_}')
    return result


def _empty_current_directory():
    for root, dirnames, filenames in os.walk('.', topdown=False):
        for filename in filenames:
            path = os.path.relpath(f'{root}/{filename}')
            if is_ignored(path) or not os.path.isfile(path):
                continue
            try:
                os.rmdir(path)
            except (FileNotFoundError, OSError):
                pass


def read_tree(tree_oid):
    '''Get tree and write tree back to directory.'''
    _empty_current_directory()
    for path, oid in get_tree(tree_oid, base_path='./').items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data.get_object(oid))


def commit(message):
    HEAD = data.get_ref('HEAD')
    commit = ''.join([
        f'tree {write_tree()}\n',
        '\n' if not HEAD else f'parent {HEAD}\n\n',
        f'{message}\n'
    ])
    oid = data.hash_object(commit.encode(), 'commit')
    data.update_ref('HEAD', oid)
    return oid


def checkout(oid):
    commit = get_commit(oid)
    read_tree(commit.tree)
    data.update_ref('HEAD', oid)


def create_tag(name, oid):
    data.update_ref(f'refs/tags/{name}', oid)


Commit = namedtuple('Commit', ['tree', 'parent', 'message'])


def get_commit(oid):
    parent = None

    commit = data.get_object(oid, 'commit').decode()
    lines = iter(commit.splitlines())
    for line in itertools.takewhile(operator.truth, lines):
        k, v = line.split(' ', 1)
        if k == 'tree':
            tree = v
        elif k == 'parent':
            parent = v
        else:
            raise Exception(f'Unknown field {k}')
    message = '\n'.join(lines)
    return Commit(tree=tree, parent=parent, message=message)


def get_oid(name):
    # name is ref
    refs_to_search = [
        f'{name}',
        f'refs/{name}',
        f'refs/tags/{name}',
        f'refs/heads/{name}'
    ]
    for ref in refs_to_search:
        searched_ref = data.get_ref(ref)
        if searched_ref:
            return searched_ref
    # name is sha1
    is_hex = all(c in string.hexdigits for c in name)
    if len(name) == 40 and is_hex:
        return name

    raise Exception(f'Unknown name {name}')


def is_ignored(path):
    return '.ugit' in path.split('/')
