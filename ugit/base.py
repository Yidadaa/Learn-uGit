import os
import itertools
import operator
import string

from collections import namedtuple, deque
from sys import gettrace

from . import data  # pylint: disable=relative-beyond-top-level
from . import diff  # pylint: disable=relative-beyond-top-level


def init():
    data.init()
    data.update_ref('HEAD', data.RefValue(
        symbolic=True, value='refs/heads/master'))


def write_tree():
    index_as_tree = {}
    with data.get_index() as index:
        for path, oid in index.items():
            path = path.split('/')
            dirpath, filename = path[:-1], path[-1]

            # convert flat index to tree-like index
            current = index_as_tree
            for dirname in dirpath:
                current = current.setdefault(dirname, {})
            current[filename] = oid

    def write_tree_recursive(tree_dict: dict):
        entries = []
        for name, value in tree_dict.items():
            if type(value) is dict:
                type_ = 'tree'
                oid = write_tree_recursive(value)
            else:
                type_ = 'blob'
                oid = value
            entries.append((name, oid, type_))

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


def get_working_tree():
    result = {}
    for root, _, filenames in os.walk('.'):
        for filename in filenames:
            path = os.path.relpath(f'{root}/{filename}')
            if is_ignored(path) or not os.path.isfile(path):
                continue
            with open(path, 'rb') as f:
                result[path] = data.hash_object(f.read())
    return result


def get_index_tree():
    with data.get_index() as index:
        return index


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


def read_tree(tree_oid, update_working=False):
    with data.get_index() as index:
        index.clear()
        index.update(get_tree(tree_oid))
        if update_working:
            _checkout_index(index)


def read_tree_merged(t_base, t_HEAD, t_other, update_workding=False):
    with data.get_index() as index:
        index.clear()
        index.update(diff.merge_trees(
            get_tree(t_base),
            get_tree(t_HEAD),
            get_tree(t_other)
        ))
        if update_workding:
            _checkout_index(index)


def _checkout_index(index: dict):
    _empty_current_directory()
    for path, oid in index.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data.get_object(oid, 'blob'))


def commit(message):
    HEAD = data.get_ref('HEAD').value
    MERGE_HEAD = data.get_ref('MERGE_HEAD').value
    commit = ''.join([
        f'tree {write_tree()}\n',
        '\n' if not HEAD else f'parent {HEAD}\n',
        '\n' if not MERGE_HEAD else f'parent {MERGE_HEAD}\n',
        f'\n{message}\n'
    ])

    # then delete merge head
    if MERGE_HEAD:
        data.delete_ref('MERGE_HEAD', deref=False)

    oid = data.hash_object(commit.encode(), 'commit')
    data.update_ref('HEAD', data.RefValue(False, oid))
    return oid


def checkout(name):
    oid = get_oid(name)
    commit = get_commit(oid)
    read_tree(commit.tree, update_working=True)

    if is_branch(name):
        HEAD = data.RefValue(symbolic=True, value=f'refs/heads/{name}')
    else:
        HEAD = data.RefValue(symbolic=False, value=oid)

    data.update_ref('HEAD', HEAD, deref=False)


def iter_branch_names():
    for refname, _ in data.iter_refs('refs/heads/'):
        yield os.path.relpath(refname, 'refs/heads/')


def is_branch(branch):
    return data.get_ref(f'refs/heads/{branch}').value is not None


def get_branch_name():
    HEAD = data.get_ref('HEAD', deref=False)
    if not HEAD.symbolic:
        return None
    HEAD = HEAD.value
    assert HEAD.startswith('refs/heads/')
    return os.path.relpath(HEAD, 'refs/heads')


def reset(oid):
    data.update_ref('HEAD', data.RefValue(symbolic=False, value=oid))


