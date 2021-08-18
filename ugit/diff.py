from collections import defaultdict
import difflib

from . import data


def compare_trees(*trees):
    entries = defaultdict(lambda: [None] * len(trees))
    for i, tree in enumerate(trees):
        for path, oid in tree.items():
            entries[path][i] = oid

    for path, oids in entries.items():
        yield (path, *oids)


def diff_trees(t_from, t_to):
    output = ''
    for path, o_from, o_to in compare_trees(t_from, t_to):
        if o_from != o_to:
            output += f'changed: {path}\n'
            diff_result = diff_blobs(o_from, o_to)
            output += f'{diff_result}\n\n' if diff_result else ''
    return output


def diff_blobs(o_from, o_to, path='blob'):
    try:
        b_from = data.get_object(o_from).decode(errors='ignore')
    except:
        b_from = ''
    try:
        b_to = data.get_object(o_to).decode(errors='ignore')
    except:
        b_to = ''
    result = difflib.unified_diff(b_from.splitlines(), b_to.splitlines())
    return '\n'.join(result)
