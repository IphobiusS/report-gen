"""Regression checks for acceptance evidence, not substitutes for Atlas exports."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def runner():
    spec = importlib.util.spec_from_file_location('atlas_acceptance_test', ROOT / 'scripts/audit-atlas-exports.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_catalog_is_exercised_in_every_language_without_duplicate_jobs():
    module = runner()
    plan = module.catalog_plan()
    assert len({row['key'] for row in plan}) == len(plan)
    for language in module.LANGUAGES:
        rows = [row for row in plan if row['language'] == language]
        assert {row['profile'] for row in rows if 'profile' in row} == {
            profile['id'] for profile in module.design_library.catalog()['profiles']}
        assert {row['theme'] for row in rows if 'theme' in row} == module.THEMES
        complete = [row for row in rows if row['scope'] == 'complete_case']
        assert len(complete) == 1
        assert set(complete[0]['formats']) == set(module.delivery.FORMATS)
        for layout in module.design_library.LAYOUTS:
            assert {row['variant'] for row in rows if row.get('layout') == layout} == set(module.design_library.VARIANTS)


def test_failed_or_absent_jobs_cannot_satisfy_catalog_coverage():
    module = runner()
    plan = module.catalog_plan()
    successful = [dict(key=row['key'], status='passed') for row in plan]
    english = next(row for row in plan if row['language'] == 'en' and row.get('profile') == 'htb-cape')
    failed = [{**row, 'status': 'failed'} if row['key'] == english['key'] else row for row in successful]
    result = module.verified_coverage(plan, failed)
    assert english['key'] in result['missing_jobs']
    assert 'htb-cape' in result['missing_per_language']['en']['profiles']
    # A valid Spanish copy cannot hide missing English execution.
    assert 'htb-cape' not in result['missing_per_language']['es']['profiles']
    assert module.verified_coverage(plan, [])['completed_jobs'] == 0


def test_a_new_catalog_profile_cannot_silently_disappear_from_the_matrix(monkeypatch):
    module = runner()
    original = module.design_library.catalog()
    extra = {**original['profiles'][0], 'id': 'test-extra-layout-profile'}
    monkeypatch.setattr(module.design_library, 'catalog', lambda: {**original, 'profiles': original['profiles'] + [extra]})
    plan = module.catalog_plan()
    for language in module.LANGUAGES:
        assert any(row.get('profile') == extra['id'] and row['language'] == language for row in plan)
    baseline_jobs = [dict(key=row['key'], status='passed') for row in plan if row.get('profile') != extra['id']]
    missing = module.verified_coverage(plan, baseline_jobs)
    assert extra['id'] in missing['missing_values']['profiles']
