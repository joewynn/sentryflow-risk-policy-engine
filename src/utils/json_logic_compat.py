"""
Python 3 compatible re-implementation of json-logic 0.6.3.
The PyPI package (json-logic==0.6.3) is Python 2 only:
  - dict.keys()[0]      → list(dict.keys())[0]
  - missing reduce import (was a builtin in Py2, lives in functools in Py3)
  - map() returns a lazy iterator in Py3; must be wrapped in list() before *-unpacking
"""
import sys
from functools import reduce


def jsonLogic(tests, data=None):
    if tests is None or type(tests) != dict:
        return tests

    data = data or {}

    op = list(tests.keys())[0]
    values = tests[op]

    operations = {
        "==":  (lambda a, b: a == b),
        "===": (lambda a, b: a is b),
        "!=":  (lambda a, b: a != b),
        "!==": (lambda a, b: a is not b),
        ">":   (lambda a, b: a > b),
        ">=":  (lambda a, b: a >= b),
        "<":   (lambda a, b, c=None: a < b if c is None else (a < b) and (b < c)),
        "<=":  (lambda a, b, c=None: a <= b if c is None else (a <= b) and (b <= c)),
        "!":   (lambda a: not a),
        "%":   (lambda a, b: a % b),
        "and": (lambda *args: reduce(lambda t, a: t and a, args, True)),
        "or":  (lambda *args: reduce(lambda t, a: t or a, args, False)),
        "?:":  (lambda a, b, c: b if a else c),
        "log": (lambda a: a if sys.stdout.write(str(a)) else a),
        "in":  (lambda a, b: a in b if hasattr(b, "__contains__") else False),
        "var": (lambda a, not_found=None:
            reduce(
                lambda d, key: (
                    d.get(key, not_found) if type(d) == dict
                    else d[int(key)] if (
                        type(d) in (list, tuple) and str(key).lstrip("-").isdigit()
                    ) else not_found
                ),
                str(a).split("."),
                data,
            )
        ),
        "cat": (lambda *args: "".join(str(a) for a in args)),
        "+":   (lambda *args: reduce(lambda t, a: t + float(a), args, 0.0)),
        "*":   (lambda *args: reduce(lambda t, a: t * float(a), args, 1.0)),
        "-":   (lambda a, b=None: -a if b is None else a - b),
        "/":   (lambda a, b=None: a if b is None else float(a) / float(b)),
        "min": (lambda *args: min(args)),
        "max": (lambda *args: max(args)),
        "count": (lambda *args: sum(1 if a else 0 for a in args)),
    }

    if op not in operations:
        raise RuntimeError(f"Unrecognized operation '{op}'")

    if type(values) not in (list, tuple):
        values = [values]

    values = list(map(lambda val: jsonLogic(val, data), values))
    return operations[op](*values)
