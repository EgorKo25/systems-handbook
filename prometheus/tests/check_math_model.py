#!/usr/bin/env python3
"""A deliberately small arithmetic model, NOT a PromQL interpreter.

Only fixed, ordered float counter samples are accepted. No parser, storage,
staleness, histograms or vector matching is implemented here. Native promtool
tests independently verify the examples against the real engine.
"""
from math import isclose


def counter_window(samples, timestamp, width):
    selected = [(t, v) for t, v in samples if timestamp - width < t <= timestamp]
    assert len(selected) >= 2
    span = selected[-1][0] - selected[0][0]
    assert span > 0
    corrected = selected[-1][1] - selected[0][1]
    resets = 0
    for (_, previous), (_, current) in zip(selected, selected[1:]):
        if current < previous:
            corrected += previous
            resets += 1
    average = span / (len(selected) - 1)
    left = selected[0][0] - (timestamp - width)
    right = timestamp - selected[-1][0]
    if left >= 1.1 * average: left = average / 2
    if corrected > 0 and selected[0][1] >= 0:
        left = min(left, span * selected[0][1] / corrected)
    if right >= 1.1 * average: right = average / 2
    increase = corrected * (span + left + right) / span
    return increase / width, increase, resets


def main():
    fixed = list(zip(range(0, 301, 60), [0, 60, 120, 20, 80, 140]))
    rate, increase, resets = counter_window(fixed, 300, 300)
    assert isclose(rate, 5 / 6) and increase == 250 and resets == 1
    assert counter_window([(120, 60), (180, 120)], 180, 180)[:2] == (.5, 90)
    rate, increase, _ = counter_window([(60, 0), (120, 60), (180, 120)], 180, 180)
    assert isclose(rate, 2 / 3) and increase == 120
    assert isclose(.3 + (1 - .3) * (.9 * 4 - 3) / (4 - 3), .72)
    assert 50 * 8 * (10 + 3) == 5200
    assert 6000 / 15 * 7 * 86400 == 241920000
    assert isclose(14.4 * 3600 / (30 * 86400), .02)
    print('MODEL PASS: fixed counter/extrapolation, classic interpolation, capacity and budget arithmetic; this is NOT engine execution')


if __name__ == '__main__': main()
