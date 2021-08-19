from collections import defaultdict
import difflib

from . import data


class Flags:
    BYTE_BLOB = 'BYTE_BLOB'
    BYTE_SPLIT = b'<<<<<<<<<>>>>>>>>'
    UGIT_BYTES_TYPE = b'@UGIT_TYPE: 0'


def compare_trees(*trees):
    entries = defaultdict(lambda: [None] * len(trees))
    for i, tree in enumerate(trees):
        for path, oid in tree.items():
            entries[path][i] = oid

    for path, oids in entries.items():
        yield (path, *oids)


def iter_changed_files(t_from, t_to):
    for path, o_from, o_to in compare_trees(t_from, t_to):
        if o_from != o_to:
            action = ('new file' if not o_from else
                      'delted' if not o_to else
                      'modified')
            yield path, action


def diff_trees(t_from, t_to):
    output = ''
    for path, o_from, o_to in compare_trees(t_from, t_to):
        if o_from != o_to:
            output += f'changed: {path}\n'
            diff_result = diff_blobs(o_from, o_to)
            output += f'{diff_result}\n\n' if diff_result else ''
    return output


def _get_blob_lines(oid):
    try:
        blob = data.get_object(oid)
        blob = blob.decode(errors='ignore')
    except:
        blob = Flags.BYTE_BLOB
    return blob.splitlines()


def diff_blobs(o_from, o_to, path='blob'):
    b_from, b_to = _get_blob_lines(o_from), _get_blob_lines(o_to)
    result = difflib.unified_diff(b_from, b_to)
    return '\n'.join(result)


def merge_trees(t_HEAD, t_other):
    tree = {}
    for path, o_HEAD, o_other in compare_trees(t_HEAD, t_other):
        tree[path] = merge_blobs(o_HEAD, o_other)
    return tree


def merge_blobs(o_HEAD, o_other):
    b_HEAD, b_other = _get_blob_lines(o_HEAD), _get_blob_lines(o_other)
    # if both file is text file, diff and merge it
    if b_HEAD != Flags.BYTE_BLOB and b_other != Flags.BYTE_BLOB:
        result = difflib.ndiff(b_HEAD, b_other)
        return '\n'.join(result).encode('utf-8')
    # else use Flags.BYTE_SPLIT line split them and place to one file
    result = []
    if b_HEAD == Flags.BYTE_BLOB:
        result.append(data.get_object(o_HEAD))
    if b_other == Flags.BYTE_BLOB:
        result.append(data.get_object(o_other))
    # merged file start with Flas.UGIT_BYTES_TYPE
    return Flags.UGIT_BYTES_TYPE + Flags.BYTE_SPLIT.join(result)
