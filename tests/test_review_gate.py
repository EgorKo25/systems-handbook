import copy
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import review_gate as gate

HEAD = 'a' * 40
BASE = 'b' * 40
NEW = 'c' * 40
REPO = 'EgorKo25/systems-handbook'
PR = 10
PROJECT_ACTOR = 111
TECHNICAL_FILE = {'filename': 'scripts/review_gate.py', 'status': 'modified'}


def work_assignment(role, reporter, index):
    return {
        'role': role, 'reporter': reporter,
        'thread_id': f'00000000-0000-4000-8000-{index:012d}',
        'turn_id': f'00000000-0000-4000-8001-{index:012d}',
    }


def body(head=HEAD, base=BASE):
    rows = [f'- [x] {label} · отчёт приложен' for label in (*gate.ROLES.values(), gate.TEXT_REVIEW_LABEL)]
    binding = f'Голова PR `{head}` · текущая целевая база `{base}`'
    return '\n'.join(['- [x] Outside the block', gate.BEGIN, binding, *rows, gate.END])


class ReviewGateTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.key = self.create_signer('authority')
        self.signers = self.root / 'allowed_signers'
        public = self.key.with_suffix('.pub').read_text().split()[:2]
        self.signers.write_text(f'acceptor namespaces="{gate.NAMESPACE}" ' + ' '.join(public) + '\n')
        self.receipts = self.root / 'receipts'
        self.receipts.mkdir()
        self.file = self.receipts / f'{PR}.json'
        self.text_file = self.receipts / f'{PR}.text-review.json'
        self.policy_data = {
            'repository': REPO, 'base_ref': 'main',
            'authority': {'principal': 'acceptor', 'github_user_id': 112,
                          'allowed_signers': str(self.signers), 'receipts_dir': str(self.receipts)},
            'reporters': {role: f'codex/{role}' for role in gate.ROLES},
            'text_review': {
                'pr': PR, 'head': HEAD, 'base': BASE,
                'assignments': {
                    'authors': [work_assignment('author', 'codex/author', 1),
                                work_assignment('author', 'codex/coauthor', 2)],
                    'reader': work_assignment('reader', 'codex/reader', 3),
                    'text_reviewer': work_assignment('text_review', 'codex/text_review', 4),
                },
            },
        }
        self.policy = gate.policy_from_text(json.dumps(self.policy_data))
        self.pull = {'number': PR, 'state': 'open', 'draft': False, 'user': {'id': PROJECT_ACTOR},
                     'head': {'sha': HEAD}, 'base': {'sha': BASE, 'ref': 'main', 'repo': {'full_name': REPO}},
                     'body': body()}
        self.ref = {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': BASE}}
        self.manifest = {
            'schema': gate.NAMESPACE, 'repository': REPO, 'pr': PR, 'head': HEAD, 'base': BASE,
            'authority': 'acceptor',
            'reports': [{'role': role, 'reporter': f'codex/{role}', 'sha256': str(index) * 64,
                         'decision': 'accepted', 'outcome': 'passed', 'evidence': 'Recorded test inputs and result'}
                        for index, role in enumerate(gate.ROLES, 1)],
        }
        self.text_manifest = {field: value for field, value in self.manifest.items() if field != 'reports'}
        self.text_manifest['assignments'] = copy.deepcopy(self.policy['text_review']['assignments'])
        self.text_manifest['reader_report_sha256'] = self.manifest['reports'][-1]['sha256']
        self.text_manifest['report'] = {
            'role': 'text_review', 'reporter': 'codex/text_review',
            'sha256': '5' * 64, 'decision': 'accepted', 'outcome': 'passed',
            'evidence': 'Accepted independent review report', 'scope': 'All revised passages in Docker 11',
            'open_findings': 0, 'reader_text': True,
            'html': [{'path': 'docker/index.html', 'anchors': ['11-compose-lifecycle']}],
        }
        self.sign_text()

    def create_signer(self, name):
        key = self.root / name
        subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
        return key

    def sign(self, data=None, key=None, *, file=None):
        file = file or self.file
        file.with_suffix('.json.sig').unlink(missing_ok=True)
        raw = json.dumps(self.manifest).encode() if data is None else data
        file.write_bytes(raw)
        subprocess.run(['/usr/bin/ssh-keygen', '-Y', 'sign', '-f', str(key or self.key),
                        '-n', gate.NAMESPACE, str(file)], check=True, capture_output=True)
        return raw

    def sign_text(self, *, key=None):
        return self.sign(json.dumps(self.text_manifest).encode(), key, file=self.text_file)

    def api(self, second_pull=None, second_ref=None):
        return Mock(**{'get.side_effect': [self.pull, self.ref,
                                          second_pull or self.pull, second_ref or self.ref]})

    def check_signed(self):
        return gate.evaluate_live(self.api(), self.policy, PR)

    def sign_na(self, files=None):
        report = self.text_manifest['report']
        report.update(outcome='not_applicable', reader_text=False, html=[],
                      scope='Exact PR file list', evidence='Only the review gate changed',
                      technical_files=[TECHNICAL_FILE] if files is None else files)
        self.sign()
        return self.sign_text()

    def na_api(self, files, *, second_files=None, final_pull=None, final_ref=None):
        return Mock(**{'get.side_effect': [
            self.pull, self.ref, files, self.pull, self.ref,
            files if second_files is None else second_files,
            final_pull or self.pull, final_ref or self.ref,
        ]})

    def test_one_project_github_actor_and_distinct_work_assignments_pass(self):
        self.manifest['reports'][1].update(outcome='not_applicable', evidence='No frontend files changed')
        self.sign()
        result = self.check_signed()
        self.assertEqual(set(result['receipts']), set(gate.ROLES) | {'text_review'})
        self.assertEqual(result['receipts']['frontend']['outcome'], 'not_applicable')
        self.assertEqual((result['pr'], result['head'], result['base']), (PR, HEAD, BASE))
        self.assertEqual(self.pull['user'], {'id': PROJECT_ACTOR})
        self.assertEqual(result['receipts']['text_review']['reporter'], 'codex/text_review')

    def test_unchecked_rows_are_display_only(self):
        self.pull['body'] = self.pull['body'].replace('[x]', '[ ]')
        self.sign()
        self.assertEqual(self.check_signed()['pr'], PR)

    def test_checked_rows_and_missing_manifest_do_not_pass(self):
        with self.assertRaisesRegex(gate.Blocked, 'manifest or signature is unavailable'):
            self.check_signed()

    def test_wrong_signer_and_modified_bytes_fail(self):
        self.sign(key=self.create_signer('author'))
        with self.assertRaisesRegex(gate.Blocked, 'signature is not trusted'):
            self.check_signed()
        raw = self.sign()
        self.file.write_bytes(raw + b' ')
        with self.assertRaisesRegex(gate.Blocked, 'signature is not trusted'):
            self.check_signed()

    def test_signed_but_wrong_pr_head_and_base_fail(self):
        for field, value in {'pr': 11, 'head': NEW, 'base': NEW, 'authority': 'other', 'repository': 'other/repo'}.items():
            with self.subTest(field=field):
                modified = self.manifest | {field: value}
                self.sign(json.dumps(modified).encode())
                with self.assertRaisesRegex(gate.Blocked, 'exact PR/head/base or authority'):
                    self.check_signed()

    def test_missing_duplicated_or_unaccepted_reports_fail(self):
        cases = [
            (1, None, 'exactly four'),
            (1, {'role': 'factcheck'}, 'report source'),
            (1, {'reporter': 'codex/factcheck'}, 'report source'),
            (1, {'sha256': '1' * 64}, 'reused report digest'),
            (1, {'decision': 'requested'}, 'accepted decision'),
            (1, {'outcome': 'failed'}, 'accepted decision'),
            (1, {'outcome': 'not_applicable', 'evidence': ' '}, 'accepted decision'),
        ]
        for index, fields, error in cases:
            with self.subTest(fields=fields):
                modified = copy.deepcopy(self.manifest)
                if fields is None:
                    del modified['reports'][index]
                else:
                    modified['reports'][index].update(fields)
                self.sign(json.dumps(modified).encode())
                with self.assertRaisesRegex(gate.Blocked, error):
                    self.check_signed()

    def test_signed_duplicate_json_key_fails(self):
        self.sign(b'{"pr":11,' + json.dumps(self.manifest).encode()[1:])
        with self.assertRaisesRegex(gate.Blocked, 'duplicate JSON key'):
            self.check_signed()

    def test_pr_author_cannot_be_mapped_signer(self):
        self.pull['user']['id'] = 112
        with self.assertRaisesRegex(gate.Blocked, 'author cannot sign'):
            self.check_signed()

    def test_operator_policy_requires_distinct_external_trust(self):
        self.policy_data['reporters']['frontend'] = self.policy_data['reporters']['factcheck']
        with self.assertRaisesRegex(gate.Blocked, 'independent report'):
            gate.policy_from_text(json.dumps(self.policy_data))
        self.policy_data['authority']['allowed_signers'] = str(gate.CHECKOUT / 'allowed_signers')
        with self.assertRaisesRegex(gate.Blocked, 'outside the code checkout'):
            gate.policy_from_text(json.dumps(self.policy_data))

    def test_missing_duplicate_or_stale_block_fails(self):
        for invalid in [body().replace(gate.BEGIN, ''), body() + '\n' + body(), body(base=NEW),
                        body().replace('Фактчек', 'Фронтенд-тесты')]:
            with self.subTest(invalid=invalid):
                self.pull['body'] = invalid
                with self.assertRaises(gate.Blocked):
                    self.check_signed()

    def test_draft_and_outdated_base_fail(self):
        self.pull['draft'] = True
        with self.assertRaisesRegex(gate.Blocked, 'non-draft'):
            self.check_signed()
        self.pull['draft'] = False
        self.ref['object']['sha'] = NEW
        with self.assertRaisesRegex(gate.Blocked, 'current main'):
            self.check_signed()

    def test_rereads_pr_and_current_main(self):
        self.sign()
        moved = copy.deepcopy(self.pull)
        moved['head']['sha'] = NEW
        moved['body'] = body(head=NEW)
        with self.assertRaisesRegex(gate.Blocked, 'PR changed'):
            gate.evaluate_live(self.api(second_pull=moved), self.policy, PR)
        advanced = copy.deepcopy(self.ref)
        advanced['object']['sha'] = NEW
        with self.assertRaisesRegex(gate.Blocked, 'current main'):
            gate.evaluate_live(self.api(second_ref=advanced), self.policy, PR)

    def test_rereads_attestation(self):
        original = self.sign()
        text = self.text_file.read_bytes()
        with patch.object(gate, 'read_signed_manifest', side_effect=[original, text, original + b' ']):
            with self.assertRaisesRegex(gate.Blocked, 'manifest changed'):
                self.check_signed()

    def test_requires_fifth_row_and_separate_trusted_signature(self):
        self.sign()
        original_body = self.pull['body']
        row = next(line for line in original_body.splitlines() if gate.TEXT_REVIEW_LABEL in line)
        for invalid in (original_body.replace(row + '\n', ''), original_body.replace(row, row + '\n' + row)):
            with self.subTest(body=invalid):
                self.pull['body'] = invalid
                with self.assertRaisesRegex(gate.Blocked, 'expected one row for Ревью нейротекста'):
                    self.check_signed()
        self.pull['body'] = original_body
        self.text_file.with_suffix('.json.sig').unlink()
        with self.assertRaisesRegex(gate.Blocked, 'signed text review manifest or signature is unavailable'):
            self.check_signed()
        self.text_file.unlink()
        with self.assertRaisesRegex(gate.Blocked, 'signed text review manifest or signature is unavailable'):
            self.check_signed()
        self.sign_text(key=self.create_signer('different'))
        with self.assertRaisesRegex(gate.Blocked, 'text review manifest signature is not trusted'):
            self.check_signed()

    def test_signed_fifth_receipt_requires_exact_pair_and_trusted_reviewer(self):
        self.sign()
        for field, value in {'pr': PR + 1, 'head': NEW, 'base': NEW, 'authority': 'other'}.items():
            with self.subTest(field=field):
                original = self.text_manifest[field]
                self.text_manifest[field] = value
                self.sign_text()
                with self.assertRaisesRegex(gate.Blocked, 'signed text review manifest does not match'):
                    self.check_signed()
                self.text_manifest[field] = original
        self.text_manifest['report']['reporter'] = 'codex/reader'
        self.sign_text()
        with self.assertRaisesRegex(gate.Blocked, 'does not match trusted identity'):
            self.check_signed()

    def test_fifth_policy_rejects_work_assignment_collisions_with_common_actor(self):
        legacy = {field: value for field, value in self.policy_data.items() if field != 'text_review'}
        with self.assertRaisesRegex(gate.Blocked, 'invalid policy fields'):
            gate.policy_from_text(json.dumps(legacy))
        for field in ('reporter', 'thread_id', 'turn_id'):
            for pair in (('authors', 'reader'), ('authors', 'text_reviewer'), ('reader', 'text_reviewer')):
                with self.subTest(field=field, pair=pair):
                    policy = copy.deepcopy(self.policy_data)
                    assignments = policy['text_review']['assignments']
                    first = assignments['authors'][0] if pair[0] == 'authors' else assignments['reader']
                    assignments[pair[1]][field] = first[field]
                    with self.assertRaisesRegex(gate.Blocked, 'must be distinct|distinct full thread and turn IDs'):
                        gate.policy_from_text(json.dumps(policy))

    def test_fifth_policy_checks_role_path_and_full_work_id(self):
        for values, diagnostic in (
            ({'role': 'reader'}, 'invalid text review role assignment'),
            ({'reporter': 'codex/alternate/../reader'}, 'reporter paths'),
            ({'thread_id': 'short-id'}, 'distinct full thread and turn IDs'),
        ):
            with self.subTest(values=values):
                policy = copy.deepcopy(self.policy_data)
                policy['text_review']['assignments']['text_reviewer'].update(values)
                with self.assertRaisesRegex(gate.Blocked, diagnostic):
                    gate.policy_from_text(json.dumps(policy))

    def test_signed_fifth_assignments_must_match_current_policy_and_reader_receipt(self):
        self.sign()
        for field, value in (('pr', PR + 1), ('head', NEW), ('base', NEW)):
            with self.subTest(field=field):
                policy = copy.deepcopy(self.policy_data)
                policy['text_review'][field] = value
                with self.assertRaisesRegex(gate.Blocked, 'trusted text review assignment does not match'):
                    gate.evaluate_live(self.api(), gate.policy_from_text(json.dumps(policy)), PR)
        assignments = self.text_manifest['assignments']
        original = copy.deepcopy(assignments)
        for participant in (assignments['authors'][1], assignments['reader'], assignments['text_reviewer']):
            with self.subTest(role=participant['role']):
                old_turn = participant['turn_id']
                participant['turn_id'] = work_assignment('author', 'codex/other', 9)['turn_id']
                self.sign_text()
                with self.assertRaisesRegex(gate.Blocked, 'signed text review assignments do not match'):
                    self.check_signed()
                participant['turn_id'] = old_turn
        self.assertEqual(assignments, original)
        self.sign_text()
        self.manifest['reports'][-1]['sha256'] = '6' * 64
        self.sign()
        with self.assertRaisesRegex(gate.Blocked, 'does not match the accepted reader report'):
            self.check_signed()

    def test_fifth_pass_requires_accepted_evidence_coverage_anchors_and_closed_findings(self):
        self.sign()
        original = self.text_manifest['report']
        for values, error in (
            ({'decision': 'requested'}, 'accepted decision'),
            ({'evidence': ' '}, 'accepted decision'),
            ({'scope': ''}, 'accepted decision'),
            ({'open_findings': 1}, 'zero open findings'),
            ({'open_findings': False}, 'zero open findings'),
            ({'sha256': '1' * 64}, 'reused text review digest'),
            ({'sha256': 'no digest'}, 'text review digest'),
            ({'html': []}, 'requires final HTML and anchors'),
            ({'html': [{'path': 'docker/index.html', 'anchors': []}]}, 'invalid or duplicate text review anchors'),
            ({'html': [{'path': '../index.html', 'anchors': ['one']}]}, 'invalid or duplicate text review HTML path'),
            ({'reader_text': False}, 'passed text review requires reader text'),
        ):
            with self.subTest(values=values):
                self.text_manifest['report'] = original | values
                self.sign_text()
                with self.assertRaisesRegex(gate.Blocked, error):
                    self.check_signed()

    def test_fifth_na_requires_signed_no_reader_text_rationale(self):
        files = [{'filename': path, 'status': 'added'} for path in (
            '.github/PULL_REQUEST_TEMPLATE.md', 'scripts/review_gate.py', 'tests/test_review_gate.py',
        )]
        self.pull['changed_files'] = len(files)
        raw = self.sign_na(files)
        report = self.text_manifest['report']
        actual = [file | {'sha': 'e' * 40} for file in reversed(files)]
        api = self.na_api(actual)
        result = gate.evaluate_live(api, self.policy, PR)
        self.assertEqual(result['receipts']['text_review']['outcome'], 'not_applicable')
        endpoint = f'/pulls/{PR}/files?per_page=100&page=1'
        file_calls = [call for call in api.get.call_args_list if call.args[0] == endpoint]
        self.assertEqual([call.kwargs for call in file_calls], [{'single_page': True}] * 2)
        for values, error in (({'reader_text': True}, 'N/A requires'),
                              ({'evidence': ''}, 'accepted decision'),
                              ({'open_findings': 1}, 'zero open findings')):
            with self.subTest(values=values):
                self.text_manifest['report'] = report | values
                self.sign_text()
                with self.assertRaisesRegex(gate.Blocked, error):
                    self.check_signed()
        self.text_file.write_bytes(raw)
        with self.assertRaisesRegex(gate.Blocked, 'text review manifest signature is not trusted'):
            self.check_signed()

    def test_fifth_na_accepts_exact_pr12_technical_delta(self):
        pr = 12
        head = 'e6d7176ea49047baf0d707957b62bb99b5ae1f6a'
        base = 'b20a374d2049085c2bb59144ff2ed23c70e48edd'
        binding = {'pr': pr, 'head': head, 'base': base}
        self.policy_data['text_review'].update(binding)
        self.policy = gate.policy_from_text(json.dumps(self.policy_data))
        self.manifest.update(binding)
        self.text_manifest.update(binding)
        self.file = self.receipts / f'{pr}.json'
        self.text_file = self.receipts / f'{pr}.text-review.json'
        files = [{'filename': path, 'status': 'added'} for path in (
            'scripts/ops/plan_reserve_cleanup.py',
            'scripts/ops/reserve-cleanup.md',
            'tests/test_plan_reserve_cleanup.py',
        )]
        self.pull.update(number=pr, head={'sha': head}, base=self.pull['base'] | {'sha': base},
                         body=body(head, base), changed_files=len(files))
        self.ref['object']['sha'] = base
        self.sign_na(files)
        api = self.na_api(list(reversed(files)))
        result = gate.evaluate_live(api, self.policy, pr)
        self.assertEqual(result['receipts']['text_review']['outcome'], 'not_applicable')
        endpoint = f'/pulls/{pr}/files?per_page=100&page=1'
        self.assertEqual([call.args[0] for call in api.get.call_args_list].count(endpoint), 2)

    def test_fifth_na_rejects_chapter_text_in_actual_pr_files(self):
        self.assert_visible_file_blocks_na('docker/sources/11-compose-lifecycle.html', '<p>Новый абзац</p>')

    def test_fifth_na_rejects_reader_diagram_caption(self):
        self.assert_visible_file_blocks_na('git/index.html', '<figcaption>Новая подпись</figcaption>')

    def test_fifth_na_rejects_reader_diagram_alt(self):
        self.assert_visible_file_blocks_na('git/index.html', '<img src="diagram.svg" alt="Новое описание">')

    def test_fifth_na_rejects_catalog_generator_text(self):
        self.assert_visible_file_blocks_na('scripts/library_structure.py', 'practice_note = "Новый текст каталога"')

    def assert_visible_file_blocks_na(self, filename, change):
        self.pull['changed_files'] = 1
        self.sign_na()
        visible = {'filename': filename, 'status': 'modified', 'patch': f'@@ -1 +1 @@\n+{change}'}
        with self.assertRaisesRegex(gate.Blocked, 'explicitly allowlisted technical paths'):
            gate.evaluate_live(self.na_api([visible]), self.policy, PR)

    def test_fifth_na_checks_both_rename_paths(self):
        self.pull['changed_files'] = 1
        allowed = {'filename': 'tests/test_review_gate.py', 'status': 'renamed',
                   'previous_filename': TECHNICAL_FILE['filename']}
        self.sign_na([allowed])
        gate.evaluate_live(self.na_api([allowed]), self.policy, PR)
        for field in ('filename', 'previous_filename'):
            with self.subTest(field=field):
                visible = allowed | {field: 'git/sources/diagram.svg'}
                with self.assertRaisesRegex(gate.Blocked, 'explicitly allowlisted technical paths'):
                    gate.evaluate_live(self.na_api([visible]), self.policy, PR)
        with self.assertRaisesRegex(gate.Blocked, 'incomplete text review N/A file entry'):
            gate.evaluate_live(self.na_api([{'filename': allowed['filename'], 'status': 'renamed'}]), self.policy, PR)

    def test_fifth_na_requires_complete_count_and_file_list(self):
        self.sign_na()
        for count, files, diagnostic in (
            (None, [TECHNICAL_FILE], 'complete technical changed_files count'),
            (True, [TECHNICAL_FILE], 'complete technical changed_files count'),
            (101, [TECHNICAL_FILE], 'complete technical changed_files count'),
            (2, [TECHNICAL_FILE], 'incomplete GitHub file list'),
            (1, [TECHNICAL_FILE, TECHNICAL_FILE], 'incomplete GitHub file list'),
            (2, [TECHNICAL_FILE, TECHNICAL_FILE], 'duplicate or invalid'),
            (1, {'unexpected': TECHNICAL_FILE}, 'incomplete GitHub file list'),
            (1, [TECHNICAL_FILE | {'status': 'unknown'}], 'unrecognized'),
            (1, [TECHNICAL_FILE | {'status': 'added'}], 'does not match the GitHub file list'),
            (1, gate.Blocked('GitHub GET network failure'), 'network failure'),
        ):
            with self.subTest(count=count, files=files):
                self.pull['changed_files'] = count
                with self.assertRaisesRegex(gate.Blocked, diagnostic):
                    gate.evaluate_live(self.na_api(files), self.policy, PR)

    def test_fifth_na_rereads_exact_pair_count_and_file_scope(self):
        self.pull['changed_files'] = 1
        self.sign_na()
        files = [TECHNICAL_FILE]
        cases = (
            ({'second_files': [TECHNICAL_FILE | {'status': 'added'}]}, 'file list changed'),
            ({'final_pull': self.pull | {'head': {'sha': NEW}, 'body': body(head=NEW)}}, 'PR or changed_files changed'),
            ({'final_pull': self.pull | {'changed_files': 2}}, 'PR or changed_files changed'),
            ({'final_ref': self.ref | {'object': {'type': 'commit', 'sha': NEW}}}, 'current main'),
        )
        for options, diagnostic in cases:
            with self.subTest(options=options):
                with self.assertRaisesRegex(gate.Blocked, diagnostic):
                    gate.evaluate_live(self.na_api(files, **options), self.policy, PR)

    def test_fifth_na_rejects_pagination_header_even_with_the_expected_number_of_files(self):
        self.pull['changed_files'] = 1
        self.sign_na()
        response = BytesIO(json.dumps([TECHNICAL_FILE]).encode())
        response.headers = {'Link': '<https://api.github.com/example?page=2>; rel="next"'}
        api = gate.GitHub(REPO)
        api.opener.open = Mock(return_value=response)
        github_get = api.get
        metadata = iter((self.pull, self.ref))
        with patch.object(api, 'get', side_effect=lambda path, **kw: github_get(path, **kw) if kw else next(metadata)):
            with self.assertRaisesRegex(gate.Blocked, 'unexpected pagination'):
                gate.evaluate_live(api, self.policy, PR)

    def test_rereads_fifth_attestation(self):
        original = self.sign()
        text = self.text_file.read_bytes()
        with patch.object(gate, 'read_signed_manifest', side_effect=[original, text, original, text + b' ']):
            with self.assertRaisesRegex(gate.Blocked, 'text review manifest changed'):
                self.check_signed()


if __name__ == '__main__':
    unittest.main()
