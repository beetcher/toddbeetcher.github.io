#!/usr/bin/env python3
"""Explicit Hosting/API smoke check; preserves and archives its validation records.

Key is read from a private file, never command arguments or output. Supports an
emulator or explicitly selected HTTPS origin. Saves only non-secret evidence.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--key-file', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--verify-manifest', help='Read back previous evidence after restart/redeployment; no writes')
    parser.add_argument('--browser', action='store_true')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    assert base.startswith('https://') or base.startswith('http://127.0.0.1:'), 'HTTPS or loopback required'
    key = Path(args.key_file).read_text().strip().removeprefix('READY_API_KEY=')
    assert len(key) >= 32
    evidence = Path(args.evidence)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    artifacts = evidence.parent

    def raw(method, path, data=None, auth=True, expected=(200, 201), extra=None):
        time.sleep(0.38)  # Stay below the documented per-address request budget.
        headers = {'Content-Type': 'application/json', **(extra or {})}
        if auth:
            headers['Authorization'] = 'Bearer ' + key
        req = Request(base + path, data=None if data is None else json.dumps(data).encode(), headers=headers, method=method)
        try:
            response = urlopen(req, timeout=90)
        except HTTPError as error:
            response = error
        body = response.read()
        assert response.status in expected, (method, path, response.status, body[:600])
        return response.status, response.headers, body

    def api(method, path, data=None, **kwargs):
        code, headers, body = raw(method, '/v1/' + path, data, **kwargs)
        envelope = json.loads(body)
        assert envelope['ok'], (path, envelope)
        return envelope['data']

    assert api('GET', 'health', auth=False)['status'] == 'ok'
    raw('GET', '/v1/questions', auth=False, expected=(401,))
    assert api('GET', 'capabilities')['persistence'] == 'FirestoreStore'
    for path, mime in [('/ready/', 'text/html'), ('/ready/style.css', 'text/css'), ('/ready/main.js', 'javascript'), ('/ready/seed.json', 'application/json')]:
        _, headers, body = raw('GET', path, auth=False)
        assert mime in headers['Content-Type'] and key.encode() not in body

    if args.verify_manifest:
        prior = json.loads(Path(args.verify_manifest).read_text())
        assert prior['origin'] == base
        for row in prior['retained']:
            current = api('GET', row['kind'] + '/' + row['id'])
            assert current['id'] == row['id'] and current['is_archived']
        test = api('GET', 'tests/' + prior['test_id'])
        assert test['items'] == prior['frozen_items']
        evidence.write_text(json.dumps({'origin': base, 'checked_at': datetime.now(timezone.utc).isoformat(), 'durability_readback': len(prior['retained']), 'passed': True}, indent=2))
        print('Hosting durability readback passed; archived records and frozen test survived restart/redeployment.')
        return

    seed = json.loads(raw('GET', '/ready/seed.json', auth=False)[2])
    validation_tag = 'hosting_' + uuid4().hex
    for kind in ['questions', 'answers', 'sets']:
        for row in seed[kind]:
            metadata = row.get('data', row).setdefault('metadata', {})
            metadata.setdefault('tags', []).append(validation_tag)
    # Isolated builder validation variant: exercise authored half-credit too.
    for row in seed['sets']:
        connection = next(c for c in row['connections'] if c['role'] == 'incorrect')
        connection.update(role='ambiguous', feedback='Synthetic half-credit option for deployment verification.')
    seed.update(dry_run=True, idempotency_key=str(uuid4()))
    count_before = api('GET', 'questions')['count']
    assert api('POST', 'content/imports', seed)['is_valid']
    assert api('GET', 'questions')['count'] == count_before
    seed['dry_run'] = False
    imported = api('POST', 'content/imports', seed)
    assert Counter(row['type'] for row in imported['created']) == {'question': 10, 'answer': 38, 'question_answer_set': 10}
    assert api('POST', 'content/imports', seed)['created'] == imported['created']
    sets = [row['id'] for row in imported['created'] if row['type'] == 'question_answer_set'][:2]
    shortage = api('POST', 'selections', {'target': 'sets', 'mode': 'ordered', 'count': 20, 'criteria': {'tags': [validation_tag]}})
    assert shortage['found_count'] == 10 and shortage['shortfall_count'] == 10
    origin = {'author': 'READY builder', 'authorship_kind': 'system', 'source_reference': 'Hosting validation'}
    request = {'label': 'Hosting validation', 'metadata': {'tags': ['system_validation']}, 'origin': origin,
               'set_ids': sets + sets, 'allow_duplicates': True, 'duplicate_pair_count': 2}
    test_key = str(uuid4())
    test = api('POST', 'tests', request, extra={'Idempotency-Key': test_key})
    assert api('POST', 'tests', request, extra={'Idempotency-Key': test_key})['id'] == test['id']
    assert len({row['item_id'] for row in test['items']}) == 4
    assert set(Counter(row['question_id'] for row in test['items']).values()) == {2}
    variant = api('POST', 'tests/' + test['id'] + '/variants', {**request, 'label': 'Hosting validation variant'}, extra={'Idempotency-Key': str(uuid4())})
    assert variant['id'] != test['id']
    question = api('GET', 'questions/' + test['items'][0]['question_id'])
    revised = api('PATCH', 'questions/' + question['id'], {'question_text': question['question_text'] + ' [validation revision]'}, extra={'If-Match': '"' + str(question['record_version']) + '"'})
    assert revised['id'] != question['id'] and revised['previous_id'] == question['id']
    assert api('GET', 'tests/' + test['id'])['items'] == test['items']
    retained = []
    attempts = []
    for role, expected in [('strong', 4), ('ambiguous', 2), ('incorrect', 0)]:
        report = {'test_id': test['id'], 'person_id': 'hosting-validation-' + test['id'], 'test_taken_at': '2026-10-28T12:00:00Z',
                  'responses': [{'item_id': row['item_id'], 'answer_ids': [next(a['answer_id'] for a in row['answers'] if a['role'] == role)]} for row in test['items']],
                  'returned_score': {'points_earned': 0, 'points_possible': 4}, 'idempotency_key': str(uuid4())}
        result = api('POST', 'attempts', report)
        assert result['calculated_score']['points_earned'] == expected
        assert api('POST', 'attempts', report)['id'] == result['id']
        attempts.append(result)
    assert attempts[0]['score_difference']['is_different']
    assert attempts[1]['previous_id'] == attempts[0]['id'] and attempts[2]['previous_id'] == attempts[1]['id']
    anonymous = {k: v for k, v in report.items() if k not in ('person_id', 'test_taken_at')}
    anonymous['idempotency_key'] = str(uuid4())
    first = api('POST', 'attempts', anonymous)
    anonymous['idempotency_key'] = str(uuid4())
    second = api('POST', 'attempts', anonymous)
    assert first['id'] != second['id']
    attempts.extend([first, second])

    browser_authored = []
    if args.browser:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get('READY_BROWSER_EXECUTABLE'), headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(base + '/ready/')
            page.fill('#api-key', key)
            page.click('#connect-form button[type=submit]')
            page.wait_for_function("() => document.querySelector('#environment').textContent.includes('FirestoreStore') && !document.body.classList.contains('busy')")
            assert page.input_value('#api-key') == ''
            assert page.evaluate('getComputedStyle(document.body).backgroundColor') == 'rgb(245, 243, 235)'
            for name in ['builder', 'results', 'import', 'guide', 'library']:
                page.click(f'[data-tab={name}]')
                assert page.locator(f'#panel-{name}').is_visible()
            page.click('#new-record')
            page.wait_for_function("() => !document.body.classList.contains('busy')")
            page.fill('#record-text', 'Native browser authoring validation?')
            page.fill('#record-author', 'READY builder')
            page.fill('#record-source', 'Hosting browser validation')
            page.select_option('#record-authorship', 'system')
            page.fill('#record-tags', 'system_validation, ' + validation_tag)
            page.click('#save-record')
            page.wait_for_function("() => document.querySelector('#status').textContent.includes('Saved revision 1') && !document.body.classList.contains('busy')")
            page.fill('#record-text', 'Native browser authoring revised?')
            page.click('#save-record')
            page.wait_for_function("() => document.querySelector('#status').textContent.includes('Saved revision 2') && !document.body.classList.contains('busy')")
            page.check('#show-history')
            page.wait_for_function("() => !document.body.classList.contains('busy')")
            authored = api('GET', 'questions?include_history=true&limit=100')['records']
            browser_authored = [row['id'] for row in authored if row['question_text'].startswith('Native browser authoring') and validation_tag in row.get('metadata', {}).get('tags', [])]
            assert len(browser_authored) == 2
            page.screenshot(path=str(artifacts / 'hosting-desktop.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(artifacts / 'hosting-mobile.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            assert page.evaluate('localStorage.length === 0 && sessionStorage.length === 0')
            assert not errors, errors
            browser.close()

    kinds = {'question': 'questions', 'answer': 'answers', 'question_answer_set': 'sets'}
    rows = [(kinds[row['type']], row['id']) for row in imported['created']]
    rows += [('questions', record_id) for record_id in browser_authored]
    rows += [('questions', revised['id']), ('tests', test['id']), ('tests', variant['id'])] + [('attempts', row['id']) for row in attempts]
    for kind, record_id in rows:
        row = api('GET', kind + '/' + record_id)
        archived = api('PUT', kind + '/' + record_id + '/archive', {'is_archived': True, 'reason': 'Hosting validation complete; retain all evidence', 'expected_record_version': row['record_version']})
        assert archived['is_archived']
        retained.append({'kind': kind, 'id': record_id})
    evidence.write_text(json.dumps({'origin': base, 'checked_at': datetime.now(timezone.utc).isoformat(), 'test_id': test['id'], 'frozen_items': test['items'], 'retained': retained, 'passed': True}, indent=2))
    print('Hosting HTTP check passed: Firestore auth, seed dry-run/import/replay, revisions, frozen paired tests, grading, correction history, independent anonymous results, archival and browser layout.')


if __name__ == '__main__':
    main()
