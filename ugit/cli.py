import argparse
from itertools import starmap
import sys
import os
import textwrap
from graphviz import Digraph

from . import base  # pylint: disable=relative-beyond-top-level
from . import data  # pylint: disable=relative-beyond-top-level
from . import diff  # pylint: disable=relative-beyond-top-level
from . import remote  # pylint: disable=relative-beyond-top-level


def main():
    with data.change_git_dir('.'):
        args = parse_args()
        args.func(args)


def parse_args():
    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(dest='command')
    commands.required = True

    oid = base.get_oid

    init_parser = commands.add_parser('init')
    init_parser.set_defaults(func=init)

    hash_object_parser = commands.add_parser('hash-object')
    hash_object_parser.set_defaults(func=hash_object)
    hash_object_parser.add_argument('file')

    cat_file_object_parser = commands.add_parser('cat-file')
    cat_file_object_parser.set_defaults(func=cat_file)
    cat_file_object_parser.add_argument('object', type=oid)

    write_tree_object_parser = commands.add_parser('write-tree')
    write_tree_object_parser.set_defaults(func=write_tree)

    read_tree_object_parser = commands.add_parser('read-tree')
    read_tree_object_parser.set_defaults(func=read_tree)
    read_tree_object_parser.add_argument('tree', type=oid)

    commit_object_parser = commands.add_parser('commit')
    commit_object_parser.set_defaults(func=commit)
    commit_object_parser.add_argument('-m', '--message', required=True)

    log_parser = commands.add_parser('log')
    log_parser.set_defaults(func=log)
    log_parser.add_argument('oid', default='@', type=oid, nargs='?')

    show_parser = commands.add_parser('show')
    show_parser.set_defaults(func=show)
    show_parser.add_argument('oid', default='@', type=oid, nargs='?')

    diff_parser = commands.add_parser('diff')
    diff_parser.set_defaults(func=_diff)
    diff_parser.add_argument('--cached', action='store_true')
    diff_parser.add_argument('commit', nargs='?')

    checkout_parser = commands.add_parser('checkout')
    checkout_parser.set_defaults(func=checkout)
    checkout_parser.add_argument('commit')

    tag_parser = commands.add_parser('tag')
    tag_parser.set_defaults(func=tag)
    tag_parser.add_argument('name')
    tag_parser.add_argument('oid', default='@', type=oid, nargs='?')

    branch_parser = commands.add_parser('branch')
    branch_parser.set_defaults(func=branch)
    branch_parser.add_argument('name', nargs='?')
    branch_parser.add_argument('start_point', default='@', type=oid, nargs='?')

    k_parser = commands.add_parser('k')
    k_parser.set_defaults(func=k)

    status_parser = commands.add_parser('status')
    status_parser.set_defaults(func=status)

    reset_parser = commands.add_parser('reset')
    reset_parser.set_defaults(func=reset)
    reset_parser.add_argument('commit', type=oid)

    merge_parser = commands.add_parser('merge')
    merge_parser.set_defaults(func=merge)
    merge_parser.add_argument('commit', type=oid)

    merge_base_parser = commands.add_parser('merge_base')
    merge_base_parser.set_defaults(func=merge_base)
    merge_base_parser.add_argument('commit1', type=oid)
    merge_base_parser.add_argument('commit2', type=oid)

    fetch_parser = commands.add_parser('fetch')
    fetch_parser.set_defaults(func=fetch)
    fetch_parser.add_argument('remote')

    push_parser = commands.add_parser('push')
    push_parser.set_defaults(func=push)
    push_parser.add_argument('remote')
    push_parser.add_argument('branch')

    add_parser = commands.add_parser('add')
    add_parser.set_defaults(func=add)
    add_parser.add_argument('files', nargs='+')

    return parser.parse_args()


def init(args):
    base.init()
    print(f'Initialized empty ugit repository in {os.getcwd()}/{data.GIT_DIR}')


def hash_object(args):
    with open(args.file, 'rb') as f:
        print(data.hash_object(f.read()))


def cat_file(args):
    sys.stdout.flush()
    sys.stdout.buffer.write(data.get_object(args.object))


def write_tree(args):
    tree = base.write_tree()
    print(tree)


