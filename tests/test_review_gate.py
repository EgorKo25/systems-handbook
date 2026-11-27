import copy
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


def body(head=HEAD, base=BASE):
    rows = [f'- [x] {label} · отчёт приложен' for label in gate.ROLES.values()]
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
        self.policy_data = {
            'repository': REPO, 'base_ref': 'main',
            'authority': {'principal': 'acceptor', 'github_user_id': 112,
                          'allowed_signers': str(self.signers), 'receipts_dir': str(self.receipts)},
            'reporters': {role: f'codex/{role}' for role in gate.ROLES},
        }
        self.policy = gate.policy_from_text(json.dumps(self.policy_data))
        self.pull = {'number': PR, 'state': 'open', 'draft': False, 'user': {'id': 111},
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

    def create_signer(self, name):
        key = self.root / name
        subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
        return key

    def sign(self, data=None, key=None):
        self.file.with_suffix('.json.sig').unlink(missing_ok=True)
        raw = json.dumps(self.manifest).encode() if data is None else data
        self.file.write_bytes(raw)
        subprocess.run(['/usr/bin/ssh-keygen', '-Y', 'sign', '-f', str(key or self.key),
                        '-n', gate.NAMESPACE, str(self.file)], check=True, capture_output=True)
        return raw

    def api(self, second_pull=None, second_ref=None):
        return Mock(**{'get.side_effect': [self.pull, self.ref,
                                          second_pull or self.pull, second_ref or self.ref]})

    def check_signed(self):
        return gate.evaluate_live(self.api(), self.policy, PR)

    def test_real_signature_and_four_reports_pass(self):
        self.manifest['reports'][1].update(outcome='not_applicable', evidence='No frontend files changed')
        self.sign()
        result = self.check_signed()
        self.assertEqual(set(result['receipts']), set(gate.ROLES))
        self.assertEqual(result['receipts']['frontend']['outcome'], 'not_applicable')
        self.assertEqual((result['pr'], result['head'], result['base']), (PR, HEAD, BASE))

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
        with patch.object(gate, 'read_signed_manifest', side_effect=[original, original + b' ']):
            with self.assertRaisesRegex(gate.Blocked, 'manifest changed'):
                self.check_signed()


if __name__ == '__main__':
    unittest.main()
