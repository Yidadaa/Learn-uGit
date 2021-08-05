import argparse
import sys
import os

from . import base
from . import data


def main():
    args = parse_args()
    args.func(args)


def parse_args():
    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(dest='command')
    commands.required = True

    init_parser = commands.add_parser('init')
    init_parser.set_defaults(func=init)

    hash_object_parser = commands.add_parser('hash-object')
    hash_object_parser.set_defaults(func=hash_object)
    hash_object_parser.add_argument('file')

    cat_file_object_parser = commands.add_parser('cat-file')
    cat_file_object_parser.set_defaults(func=cat_file)
    cat_file_object_parser.add_argument('object')

    write_tree_object_parser = commands.add_parser('write-tree')
    write_tree_object_parser.set_defaults(func=write_tree)

    read_tree_object_parser = commands.add_parser('read-tree')
    read_tree_object_parser.set_defaults(func=read_tree)
    read_tree_object_parser.add_argument('tree')

    commit_object_parser = commands.add_parser('commit')
    commit_object_parser.set_defaults(func=commit)
    commit_object_parser.add_argument('-m', '--message', required=True)

    return parser.parse_args()


def init(args):
    data.init()
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
