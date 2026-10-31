Handbook demo service, version 1.0.
Python 3 standard library only; no installation or network is needed to build.

Print a greeting: python3 app.py
Run six tests: python3 -m unittest discover -s tests -v
Build: python3 tools/build.py
Optional local server: python3 app.py --serve --port 8087
The server binds only to 127.0.0.1. Stop it with Ctrl+C.

The ZIP contains only app.py and README.txt, with their original bytes.
Tests, Git metadata and provenance metadata are outside the ZIP.
The archive has a fixed member order, DOS date, Unix mode and ZIP_STORED data.
dist/manifest.json declares input hashes, archive hash, HEAD and dirty status.
dist/source-commit.txt is HEAD provenance, not proof that the inputs were clean.
