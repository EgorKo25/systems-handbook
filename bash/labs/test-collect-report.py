#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="bash-report-test-") as temporary:
    root = Path(temporary)
    data = root / "data"
    data.mkdir()
    names = ["a.log", "two words.log", "line\nnext.log", "-leading.log", "star*.log"]
    expected = []
    for index, name in enumerate(names):
        content = b"x" * index
        (data / name).write_bytes(content)
        expected.append({"path": name, "bytes": len(content)})
    (data / "not-included.txt").write_text("other")
    (data / "link.log").symlink_to(data / "a.log")
    destination = root / "report.json"
    command = ["bash", str(HERE / "collect-report.sh")]
    result = subprocess.run(command + ["--dry-run", str(data), str(destination)], capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert not destination.exists()
    assert not Path(str(destination) + ".lock").exists()
    result = subprocess.run(command + [str(data), str(destination)], capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    expected.sort(key=lambda record: os.fsencode(record["path"]))
    assert json.loads(destination.read_text())["records"] == expected
    before = destination.read_bytes()
    result = subprocess.run(command + [str(root / "missing"), str(destination)], capture_output=True, timeout=10)
    assert result.returncode != 0
    assert destination.read_bytes() == before
    # Два согласованных экземпляра не повреждают JSON.
    processes = [subprocess.Popen(command + [str(data), str(destination)], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) for _ in range(2)]
    for process in processes:
        _, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
    assert json.loads(destination.read_text())["records"] == expected
print("PASS collect-report: сложные имена, пустые файлы, ссылки, dry-run, отказ до публикации, два запуска")
