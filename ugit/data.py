from genericpath import exists
import os
import hashlib
from collections import namedtuple

GIT_DIR = '.ugit'


def init():
    os.makedirs(GIT_DIR)
    os.makedirs(f'{GIT_DIR}/objects')


RefValue = namedtuple('RefValue', ['symbolic', 'value'])


def update_ref(ref, value: RefValue, deref=True):
    ref, _ = _get_ref_internal(ref, deref=False)

    assert value.value
    if value.symbolic:
        value = f'ref: {value.value}'
    else:
        value = value.value
    ref_path = f'{GIT_DIR}/{ref}'
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    with open(ref_path, 'w') as f:
        f.write(value)


def get_ref(ref, deref=True):
    _, ref_value = _get_ref_internal(ref, deref)
    return ref_value


def _get_ref_internal(ref, deref=True):
    ref_path = f'{GIT_DIR}/{ref}'
    value = None
    if os.path.isfile(ref_path):
        with open(ref_path) as f:
            value = f.read().strip()

    # support symbolic refs
    symbolic = bool(value) and value.startswith('ref:')
    if symbolic:
        value = value.split(':', 1)[1].strip()
        if deref:
            return _get_ref_internal(value, deref=True)

    return ref, RefValue(symbolic=symbolic, value=value)


def iter_refs(prefix='', deref=True):
    refs = ['HEAD']
    for root, _, filenames in os.walk(f'{GIT_DIR}/refs/'):
        root = os.path.relpath(root, GIT_DIR)
        refs.extend(f'{root}/{name}' for name in filenames)

    for refname in refs:
        if not refname.replace('\\', '/').startswith(prefix):
            continue
        yield refname, get_ref(refname, deref=deref)


def hash_object(data, type_='blob'):
    obj = type_.encode() + b'\x00' + data
    oid = hashlib.sha1(obj).hexdigest()
    with open(f'{GIT_DIR}/objects/{oid}', 'wb') as out:
        out.write(obj)
    return oid


def get_object(oid, expected='blob'):
    with open(f'{GIT_DIR}/objects/{oid}', 'rb') as f:
        obj = f.read()

    type_, _, content = obj.partition(b'\x00')
    type_ = type_.decode()

    if expected is not None:
        assert type_ == expected, f'Expected {expected}, got {type_}'

    return content
