import argparse
from itertools import starmap
import sys
import os
import textwrap
from graphviz import Digraph
from graphviz.backend import view

from . import base
from . import data


def main():
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


def log(args):
    refs = {}
    for refname, ref in data.iter_refs():
        refs.setdefault(ref.value, []).append(refname)

    for oid in base.iter_commits_and_parents({args.oid}):
        commit = base.get_commit(oid)
        refs_str = f' ({", ".join(refs[oid])})' if oid in refs else ''
        print(f'commit {oid}{refs_str}\n')
        print(textwrap.indent(commit.message, '    '))
        print('')


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
        if commit.parent:
            dot.edge(commit.parent, oid)
    print(dot.source)
    dot.render(f'{os.getcwd()}/{data.GIT_DIR}/output.gv', view=True)


def status(args):
    HEAD = base.get_oid('@')
    branch = base.get_branch_name()
    if branch:
        print(f'On branch {branch}')
    else:
        print(f'HEAD detached at {HEAD[:10]}')
