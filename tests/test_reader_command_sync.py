"""The production sync changes reference regions only, including legacy HTML."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.reader_command_sync import START, END, synchronize_page, synchronize_readers


def reader(ending='\n'):
    return ('<html><head><style>keep-css</style></head><body data-storage-key="keep-notes">'
            '<article id="keep">unchanged prose</article>'
            '<script id="command-reference-data" type="application/json">[]</script>'
            '<script>const keepRuntime=42;\n' + START + '\nreturn [];\n}\n' + END +
            '\nconst keepRuntimeTail=17;</script></body></html>').replace('\n', ending)


PARSER = START + '\nreturn ["new"];\n}\n'
CARDS = [dict(name='printf', optionBoundary='first-operand', optionPrefix='-',
              flags=[dict(flag='-v VAR', action='literal </script> & note')])]


class ReaderCommandSyncTests(unittest.TestCase):
    def test_only_two_regions_change_and_result_is_idempotent(self):
        for ending in ('\n', '\r\n'):
            before = reader(ending)
            after = synchronize_page(before, CARDS, PARSER)
            self.assertEqual(synchronize_page(after, CARDS, PARSER), after)
            self.assertEqual(synchronize_page(after, CARDS, '// source comment\n' + PARSER), after)
            self.assertIn('<style>keep-css</style>', after)
            self.assertIn('data-storage-key="keep-notes"', after)
            self.assertIn('<article id="keep">unchanged prose</article>', after)
            self.assertIn('const keepRuntime=42;' + ending, after)
            self.assertIn('const keepRuntimeTail=17;', after)
            self.assertIn(PARSER.rstrip('\n').replace('\n', ending) + ending + END, after)
            self.assertIn('<\\/script>', after)
            from scripts.reader_command_sync import DATA
            self.assertEqual(json.loads(DATA.search(after)[2]), CARDS)
            self.assertEqual(after.count('</script>'), 2)

    def test_preserves_local_cards_and_non_owned_updates(self):
        from scripts.reader_command_sync import DATA
        local = [dict(name='iostat', version='Linux14'), dict(name='printf', old=True),
                 dict(name='vmstat', local=True), dict(name='ip', explanation='new')]
        before = reader().replace('>[]</script>', '>' + json.dumps(local) + '</script>')
        incoming = CARDS + [dict(name='ip', explanation='stale'), dict(name='other')]
        after = synchronize_page(before, incoming, PARSER)
        actual = json.loads(DATA.search(after)[2])
        self.assertEqual(actual, [local[0], CARDS[0], local[2], local[3]])
        self.assertEqual(synchronize_page(after, incoming, PARSER), after)

    def test_bad_second_reader_prevents_first_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for slug, page in [('bash', reader()), ('linux', reader().replace(END, 'missing'))]:
                (root/slug).mkdir()
                (root/slug/'index.html').write_text(page)
            before = (root/'bash/index.html').read_bytes()
            with self.assertRaises(ValueError):
                synchronize_readers(root, ['bash', 'linux'], CARDS, PARSER)
            self.assertEqual((root/'bash/index.html').read_bytes(), before)

    def test_reject_ambiguous_or_non_script_markers(self):
        for page in [reader() + START, reader() + END,
                     reader().replace('<script>const keepRuntime', '<pre>const keepRuntime'),
                     reader().replace(START, END).replace('return [];', START)]:
            with self.subTest(page=page):
                with self.assertRaises(ValueError):
                    synchronize_page(page, CARDS, PARSER)
        with self.assertRaises(ValueError):
            synchronize_page(reader(), CARDS, PARSER + '</script>')

    def test_only_named_readers_and_no_followed_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'bash').mkdir()
            (root/'bash/index.html').write_text(reader())
            (root/'private.html').write_text('leave alone')
            self.assertEqual(synchronize_readers(root, ['bash'], CARDS, PARSER), 1)
            self.assertEqual(synchronize_readers(root, ['bash'], CARDS, PARSER), 0)
            self.assertEqual((root/'private.html').read_text(), 'leave alone')
            (root/'linux').mkdir()
            (root/'linux/index.html').symlink_to(root/'bash/index.html')
            with self.assertRaises(ValueError):
                synchronize_readers(root, ['linux'], CARDS, PARSER)