def merge(other):
    HEAD = data.get_ref('HEAD').value
    assert HEAD
    merge_base = get_merge_base(other, HEAD)
    c_other = get_commit(other)

    # fast-forward merge
    if merge_base == HEAD:
        read_tree(c_other.tree, update_working=True)
        data.update_ref('HEAD', data.RefValue(symbolic=False, value=other))
        print('Fast-forward merge, no need to commit')
        return

    data.update_ref('MERGE_HEAD', data.RefValue(symbolic=False, value=other))
    c_base = get_commit(merge_base)
    c_HEAD = get_commit(HEAD)

    read_tree_merged(c_base.tree, c_HEAD.tree,
                     c_other.tree, update_workding=True)
    print('Merged in working tree\nPlease commit to continue')


def get_merge_base(oid1, oid2):
    parents1 = set(iter_commits_and_parents({oid1}))

    for oid in iter_commits_and_parents({oid2}):
        if oid in parents1:
            return oid


def is_ancestor_of(commit, maybe_ancester):
    return maybe_ancester in iter_commits_and_parents({commit})


def create_tag(name, oid):
    data.update_ref(f'refs/tags/{name}', data.RefValue(False, oid))


def create_branch(name, oid):
    data.update_ref(f'refs/heads/{name}', data.RefValue(False, oid))


Commit = namedtuple('Commit', ['tree', 'parents', 'message'])


def get_commit(oid):
    parents = []

    commit = data.get_object(oid, 'commit').decode()
    lines = iter(commit.splitlines())
    for line in itertools.takewhile(operator.truth, lines):
        k, v = line.split(' ', 1)
        if k == 'tree':
            tree = v
        elif k == 'parent':
            parents.append(v)
        else:
            raise Exception(f'Unknown field {k}')
    message = '\n'.join(lines)
    return Commit(tree=tree, parents=parents, message=message)


def iter_commits_and_parents(oids):
    oids = deque(oids)
    visited = set()

    while oids:
        oid = oids.popleft()
        if not oid or oid in visited:
            continue
        visited.add(oid)
        yield oid
        commit = get_commit(oid)
        oids.extendleft(commit.parents[:1])
        oids.extend(commit.parents[1:])


def iter_objects_in_commits(oids):
    visited = set()

    def _iter_objects_in_tree(oid):
        '''Get all objects in tree via DFS'''
        visited.add(oid)
        yield oid
        for type_, oid, _ in _iter_tree_entries(oid):
            if type_ == 'tree':
                yield from _iter_objects_in_tree(oid)
            else:
                visited.add(oid)
                yield oid

    # get objects in parent tree
    for oid in iter_commits_and_parents(oids):
        yield oid
        commit = get_commit(oid)
        if commit.tree not in visited:
            yield from _iter_objects_in_tree(commit.tree)


def get_oid(name):
    # alias @ as HEAD
    if name == '@':
        name = 'HEAD'

    # name is ref
    refs_to_search = [
        f'{name}',
        f'refs/{name}',
        f'refs/tags/{name}',
        f'refs/heads/{name}'
    ]
    for ref in refs_to_search:
        searched_ref = data.get_ref(ref).value
        if searched_ref:
            return searched_ref
    # name is sha1
    is_hex = all(c in string.hexdigits for c in name)
    if len(name) == 40 and is_hex:
        return name

    raise Exception(f'Unknown name {name}')


def add(filenames):
    def add_file(filename):
        filename = os.path.relpath(filename)
        with open(filename, 'rb') as f:
            oid = data.hash_object(f.read())
        index[filename] = oid

    def add_directory(dirname):
        for root, _, filenames in os.walk(dirname):
            for filename in filenames:
                path = os.path.relpath(os.path.join(root, filename))
                if is_ignored(path) or not os.path.isfile(path):
                    continue
                add_file(path)

    with data.get_index() as index:
        for filename in filenames:
            if os.path.isfile(filename):
                add_file(filename)
            elif os.path.isdir(filename):
                add_directory(filename)


def is_ignored(path):
    return '.ugit' in path
