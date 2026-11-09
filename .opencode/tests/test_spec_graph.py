import json
from pathlib import Path
import re
import unittest
import test_gates as gate_tests


MASTER = 'docs/specs/F12-export/master.md'
S1 = 'docs/specs/F12-export/stories/S1-csv.md'
S2 = 'docs/specs/F12-export/stories/S2-json.md'
S3 = 'docs/specs/F12-export/stories/S3-ui.md'
C1 = 'docs/specs/F12-export/corrections/S1-C1-format.md'
C2 = 'docs/specs/F12-export/corrections/S1-C2-format.md'


def link(path):
    return '[[' + path.removesuffix('.md') + ']]'


class SpecTests(unittest.TestCase):
    setUp = gate_tests.RepoTests.setUp
    tearDown = gate_tests.RepoTests.tearDown
    git = gate_tests.RepoTests.git
    write = gate_tests.RepoTests.write
    commit = gate_tests.RepoTests.commit
    cli = gate_tests.RepoTests.cli

    def spec(self, path, ident, kind='story', parent=MASTER, **fields):
        data = dict(schema='spec/v1', id=ident, kind=kind, title='Export',
                    parent=link(parent) if parent else None, depends_on=[])
        if kind != 'master':
            data.update(blockers=[], writes=['src/' + ident + '/'], reads=[], resources=[])
        data.update(fields)
        body = '# Export\n'
        if kind != 'master':
            body += '\n### AC-' + ident + '-01 Export\nGiven orders\nWhen export\nThen file\nПроверка: stand\n'
        header = '\n'.join(k + ': ' + (v if isinstance(v, str) and not v.startswith('[[')
                                      else json.dumps(v)) for k, v in data.items())
        self.write(path, '---\n' + header + '\n---\n' + body)

    def feature(self):
        self.spec(MASTER, 'F12', 'master', None, stories=[link(S1), link(S2), link(S3)])
        self.spec(S1, 'F12-S1')
        self.spec(S2, 'F12-S2')
        self.spec(S3, 'F12-S3', depends_on=[link(S1), link(S2)])
        return self.commit()

    def correction(self, path=C1, ident='F12-S1-C1', old=S1, old_id='F12-S1'):
        self.spec(path, ident, 'correction', S1, corrects=[link(old)],
                  supersedes=['AC-' + old_id + '-01'])

    def graph(self, status=0, *args):
        return self.cli(status, 'spec-graph', '--spec', MASTER, *args)

    def contract(self, path=S1, status=0, *args):
        return self.cli(status, 'contract', '--spec', path, '--arch', 'docs/arch/1.md', *args)

    def plan(self, *args, status=0):
        return self.cli(status, 'spec-plan', '--spec', MASTER, *args)

    def test_independent_stories_then_dependent_story(self):
        self.feature()
        self.assertEqual(['F12-S1', 'F12-S2'], self.plan()['ready'])
        self.assertIn('depends_on:F12-S1', self.plan()['blocked']['F12-S3'])
        self.assertEqual(['F12-S3'], self.plan('--completed', 'F12-S1', '--completed', 'F12-S2')['ready'])

    def test_single_story_is_still_required(self):
        self.spec(MASTER, 'F12', 'master', None, stories=[])
        self.commit()
        self.graph(2)
        self.spec(MASTER, 'F12', 'master', None, stories=[link(S1)])
        self.spec(S1, 'F12-S1')
        self.commit()
        self.assertEqual(['F12-S1'], self.plan()['ready'])

    def test_missing_story_and_dependency_are_errors(self):
        self.feature()
        (self.root / S2).unlink()
        self.commit()
        self.graph(2)
        self.spec(S2, 'F12-S2', depends_on=[link('docs/specs/missing.md')])
        self.commit()
        self.graph(2)

    def test_dependency_cycle_blocks_plan(self):
        self.feature()
        self.spec(S1, 'F12-S1', depends_on=[link(S3)])
        self.commit()
        self.plan(status=2)

    def test_parent_cycle_blocks_graph(self):
        self.feature()
        self.spec(S1, 'F12-S1', parent=S1)
        self.commit()
        self.graph(2)

    def test_story_requires_correct_parent_and_namespace(self):
        self.feature()
        self.spec(S1, 'F13-S1')
        self.commit()
        self.graph(2)

    def test_invalid_ac_is_error(self):
        self.feature()
        p = self.root / S1
        p.write_text(p.read_text().replace('Проверка: stand', 'Проверка: later'))
        self.commit()
        self.graph(2)

    def test_file_directory_and_read_conflicts_serialize(self):
        self.feature()
        self.spec(S1, 'F12-S1', writes=['src/shared/'])
        self.spec(S2, 'F12-S2', reads=['src/shared/Dto.java'])
        self.commit()
        plan = self.plan()
        self.assertEqual(['F12-S1'], plan['ready'])
        self.assertTrue(any(r.startswith('conflict:') for r in plan['blocked']['F12-S2']))

    def test_resource_conflicts_and_capacity(self):
        self.feature()
        self.spec(S1, 'F12-S1', resources=['db:orders'])
        self.spec(S2, 'F12-S2', resources=['db:orders'])
        self.commit()
        self.assertEqual([], self.plan('--active', 'F12-S1')['ready'])
        self.plan('--active', 'F12-S1', '--active', 'F12-S2', status=2)
        self.plan('--limit', '0', status=2)

    def test_external_blocker_closes_without_editing_spec(self):
        self.feature()
        self.spec(S1, 'F12-S1', blockers=['decision:encoding'])
        self.commit()
        before = self.contract()['snapshot']
        self.assertEqual(['F12-S2'], self.plan()['ready'])
        self.assertEqual(['F12-S1', 'F12-S2'], self.plan('--resolved-blocker', 'decision:encoding')['ready'])
        self.assertEqual(before, self.contract()['snapshot'])

    def test_story_snapshot_excludes_sibling_includes_prerequisites(self):
        self.feature()
        one, three = self.contract()['snapshot'], self.contract(S3)['snapshot']
        self.spec(S2, 'F12-S2', resources=['api:json'])
        self.commit()
        self.contract(S1, 0, '--expected', one)
        self.contract(S3, 1, '--expected', three)

    def test_master_snapshot_covers_all_initial_stories(self):
        self.feature()
        approved = self.contract(MASTER)['snapshot']
        self.spec(S2, 'F12-S2', resources=['api:json'])
        self.commit()
        self.contract(MASTER, 1, '--expected', approved)

    def test_correction_does_not_rewrite_or_invalidate_originals(self):
        frozen = self.feature()
        baseline = self.contract(MASTER)['snapshot']
        self.correction()
        self.commit()
        self.graph(0, '--baseline', frozen)
        self.contract(MASTER, 0, '--expected', baseline)
        files = self.contract(C1)['files']
        self.assertIn(S1, files)
        self.assertIn(MASTER, files)
        self.assertNotIn(S2, files)
        self.assertIn('depends_on:F12-S1', self.plan()['blocked']['F12-S1-C1'])
        self.assertIn('F12-S1-C1', self.plan('--completed', 'F12-S1')['ready'])

    def test_frozen_spec_edit_is_rejected(self):
        frozen = self.feature()
        self.spec(S2, 'F12-S2', resources=['api:changed'])
        self.commit()
        self.assertEqual([S2], self.graph(1, '--baseline', frozen)['changed'])

    def test_frozen_spec_deletion_or_rename_cannot_pass(self):
        frozen = self.feature()
        (self.root / S1).rename(self.root / S1.replace('csv', 'renamed'))
        self.commit()
        self.graph(2, '--baseline', frozen)

    def test_correction_chain_and_competing_corrections(self):
        self.feature()
        self.correction()
        self.correction(C2, 'F12-S1-C2', C1, 'F12-S1-C1')
        self.commit()
        self.graph()
        self.assertIn('depends_on:F12-S1-C1', self.plan()['blocked']['F12-S1-C2'])
        self.correction(C2, 'F12-S1-C2')
        self.commit()
        self.graph(2)

    def test_cross_story_correction_and_unknown_ac_rejected(self):
        self.feature()
        self.correction(old=S2, old_id='F12-S2')
        self.commit()
        self.graph(2)
        self.correction(old_id='F12-S1-NONEXISTENT')
        self.commit()
        self.graph(2)

    def test_active_unit_requires_completed_prerequisites(self):
        self.feature()
        self.plan('--active', 'F12-S3', status=2)
        self.plan('--completed', 'unknown', status=2)
        self.plan('--completed', 'F12-S1', '--active', 'F12-S1', status=2)

    def test_paths_symlinks_and_frontmatter_are_fail_closed(self):
        self.feature()
        self.spec(S1, 'F12-S1', writes=['src/**'])
        self.commit()
        self.graph(2)
        self.spec(S1, 'F12-S1', depends_on=['[[docs/specs/../../outside]]'])
        self.commit()
        self.graph(2)
        (self.root / S1).unlink()
        (self.root / S1).symlink_to('S2-json.md')
        self.commit()
        self.graph(2)

    def test_scope_catches_unplanned_file_and_exempts_only_own_qa(self):
        base = self.feature()
        self.write('src/F12-S1/Export.java', 'class Export {}')
        self.write('docs/qa/F12/S1.md', 'PASS')
        self.commit()
        args = ('spec-scope', '--spec', S1, '--base', base, '--qa-report', 'docs/qa/F12/S1.md')
        self.cli(0, *args)
        self.write('src/shared/Dto.java', 'class Dto {}')
        self.commit()
        self.assertEqual(['src/shared/Dto.java'], self.cli(1, *args)['outside_scope'])

    def test_scope_forbids_spec_changes_even_with_broad_write_scope(self):
        self.feature()
        self.spec(S1, 'F12-S1', writes=['docs/'])
        base = self.commit()
        self.spec(S2, 'F12-S2', resources=['api:json'])
        self.commit()
        self.cli(1, 'spec-scope', '--spec', S1, '--base', base)


    def test_effective_ac_ignores_pending_correction_and_replaces_only_when_selected(self):
        self.feature()
        self.correction()
        self.correction(C2, 'F12-S1-C2', C1, 'F12-S1-C1')
        self.commit()
        args = ('spec-effective', '--spec', MASTER, '--integrated', 'F12-S1')
        old = self.cli(0, *args)
        self.assertEqual(['AC-F12-S1-01'], list(old['active_ac']))
        future = self.cli(0, *args, '--include', 'F12-S1-C1')
        self.assertEqual(['AC-F12-S1-C1-01'], list(future['active_ac']))
        latest = self.cli(0, *args, '--integrated', 'F12-S1-C1', '--include', 'F12-S1-C2')
        self.assertEqual(['AC-F12-S1-C2-01'], list(latest['active_ac']))
        self.cli(2, *args, '--include', 'F12-S1-C2')

    def test_unapproved_candidate_does_not_consume_capacity(self):
        self.feature()
        self.assertEqual(['F12-S2'], self.plan('--candidate', 'F12-S2', '--limit', '1')['ready'])
        self.plan('--candidate', 'unknown', status=2)

    def test_actual_templates_form_valid_graph(self):
        templates = Path(__file__).resolve().parents[1] / 'skills/write-spec'
        values = dict(F='12', N='1', K='1', SLUG='export', STORY_SLUG='csv',
                      TITLE='Export', REPO_PATH='src/export')
        for template, path in [('spec-template.md', MASTER), ('story-template.md', S1),
                               ('correction-template.md', C1)]:
            text = (templates / template).read_text()
            text = re.sub(r'\{\{(.*?)\}\}', lambda m: values.get(m[1], 'Описание'), text, flags=re.S)
            self.write(path, text)
        self.commit()
        self.graph()
        self.assertEqual(['F12-S1'], self.plan()['ready'])

    def test_only_correction_can_supersede_ac(self):
        self.feature()
        self.spec(S2, 'F12-S2', supersedes=['AC-F12-S1-01'])
        self.commit()
        self.graph(2)

    def test_duplicate_id_and_malformed_metadata_are_errors(self):
        self.feature()
        self.spec('docs/specs/duplicate.md', 'F12', 'master', None, stories=[link(S1)])
        self.commit()
        self.graph(2)
        (self.root / 'docs/specs/duplicate.md').unlink()
        self.spec(S2, 'F12-S2', title=['not a title'])
        self.commit()
        self.graph(2)

    def test_global_resource_conflict_with_active_other_feature(self):
        self.feature()
        other_master = 'docs/specs/F99-other/master.md'
        other_story = 'docs/specs/F99-other/stories/S1-api.md'
        self.spec(other_master, 'F99', 'master', None, stories=[link(other_story)])
        self.spec(other_story, 'F99-S1', parent=other_master, resources=['api:orders'])
        self.spec(S1, 'F12-S1', resources=['api:orders'])
        self.commit()
        plan = self.plan('--active', 'F99-S1')
        self.assertEqual(['F12-S2'], plan['ready'])
        self.assertIn('conflict:F99-S1:api:orders', plan['blocked']['F12-S1'])

    def test_candidate_priority_order_is_respected(self):
        self.feature()
        self.spec(S1, 'F12-S1', resources=['db:orders'])
        self.spec(S2, 'F12-S2', resources=['db:orders'])
        self.commit()
        self.assertEqual(['F12-S2'], self.plan('--candidate', 'F12-S2', '--candidate', 'F12-S1')['ready'])


if __name__ == '__main__':
    unittest.main()
