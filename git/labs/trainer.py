#!/usr/bin/env python3
"""An offline, stateful Git laboratory. Never operates on an unmarked project."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

LAB = "systems-handbook-git-lab-v1"
MARKER = ".handbook-git-lab.json"
CHILD_MARKER = ".handbook-owned.json"
CHILDREN = ("repo", "peer", "remote.git", ".trainer-hooks")
CHECKPOINTS = ("start", "index", "branch", "merge", "recovery", "remote", "build")
EXERCISES = ("index", "branch", "merge", "recovery", "fetched", "remote", "build", "reproducible")
TEMPLATE = Path(__file__).with_name("template")
TEMPLATE_FILES = (".gitignore", "README.txt", "app.py", "message.txt", "notes.txt",
                  "tests/test_app.py", "tools/build.py")


class LabError(Exception):
    pass


def linklike(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def write(path, text):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def checked_path(value):
    path = Path(os.path.abspath(os.path.expanduser(str(value))))
    if path == Path(path.anchor):
        raise LabError("Корень файловой системы не может быть стендом.")
    for parent in (path, *path.parents):
        if linklike(parent):
            raise LabError("Путь стенда и его родители не могут быть символическими ссылками.")
    return path


def no_links(path):
    """Reject symlinks before traversal/deletion; do not follow them."""
    if linklike(path):
        raise LabError("Символическая ссылка внутри стенда: операция отменена.")
    if not path.is_dir():
        return
    with os.scandir(path) as entries:
        for entry in entries:
            if linklike(Path(entry.path)):
                raise LabError("Символическая ссылка внутри стенда: операция отменена.")
            if entry.is_dir(follow_symlinks=False):
                no_links(Path(entry.path))
            elif not entry.is_file(follow_symlinks=False):
                raise LabError("В стенде найден специальный файл: операция отменена.")


def read_marker(workspace):
    workspace = checked_path(workspace)
    marker = workspace / MARKER
    if linklike(marker) or not marker.is_file() or marker.stat().st_size > 4096:
        raise LabError("Нет корректного маркера учебного стенда.")
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        raise LabError("Маркер стенда повреждён.") from None
    if (not isinstance(data, dict) or data.get("lab") != LAB or data.get("format") != 1
            or data.get("children") != list(CHILDREN)
            or data.get("checkpoint") not in CHECKPOINTS
            or not re.fullmatch(r"[0-9a-f]{64}", str(data.get("id", "")))):
        raise LabError("Маркер не соответствует формату этого стенда.")
    return workspace, data


def validate(workspace):
    workspace, data = read_marker(workspace)
    if set(p.name for p in workspace.iterdir()) - {MARKER, *CHILDREN}:
        raise LabError("На верхнем уровне есть посторонние файлы. Сброс запрещён.")
    no_links(workspace)
    for name in CHILDREN:
        child = workspace / name
        if not child.exists():
            continue  # Allows recovery from an interrupted reset after a child was removed.
        if not child.is_dir():
            raise LabError("Известный дочерний путь перестал быть каталогом.")
        if name == ".trainer-hooks":
            if any(child.iterdir()):
                raise LabError("Каталог учебных hooks должен оставаться пустым.")
        else:
            marker = child / CHILD_MARKER
            if not marker.is_file() or marker.stat().st_size > 4096:
                raise LabError("Нет дочернего маркера: сброс запрещён.")
            try:
                owned = json.loads(marker.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raise LabError("Дочерний маркер повреждён.") from None
            if owned != {"lab": LAB, "id": data["id"], "child": name}:
                raise LabError("Дочерний каталог не принадлежит этому стенду.")
            metadata = child if name == "remote.git" else child / ".git"
            if metadata.exists() and not metadata.is_dir():
                raise LabError("Перенаправляющий файл .git не поддерживается этим стендом.")
            for redirect in ("commondir", "gitdir", "objects/info/alternates", "objects/info/http-alternates"):
                if (metadata / redirect).exists():
                    raise LabError("Внешние ссылки на хранилище Git не поддерживаются стендом.")
    return workspace, data


def environment():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
               GIT_AUTHOR_NAME="Handbook Student", GIT_AUTHOR_EMAIL="student@example.invalid",
               GIT_COMMITTER_NAME="Handbook Student", GIT_COMMITTER_EMAIL="student@example.invalid",
               PYTHONDONTWRITEBYTECODE="1")
    return env


def git(workspace, directory, *args, okay=(0,)):
    command = ["git", "--no-pager", "-c", "core.hooksPath=" + str(workspace / ".trainer-hooks"),
               "-c", "core.fsmonitor=false", "-c", "core.autocrlf=false",
               "-c", "protocol.allow=never", "-c", "protocol.file.allow=always",
               "-c", "commit.gpgSign=false", "-c", "tag.gpgSign=false"]
    metadata = directory / ".git"
    if metadata.is_dir() and not linklike(metadata):
        # Local core.worktree must not redirect operations outside this copy.
        command += ["--git-dir=" + str(metadata), "--work-tree=" + str(directory)]
    command += list(args)
    result = subprocess.run(command, cwd=directory, env=environment(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            encoding="utf-8", errors="replace")
    if result.returncode not in okay:
        # Do not print private paths or arbitrary repository stderr in reports.
        raise LabError("Git завершился с кодом %d (%s)." % (result.returncode, args[0]))
    return result.stdout.rstrip("\r\n")


def check_git():
    try:
        value = subprocess.run(["git", "--version"], env=environment(), check=True,
                               stdout=subprocess.PIPE, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise LabError("Требуется установленный Git версии 2.28 или новее.") from None
    match = re.search(r"(\d+)\.(\d+)", value)
    if not match or tuple(map(int, match.groups())) < (2, 28):
        raise LabError("Требуется Git 2.28 или новее.")
    return value


def check_template():
    no_links(TEMPLATE)
    for name in TEMPLATE_FILES:
        if not (TEMPLATE / name).is_file():
            raise LabError("В поставке отсутствует файл шаблона: " + name)


def configure(workspace, directory):
    settings = {"user.name": "Handbook Student", "user.email": "student@example.invalid",
                "commit.gpgSign": "false", "tag.gpgSign": "false", "core.autocrlf": "false",
                "core.eol": "lf", "core.fsmonitor": "false", "pull.rebase": "false",
                "core.hooksPath": "../.trainer-hooks"}
    for key, value in settings.items():
        git(workspace, directory, "config", "--local", key, value)


def commit(workspace, message):
    repo = workspace / "repo"
    git(workspace, repo, "add", "--all")
    git(workspace, repo, "commit", "-m", message)


def child_directory(workspace, data, name):
    path = workspace / name
    path.mkdir()
    if name != ".trainer-hooks":
        write(path / CHILD_MARKER, json.dumps({"lab": LAB, "id": data["id"], "child": name}) + "\n")
    return path


def populate(workspace, data, checkpoint):
    child_directory(workspace, data, ".trainer-hooks")
    remote = child_directory(workspace, data, "remote.git")
    repo = child_directory(workspace, data, "repo")
    peer = child_directory(workspace, data, "peer")
    git(workspace, workspace, "init", "--bare", "--template=", "--initial-branch=main", str(remote))
    configure(workspace, remote)
    git(workspace, repo, "init", "--template=", "--initial-branch=main")
    configure(workspace, repo)
    no_links(TEMPLATE)
    for name in TEMPLATE_FILES:
        source, target = TEMPLATE / name, repo / name
        if not source.is_file():
            raise LabError("В поставке отсутствует файл шаблона: " + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    commit(workspace, "Start the handbook demo")
    git(workspace, repo, "remote", "add", "origin", "../remote.git")
    git(workspace, repo, "push", "--set-upstream", "origin", "main")
    git(workspace, peer, "init", "--template=", "--initial-branch=main")
    configure(workspace, peer)
    git(workspace, peer, "remote", "add", "origin", "../remote.git")
    git(workspace, peer, "fetch", "origin")
    git(workspace, peer, "reset", "--hard", "origin/main")
    git(workspace, peer, "branch", "--set-upstream-to=origin/main", "main")
    if checkpoint == "index":
        write(repo / "notes.txt", "prepared\n")
        git(workspace, repo, "add", "notes.txt")
        write(repo / "notes.txt", "working\n")
    if checkpoint in ("branch", "merge", "recovery", "remote", "build"):
        git(workspace, repo, "switch", "-c", "feature")
        write(repo / "feature.txt", "feature ready\n")
        commit(workspace, "Add a feature marker")
        git(workspace, repo, "switch", "main")
        git(workspace, repo, "merge", "--ff-only", "feature")
    if checkpoint in ("merge", "recovery", "remote", "build"):
        git(workspace, repo, "switch", "-c", "feature-conflict")
        write(repo / "message.txt", "Hello from feature\n")
        commit(workspace, "Change the feature greeting")
        git(workspace, repo, "switch", "main")
        write(repo / "message.txt", "Hello from main\n")
        commit(workspace, "Change the main greeting")
    if checkpoint in ("recovery", "remote", "build"):
        git(workspace, repo, "merge", "feature-conflict", okay=(1,))
        write(repo / "message.txt", "Hello from both branches\n")
        commit(workspace, "Resolve the greeting conflict")
    if checkpoint in ("remote", "build"):
        git(workspace, repo, "switch", "--detach")
        write(repo / "recovery.txt", "recovered\n")
        commit(workspace, "A detached experiment")
        lost = git(workspace, repo, "rev-parse", "HEAD")
        git(workspace, repo, "switch", "main")
        git(workspace, repo, "branch", "rescued", lost)
        git(workspace, repo, "push", "origin", "main")
        git(workspace, peer, "fetch", "origin")
        git(workspace, peer, "merge", "--ff-only", "origin/main")
        write(peer / "peer.txt", "from peer\n")
        git(workspace, peer, "add", "peer.txt")
        git(workspace, peer, "commit", "-m", "A peer contribution")
        git(workspace, peer, "push", "origin", "main")
        git(workspace, repo, "fetch", "origin")
    if checkpoint == "build":
        git(workspace, repo, "merge", "--ff-only", "origin/main")
    data["checkpoint"] = checkpoint
    write(workspace / MARKER, json.dumps(data, indent=2) + "\n")


def initialize(value):
    check_git()
    check_template()
    workspace = checked_path(value)
    if workspace.exists() and (not workspace.is_dir() or any(workspace.iterdir())):
        raise LabError("init принимает только отсутствующий или пустой каталог.")
    workspace.mkdir(parents=True, exist_ok=True)
    data = {"lab": LAB, "format": 1, "id": secrets.token_hex(32),
            "children": list(CHILDREN), "checkpoint": "start"}
    write(workspace / MARKER, json.dumps(data, indent=2) + "\n")
    populate(workspace, data, "start")
    return workspace


def reset_checkpoint(value, checkpoint):
    if checkpoint not in CHECKPOINTS:
        raise LabError("Неизвестная контрольная точка.")
    check_git()
    check_template()
    workspace, data = validate(value)
    # All children were validated before removing any of them.
    for name in CHILDREN:
        child = workspace / name
        if child.exists():
            shutil.rmtree(child, onerror=remove_readonly)
    populate(workspace, data, checkpoint)


def remove_readonly(function, path, exception):
    """Git objects may be read-only on Windows; only handle validated owned files."""
    if os.name != "nt" or linklike(Path(path)):
        raise exception[1]
    mode = os.stat(path, follow_symlinks=False).st_mode
    os.chmod(path, mode | stat.S_IWUSR)
    function(path)


def require(condition, message):
    if not condition:
        raise LabError(message)


def archive_check(repo):
    output = repo / "dist"
    archive = output / "handbook-demo.zip"
    require(archive.is_file(), "Сначала выполните python3 tools/build.py.")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    data = archive.read_bytes()
    require(hashlib.sha256(data).hexdigest() == manifest["sha256"], "Хеш архива не совпал с manifest.json.")
    with zipfile.ZipFile(archive) as bundle:
        require(bundle.namelist() == ["README.txt", "app.py"], "Неверный состав или порядок ZIP.")
        for item in bundle.infolist():
            require(item.date_time == (2000, 1, 1, 0, 0, 0), "Дата записи ZIP не фиксирована.")
            require(item.compress_type == zipfile.ZIP_STORED, "Ожидался ZIP_STORED.")
            require(item.create_system == 3 and item.external_attr >> 16 == stat.S_IFREG | 0o644,
                    "Неверный тип/режим записи ZIP.")
            body = bundle.read(item.filename)
            require(body == (repo / item.filename).read_bytes(), "Архив не соответствует текущим входам.")
            record = next(r for r in manifest["members"] if r["name"] == item.filename)
            require(record["bytes"] == len(body) and record["sha256"] == hashlib.sha256(body).hexdigest(),
                    "Метаданные входа не соответствуют его байтам.")
    return manifest


def python(workspace, repo, *args):
    result = subprocess.run([sys.executable, *args], cwd=repo, env=environment(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    require(result.returncode == 0, "Команда Python завершилась неуспешно: " + " ".join(args))
    return result.stdout


def check(value, exercise):
    workspace, _ = validate(value)
    repo = workspace / "repo"
    require(repo.is_dir(), "Рабочая копия отсутствует; восстановите контрольную точку.")
    if exercise == "index":
        require(git(workspace, repo, "show", "HEAD:notes.txt") == "first", "HEAD должен содержать first.")
        require(git(workspace, repo, "show", ":notes.txt") == "prepared", "Индекс должен содержать prepared.")
        require((repo / "notes.txt").read_text(encoding="utf-8") == "working\n", "Рабочий файл должен содержать working.")
        blob = git(workspace, repo, "rev-parse", ":notes.txt")
        require(git(workspace, repo, "cat-file", "-t", blob) == "blob", "Индекс должен ссылаться на blob.")
    elif exercise == "branch":
        require(git(workspace, repo, "branch", "--show-current") == "main", "Вернитесь в main.")
        require(git(workspace, repo, "rev-parse", "main") == git(workspace, repo, "rev-parse", "feature"), "Нужен fast-forward main до feature.")
        require(git(workspace, repo, "show", "main:feature.txt") == "feature ready", "Нет ожидаемого feature.txt в коммите main.")
    elif exercise == "merge":
        parents = git(workspace, repo, "rev-list", "--parents", "-n", "1", "main").split()
        require(len(parents) == 3, "main должен указывать на коммит с двумя родителями.")
        require(git(workspace, repo, "show", "main:message.txt") == "Hello from both branches", "Результат конфликта ещё не сохранён в main.")
        require(not git(workspace, repo, "ls-files", "--unmerged"), "В индексе остался неразрешённый конфликт.")
    elif exercise == "recovery":
        require(git(workspace, repo, "show", "rescued:recovery.txt") == "recovered", "Ветка rescued должна сохранять потерянный эксперимент.")
        require(git(workspace, repo, "branch", "--show-current") == "main", "После восстановления вернитесь в main.")
        require(not (repo / "recovery.txt").exists(), "Эксперимент должен оставаться в отдельной ветке.")
    elif exercise in ("fetched", "remote"):
        peer_head = git(workspace, workspace / "peer", "rev-parse", "main")
        require(git(workspace, repo, "rev-parse", "origin/main") == peer_head, "Сначала получите вклад peer командой fetch.")
        require(git(workspace, repo, "show", "origin/main:peer.txt") == "from peer", "В удалённой истории нет peer.txt.")
        if exercise == "fetched":
            require(not (repo / "peer.txt").exists(), "Здесь fetch уже сделан, а локальная main ещё не сдвинута.")
            require(git(workspace, repo, "rev-parse", "main") != peer_head, "main ещё должна отличаться от origin/main.")
        else:
            require(git(workspace, repo, "rev-parse", "main") == peer_head, "Выполните fast-forward main до origin/main.")
            require((repo / "peer.txt").read_text(encoding="utf-8") == "from peer\n", "Рабочие файлы ещё не обновлены.")
    elif exercise == "build":
        python(workspace, repo, "-m", "unittest", "discover", "-s", "tests", "-v")
        manifest = archive_check(repo)
        head = git(workspace, repo, "rev-parse", "HEAD")
        require(manifest["provenance"]["head"] == head, "Метаданные относятся к другому HEAD; пересоберите.")
        require((repo / "dist/source-commit.txt").read_text(encoding="ascii") == head + "\n", "source-commit.txt не соответствует HEAD.")
    elif exercise == "reproducible":
        require(not git(workspace, repo, "status", "--porcelain", "--untracked-files=normal"), "Для опыта нужен чистый репозиторий; dist игнорируется.")
        with tempfile.TemporaryDirectory(prefix="handbook-repro-") as temporary:
            outputs = []
            for index in range(2):
                clone = Path(temporary) / ("copy-%d" % index)
                git(workspace, workspace, "clone", "--no-hardlinks", "--template=", str(repo), str(clone))
                configure(workspace, clone)
                for name in ("README.txt", "app.py"):
                    os.utime(clone / name, (946684800 + index * 86400, 946684800 + index * 86400))
                python(workspace, clone, "tools/build.py")
                archive_check(clone)
                outputs.append((clone / "dist/handbook-demo.zip").read_bytes())
            require(outputs[0] == outputs[1], "Архивы двух чистых копий различаются.")
            clone = Path(temporary) / "copy-1"
            old_head = git(workspace, clone, "rev-parse", "HEAD")
            git(workspace, clone, "commit", "--allow-empty", "-m", "Only provenance changes")
            python(workspace, clone, "tools/build.py")
            require((clone / "dist/handbook-demo.zip").read_bytes() == outputs[1], "Метаданные коммита изменили архив без изменения входов.")
            require((clone / "dist/source-commit.txt").read_text().strip() != old_head, "Внешние метаданные должны показать новый HEAD.")
    else:
        raise LabError("Неизвестное упражнение.")
    return {"exercise": exercise, "ok": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Автономный учебный стенд Git")
    parser.add_argument("--workspace", required=True, help="отдельный каталог стенда")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="создать стенд в отсутствующем или пустом каталоге")
    commands.add_parser("status", help="показать состояние, не сбрасывая работу")
    command = commands.add_parser("check", help="проверить результат конкретного этапа")
    command.add_argument("exercise", choices=EXERCISES)
    command = commands.add_parser("reset-checkpoint", help="удалить учебные копии и восстановить выбранную точку")
    command.add_argument("checkpoint", choices=CHECKPOINTS)
    command.add_argument("--yes", action="store_true", help="подтверждаю потерю несохранённой учебной работы")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            initialize(args.workspace)
            print("Стенд создан: repo/, peer/, remote.git/. Служба не запущена.")
        elif args.command == "reset-checkpoint":
            if not args.yes:
                raise LabError("Сброс удаляет только учебные копии, но теряет их изменения. Добавьте --yes.")
            reset_checkpoint(args.workspace, args.checkpoint)
            print("Учебный стенд восстановлен: " + args.checkpoint)
        elif args.command == "check":
            print(json.dumps(check(args.workspace, args.exercise), ensure_ascii=False))
        else:
            workspace, data = validate(args.workspace)
            print("Контрольная точка создания: " + data["checkpoint"])
            print("Состояние repo (обычные изменения после init сохраняются):")
            print(git(workspace, workspace / "repo", "status", "--short", "--branch"))
    except (LabError, OSError, ValueError, KeyError, StopIteration, zipfile.BadZipFile) as exc:
        print("Ошибка стенда: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
