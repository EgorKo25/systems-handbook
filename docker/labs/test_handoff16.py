"""Run the book's literal post-up mount check on own JSON; no Docker/Engine."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

DOCKER = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:' + 'a' * 64


class HandoffCode(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag == 'pre' and dict(attrs).get('data-handoff16') == 'retained-world':
            self.active = True
            self.blocks.append('')

    def handle_data(self, data):
        if self.active:
            self.blocks[-1] += data

    def handle_endtag(self, tag):
        if tag == 'pre':
            self.active = False


def literal_after():
    source = DOCKER / 'sources/16-integrated-lab.html'
    path = source if source.is_file() else DOCKER / 'index.html'
    parser = HandoffCode()
    parser.feed(path.read_text(encoding='utf-8'))
    if len(parser.blocks) != 1:
        raise ValueError('Expected one retained-world handoff block: ' + str(path))
    matches = re.findall(r"<<'AFTER'\n(.*?)\nAFTER(?:\n|$)", parser.blocks[0], re.S)
    if len(matches) != 1:
        raise ValueError('Expected one literal AFTER heredoc: ' + str(path))
    return matches[0]


class HandoffMountChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = literal_after()

    def base(self):
        return {'Image': IMAGE, 'State': {'Status': 'running'},
                'Config': {'User': '10001:10001', 'Labels': {
                    'com.docker.compose.project': 'study-docker',
                    'com.docker.compose.service': 'echo'}},
                'Mounts': [{'Destination': '/data', 'Type': 'volume',
                            'Name': 'study-data', 'RW': True}]}

    def check_fixture(self, obj):
        with tempfile.TemporaryDirectory(prefix='handoff16-after-own-') as td:
            path = Path(td) / 'inspect.json'
            path.write_text(json.dumps([obj]), encoding='utf-8')
            before = path.read_bytes()
            result = subprocess.run([sys.executable, '-I', '-B', '-c', self.code,
                                     str(path), IMAGE], capture_output=True,
                                    text=True, timeout=5)
            self.assertEqual(path.read_bytes(), before)
            return result

    def test_parent_data_volume_accepted(self):
        result = self.check_fixture(self.base())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unrelated_tmp_mount_accepted(self):
        obj = self.base()
        obj['Mounts'].append({'Destination': '/tmp', 'Type': 'tmpfs', 'RW': True})
        result = self.check_fixture(obj)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_nested_counter_mount_rejected(self):
        obj = self.base()
        obj['Mounts'].append({'Destination': '/data/counter', 'Type': 'bind',
                              'Source': 'own-file-with-the-same-N', 'RW': True})
        result = self.check_fixture(obj)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Фактический объект Compose не прошёл проверку', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
