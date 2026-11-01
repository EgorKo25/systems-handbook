#!/usr/bin/env python3
"""Small original models, not an emulator of Docker, OverlayFS or Linux.

No filesystem writes, subprocesses, sockets or daemon requests. Paths are logical
relative names. The layer model omits tar, symlinks, directories and metadata.
"""
from fractions import Fraction
import json
import math


def logical_path(value):
    if not isinstance(value, str) or not value or value.startswith('/'):
        raise ValueError('a nonempty relative logical path is required')
    if any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('path normalization is intentionally not modelled')
    return value


def apply_layer(lower, files=None, whiteouts=(), opaque_dirs=()):
    """Apply lower removals before same-layer files, as OCI changesets require.

    Whiteouts remove the named lower file/subtree. Opaque dirs hide lower
    descendants. Immutable lower input and same-layer new files remain intact.
    This describes visible logical files only, not on-disk OverlayFS markers.
    """
    result = {logical_path(k): v for k, v in lower.items()}
    for name in whiteouts:
        name = logical_path(name)
        result = {k: v for k, v in result.items()
                  if k != name and not k.startswith(name + '/')}
    for name in opaque_dirs:
        name = logical_path(name)
        result = {k: v for k, v in result.items()
                  if not k.startswith(name + '/')}
    for name, value in (files or {}).items():
        if not isinstance(value, str):
            raise ValueError('this text-only model expects string contents')
        result[logical_path(name)] = value
    return result


def quota_period(quota_us, period_us, parallelism):
    """Ideal saturated tasks; no borrowing, scheduler overhead or burst credit.

    Shows time to exhaust one period quota and resulting pause. It predicts
    neither latency nor the exact behaviour of Linux CFS bandwidth slices.
    """
    if (not isinstance(parallelism, int) or isinstance(parallelism, bool)
            or parallelism < 1):
        raise ValueError('parallelism must be a positive integer')
    quota, period = Fraction(quota_us), Fraction(period_us)
    if quota <= 0 or period <= 0:
        raise ValueError('quota and period must be positive')
    active = min(period, quota / parallelism)
    return dict(active_wall_us=active, pause_wall_us=period-active,
                consumed_cpu_us=active*parallelism,
                nominal_cpu=quota/period)


def nearest_rank(values, percentile):
    """Nearest-rank quantile, requiring a nonempty finite sample and 0<p<=1."""
    p = Fraction(str(percentile))
    ordered = sorted(values)
    if not ordered or not 0 < p <= 1:
        raise ValueError('nonempty sample and 0<p<=1 required')
    if any(not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in ordered):
        raise ValueError('finite numeric values required')
    return ordered[math.ceil(len(ordered)*p)-1]


if __name__ == '__main__':
    base={'app/config':'A', 'app/old':'B'}
    changed=apply_layer(base, {'app/config':'C'}, ['app/old'])
    budget=quota_period(100000,100000,4)
    print(json.dumps(dict(base=base,visible=changed,
                         quota={k:str(v) for k,v in budget.items()}),
                     ensure_ascii=False,indent=2))