def read_tree(args):
    base.read_tree(args.tree)


def commit(args):
    print(base.commit(args.message))


def _print_commit(oid, commit, refs=None):
    refs_str = f' ({", ".join(refs)})' if refs else ''
    print(f'commit {oid}{refs_str}\n')
    print(textwrap.indent(commit.message, '    '))
    print('')


def log(args):
    refs = {}
    for refname, ref in data.iter_refs():
        refs.setdefault(ref.value, []).append(refname)

    for oid in base.iter_commits_and_parents({args.oid}):
        commit = base.get_commit(oid)
        _print_commit(oid, commit, refs.get(oid))


def show(args):
    if not args.oid:
        return
    commit = base.get_commit(args.oid)
    parent_tree = None
    if commit.parents:
        parent_tree = base.get_commit(commit.parents[0]).tree

    _print_commit(args.oid, commit)

    result = diff.diff_trees(base.get_tree(
        parent_tree), base.get_tree(commit.tree))
    print(result)


def _diff(args):
    oid = args.commit and base.get_oid(args.commit)

    if args.commit:
        tree_from = base.get_tree(oid and base.get_commit(oid).tree)

    if args.cached:
        tree_to = base.get_index_tree()
        if not args.commit:
            oid = base.get_oid('@')
            tree_from = base.get_tree(oid and base.get_commit(oid).tree)
    else:
        tree_to = base.get_working_tree()
        if not args.commit:
            tree_from = base.get_index_tree()

    result = diff.diff_trees(tree_from, tree_to)
    print(result)


def checkout(args):
    base.checkout(args.commit)


def tag(args):
    oid = args.oid
    base.create_tag(args.name, oid)


def branch(args):
    if args.name:
        base.create_branch(args.name, args.start_point)
        print(f'Branch {args.name} created at {args.start_point[:10]}')
    else:
        current = base.get_branch_name()
        for branch in base.iter_branch_names():
            prefix = '*' if branch == current else ' '
            print(f'{prefix} {branch}')


def k(args):
    dot = Digraph(comment='digraph commits')
    oids = set()
    for refname, ref in data.iter_refs():
        dot.node(refname)
        dot.node(ref.value)
        dot.edge(refname, ref.value)
        if not ref.symbolic:
            oids.add(ref.value)

    for oid in base.iter_commits_and_parents(oids):
        commit = base.get_commit(oid)
        dot.node(oid, oid[:10])
        for parent in commit.parents:
            dot.edge(parent, oid)
    print(dot.source)
    dot.render(f'{os.getcwd()}/{data.GIT_DIR}/output.gv', view=True)


def status(args):
    HEAD = base.get_oid('@')
    branch = base.get_branch_name()
    if branch:
        print(f'On branch {branch}')
    else:
        print(f'HEAD detached at {HEAD[:10]}')

    MERGE_HEAD = data.get_ref('MERGE_HEAD').value
    if MERGE_HEAD:
        print(f'Merging with {MERGE_HEAD[:10]}')

    head_printed = False
    # TODO: fix head_tree is none after add files
    HEAD_tree = HEAD and base.get_commit(HEAD).tree
    print(HEAD, base.get_commit(HEAD).tree)
    print(base.get_tree(HEAD_tree))
    for path, action in diff.iter_changed_files(base.get_tree(HEAD_tree), base.get_index_tree()):
        if not head_printed:
            print('\nChanges to be commited:\n')
            head_printed = True
        print(f'{action:>12}: {path}')

    no_change_head_printed = False
    for path, action in diff.iter_changed_files(base.get_index_tree(), base.get_working_tree()):
        if not no_change_head_printed:
            print('\nChanges not staged for commit:\n')
        print(f'{action:>12}: {path}')

    if not head_printed:
        print('nothing to commit, working tree clean')
    print('\n')


def reset(args):
    base.reset(args.commit)


def merge(args):
    base.merge(args.commit)


def merge_base(args):
    print(base.get_merge_base(args.commit1, args.commit2))


def fetch(args):
    remote.fetch(args.remote)


def push(args):
    remote.push(args.remote, os.path.join('refs', 'heads', args.branch))


def add(args):
    base.add(args.files)
