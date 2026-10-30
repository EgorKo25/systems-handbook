#!/usr/bin/env python3
"""Точное представление аргументов. Вывод JSON сохраняет границы и управляющие символы."""
import json
import os
import sys
print(json.dumps([{"index": i, "text": s, "bytes": len(os.fsencode(s)),
                   "hex": os.fsencode(s).hex(" ")} for i, s in enumerate(sys.argv[1:])],
                 ensure_ascii=False, indent=2))
