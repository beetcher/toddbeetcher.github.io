#!/usr/bin/env python3
"""Synthetic CMS tests with fake SMTP; no real email or database access.
Run: venv/bin/python run_cms_tests.py. A sleeping worker tests the deadline.
"""
import contextlib
import copy
import getpass
import importlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import smtplib
import ssl
import subprocess
import sys
import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import cms_service
import registration_service as service
import smtp_transport as smtp
import run_smtp_test as cli
from core import Schemas
from crud import registration_requests_crud as requests
from crud.memory_doc_store import MemoryDocStore
from crud.schema_kit import check_document, failure
from handler import handle_http
from memory_store import MemoryStore
from ratelimit import RateLimiter

ROOT = Path(__file__).resolve().parent.parent
RECORDS = json.loads((ROOT/'schemas/examples/registration_request.test_records.json').read_text())
EXAMPLES = json.loads((ROOT/'schemas/examples/registration_request.examples.json').read_text())
NOW = datetime.fromisoformat(RECORDS['setup']['now'].replace('Z', '+00:00'))
KEY = 'synthetic-key'


def sleeping_worker(*args):
    time.sleep(30)  # no connection or email; parent must terminate this worker


def fake_smtp_worker(connection, *args):
    """Exercise the actual worker and pipe with SMTP replaced inside the child."""
    with patch('socket.create_connection', side_effect=AssertionError('Network forbidden')):
        with patch.object(smtp.smtplib, 'SMTP') as factory:
            factory.return_value.send_message.return_value = {}
            smtp._smtp_worker(connection, *args)


class SharedStore(MemoryStore):
    def __init__(self, docs):
        super().__init__(RECORDS['setup']['scheduled_classes'], RECORDS['setup']['registration_venues'], RECORDS['setup'].get('registration_curriculums', []))
        self.docs = docs

    def put_request(self, doc):
        super().put_request(doc)
        self.docs.create(requests.REQUESTS.name, doc['id'], doc)


class CmsChecks(unittest.TestCase):
    def setUp(self):
        self.net = patch('socket.create_connection', side_effect=AssertionError('Network forbidden'))
        self.net.start()
        self.addCleanup(self.net.stop)
        self.addCleanup(self.reset)
        self.reset()
        self.docs = MemoryDocStore()
        self.store = SharedStore(self.docs)
        self.schemas = Schemas.load()
        self.body = copy.deepcopy(RECORDS['tests'][0]['request'])
        self.calls = []

    def reset(self):
        smtp.transport = service.acknowledge = service.record_result = None

    def enable(self, outcome=smtp.SendResult(True, 'accepted')):
        def fake(*args):
            self.calls.append(args)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        smtp.transport = fake
        service.acknowledge = lambda d: cms_service.acknowledge(d['first_name']+' '+d['last_name'], d['email'], d['confirmation_number'], KEY)
        service.record_result = lambda id, status, stamp, code: requests.set_acknowledgment_result(self.docs, id, status, stamp, code, now=NOW)

    def submit(self, body=None):
        return handle_http('POST', json.dumps(self.body if body is None else body).encode(), 'test-visitor', self.store, self.schemas, RateLimiter(), NOW)

    def saved(self):
        return self.docs.get(requests.REQUESTS.name, self.store.requests[-1]['id'])

    def test_off_by_default(self):
        self.assertIsNone(service.acknowledge)
        self.assertIsNone(smtp.transport)
        self.assertEqual(self.submit().status, 201)
        self.assertNotIn('acknowledgment_email_status', self.saved())

    def test_accepted_values_html_and_original_preserved(self):
        self.enable()
        self.body.update(first_name='<Sam>', email=' SYNTHETIC@EXAMPLE.COM ')
        response = self.submit()
        doc = self.saved()
        self.assertEqual(response.status, 201)
        self.assertEqual(set(response.body['data']), {'confirmation_number', 'registration_type'})
        self.assertEqual(doc['acknowledgment_email_status'], 'accepted')
        self.assertNotIn('acknowledgment_email_error_code', doc)
        self.assertEqual(doc['updated_by'], 'system:cms')
        self.assertEqual(check_document(requests.REQUESTS, doc), [])
        _, email, subject, text, html = self.calls[0]
        self.assertEqual(email, 'synthetic@example.com')
        self.assertIn(doc['confirmation_number'], text)
        self.assertIn('Hello <Sam>', text)
        self.assertIn('&lt;Sam&gt;', html)
        self.assertNotIn('<Sam>', html)
        self.assertIn('We received your request', text)
        self.assertNotIn('you are registered', text)
        for name, value in self.store.requests[0].items():
            if name not in ('updated_at', 'updated_by'):
                self.assertEqual(doc[name], value)
        self.assertEqual(len(self.calls), 1)

    def test_failure_and_unknown_preserve_success(self):
        for i, code in enumerate(('authentication_failed', 'recipient_rejected', 'message_rejected', 'unknown')):
            with self.subTest(code=code):
                self.enable(smtp.SendResult(False, code))
                self.body['idempotency_key'] = f'aaaaaaaa-aaaa-4aaa-8aaa-{i:012d}'
                self.assertEqual(self.submit().status, 201)
                self.assertEqual(self.saved()['acknowledgment_email_status'], 'unknown' if code == 'unknown' else 'failed')
                self.assertEqual(self.saved()['acknowledgment_email_error_code'], code)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(len(self.store.requests), 4)

    def test_timeout_records_unknown(self):
        self.enable(TimeoutError('private synthetic detail'))
        self.assertEqual(self.submit().status, 201)
        self.assertEqual(self.saved()['acknowledgment_email_status'], 'unknown')

    def test_secret_configuration_failure_preserves_success(self):
        self.enable()
        service.acknowledge = MagicMock(side_effect=RuntimeError('private detail'))
        self.assertEqual(self.submit().status, 201)
        self.assertEqual(self.saved()['acknowledgment_email_error_code'], 'configuration_failed')
        self.assertEqual(self.calls, [])

    def test_metadata_exception_preserves_confirmation(self):
        self.enable()
        service.record_result = MagicMock(side_effect=RuntimeError('private detail'))
        r = self.submit()
        self.assertEqual(r.status, 201)
        self.assertEqual(r.body['data']['confirmation_number'], self.store.requests[0]['confirmation_number'])
        self.assertEqual(len(self.calls), 1)

    def test_metadata_refusal_preserves_success(self):
        self.enable()
        service.record_result = MagicMock(return_value=failure('not_found'))
        self.assertEqual(self.submit().status, 201)
        self.assertEqual(len(self.store.requests), 1)

    def test_replay_never_resends(self):
        self.enable()
        first, second = self.submit(), self.submit()
        self.assertEqual(second.status, 200)
        self.assertEqual(first.body, second.body)
        self.assertEqual(len(self.calls), 1)

    def test_honeypot_rejection_and_save_failure_never_send(self):
        self.enable()
        self.assertEqual(self.submit({**self.body, 'website':'bot'}).status, 201)
        self.assertEqual(self.submit({**self.body, 'email':'invalid'}).status, 400)
        self.store.put_request = MagicMock(side_effect=RuntimeError('private detail'))
        self.assertEqual(self.submit().status, 500)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.store.requests, [])

    def test_server_fields_refused(self):
        self.enable()
        for field, value in (('acknowledgment_email_status','accepted'), ('acknowledgment_email_attempted_at','2026-10-14T17:00:00Z'), ('acknowledgment_email_error_code','unknown')):
            self.assertEqual(self.submit({**self.body, field:value}).status, 400)
        self.assertEqual(self.calls, [])

    def test_logs_sanitized(self):
        self.enable(smtp.SendResult(False, 'secret raw reply synthetic@example.com'))
        with self.assertLogs('enjoy_router', level='INFO') as logs:
            self.assertEqual(self.submit().status, 201)
        for value in (KEY, self.body['email'], self.body['first_name'], 'secret raw reply'):
            self.assertNotIn(value, '\n'.join(logs.output))
        self.assertEqual(self.saved()['acknowledgment_email_error_code'], 'smtp_failed')

    def test_setter_validation_and_error_removal(self):
        doc = copy.deepcopy(EXAMPLES['stored_examples']['acknowledgment_timeout'])
        self.docs.create(requests.REQUESTS.name, doc['id'], doc)
        for args in (('invalid','accepted',NOW.isoformat(),None), (doc['id'],'delivered',NOW.isoformat(),None), (doc['id'],'accepted','invalid',None), (doc['id'],'accepted',NOW.isoformat(),'unknown'), (doc['id'],'failed',NOW.isoformat(),None), (doc['id'],'failed',NOW.isoformat(),'raw reply')):
            self.assertFalse(requests.set_acknowledgment_result(self.docs, *args).ok)
        self.assertEqual(self.docs.get(requests.REQUESTS.name, doc['id']), doc)
        self.assertTrue(requests.set_acknowledgment_result(self.docs, doc['id'], 'accepted', NOW.isoformat()).ok)
        self.assertNotIn('acknowledgment_email_error_code', self.docs.get(requests.REQUESTS.name, doc['id']))
        missing = requests.set_acknowledgment_result(self.docs, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'accepted', NOW.isoformat())
        self.assertEqual(missing.code, 'not_found')

    def test_stored_examples_valid(self):
        for doc in EXAMPLES['stored_examples'].values():
            self.assertEqual(check_document(requests.REQUESTS, doc), [])


class TransportChecks(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.send_message.return_value = {}
        self.factory = patch.object(smtp.smtplib, 'SMTP', return_value=self.client)
        self.factory.start()
        self.addCleanup(self.factory.stop)
        self.net = patch('socket.create_connection', side_effect=AssertionError('Network forbidden'))
        self.net.start()
        self.addCleanup(self.net.stop)

    def send(self):
        return smtp._send_once(KEY, 'synthetic@example.com', 'Test', 'Test body', '<p>Test</p>')

    def test_tls_headers_html_no_overrides(self):
        self.assertTrue(self.send().ok)
        methods = [c[0] for c in self.client.method_calls]
        self.assertLess(methods.index('starttls'), methods.index('login'))
        ctx = self.client.starttls.call_args.kwargs['context']
        self.assertTrue(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.client.set_debuglevel.assert_called_once_with(0)
        msg = self.client.send_message.call_args.args[0]
        self.assertEqual(msg['From'], f'Launch <{smtp.FROM_ADDRESS}>')
        self.assertEqual(msg['Reply-To'], smtp.FROM_ADDRESS)
        self.assertEqual([p.get_content_type() for p in msg.iter_parts()], ['text/plain','text/html'])
        self.assertNotIn('List-Unsubscribe', msg)
        self.assertNotIn('X-Mailin-track', msg)
        self.client.send_message.assert_called_once()

    def test_missing_starttls_blocks_auth(self):
        self.client.starttls.side_effect = smtplib.SMTPNotSupportedError('private')
        self.assertEqual(self.send().code, 'smtp_feature_unavailable')
        self.client.login.assert_not_called()
        self.client.send_message.assert_not_called()

    def test_timeout_any_stage_is_unknown(self):
        for name in ('ehlo_or_helo_if_needed','starttls','login','send_message'):
            getattr(self.client, name).side_effect = TimeoutError('private')
            self.assertEqual(self.send().code, 'unknown')
            getattr(self.client, name).side_effect = None
        smtp.smtplib.SMTP.side_effect = TimeoutError('private')
        self.assertEqual(self.send().code, 'unknown')

    def test_rejections_sanitized(self):
        errors = [(smtplib.SMTPAuthenticationError(535,b'private'),'authentication_failed'), (smtplib.SMTPRecipientsRefused({'synthetic@example.com':(550,b'private')}),'recipient_rejected'), (smtplib.SMTPSenderRefused(550,b'private','synthetic@example.com'),'sender_rejected'), (smtplib.SMTPDataError(550,b'private'),'message_rejected')]
        for exc, code in errors:
            self.client.send_message.side_effect = exc
            self.assertEqual(self.send().code, code)

    def test_cleanup_preserves_acceptance(self):
        self.client.close.side_effect = OSError('private')
        self.assertTrue(self.send().ok)

    def test_metadata_write_is_bounded_without_changing_normal_crud(self):
        from crud.firestore_doc_store import FirestoreDocStore
        db = MagicMock()
        store = FirestoreDocStore(db)
        reference = db.collection.return_value.document.return_value
        store.update('synthetic_collection', 'synthetic_id', {'status':'test'}, timeout=2)
        reference.update.assert_called_once_with({'status':'test'}, retry=None, timeout=2)
        reference.update.reset_mock()
        store.update('synthetic_collection', 'synthetic_id', {'status':'test'})
        reference.update.assert_called_once_with({'status':'test'})

    def test_real_deadline_stops_harmless_worker(self):
        before = {p.pid for p in multiprocessing.active_children()}
        start = time.monotonic()
        with patch.object(smtp, '_smtp_worker', sleeping_worker), patch.object(smtp, 'TIMEOUT_SECONDS', 0.2):
            self.assertEqual(smtp.send_brevo(KEY, 'synthetic@example.com', 'Test', 'Test').code, 'unknown')
        self.assertLess(time.monotonic()-start, 1.5)
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)
        self.client.send_message.assert_not_called()

    def test_parent_receives_acceptance(self):
        ctx, recv, sender = MagicMock(), MagicMock(), MagicMock()
        ctx.Pipe.return_value = recv, sender
        recv.poll.return_value = True
        recv.recv.return_value = smtp.SendResult(True,'accepted')
        ctx.Process.return_value.is_alive.return_value = False
        with patch.object(smtp.multiprocessing, 'get_context', return_value=ctx):
            self.assertTrue(smtp.send_brevo(KEY,'synthetic@example.com','Test','Test').ok)
        ctx.Process.return_value.start.assert_called_once()
        self.assertLessEqual(recv.poll.call_args.args[0], 10)
        recv.close.assert_called_once()

    def test_spawned_worker_fake_smtp_round_trip(self):
        with patch.object(smtp, '_smtp_worker', fake_smtp_worker):
            self.assertTrue(smtp.send_brevo(KEY, 'synthetic@example.com', 'Test', 'Test').ok)
        self.client.send_message.assert_not_called()

    def test_cli_no_flag_or_terminal_cannot_send(self):
        with patch.object(cli.getpass,'getpass') as prompt, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([]), 2)
            prompt.assert_not_called()
        with patch.object(cli.sys.stdin,'isatty',return_value=False), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--send']), 2)
        self.client.send_message.assert_not_called()

    def test_hidden_input_fallback_refused(self):
        import warnings
        def fallback(*args):
            warnings.warn('hidden input unavailable', getpass.GetPassWarning)
            self.fail('visible input reached')
        with patch.object(cli.sys.stdin,'isatty',return_value=True), patch.object(cli.sys.stderr,'isatty',return_value=True), patch.object(cli.getpass,'getpass',side_effect=fallback), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--send']), 2)
        self.client.send_message.assert_not_called()


class WiringChecks(unittest.TestCase):
    def check_discovery(self, enabled):
        # A fresh interpreter models Firebase discovery: project dotenv values
        # are not loaded yet. Preinstalled root logging models the runtime.
        code = '''
import io, logging, os
from unittest.mock import patch, PropertyMock
import smtp_transport as smtp
import registration_service as service
from firebase_functions.params import SecretParam
output = io.StringIO()
logging.basicConfig(level=logging.WARNING, stream=output)
fake = lambda *args: smtp.SendResult(True, "accepted")
with patch("socket.create_connection", side_effect=AssertionError("Network forbidden")), patch.object(smtp, "send_brevo", fake), patch.object(SecretParam, "value", new_callable=PropertyMock, side_effect=AssertionError("Discovery must not read secrets")):
    import main
    expected = os.environ.get("ICDT_CMS_ENABLED") == "true"
    assert main.CMS_ENABLED is expected
    bindings = main.enjoy_registration_request.__firebase_endpoint__.secretEnvironmentVariables
    assert bindings == [{"key": "ICDT_BREVO_SMTP_KEY"}], "Secret binding missing during discovery"
    assert not main.enjoy_console_records.__firebase_endpoint__.secretEnvironmentVariables
    assert (service.acknowledge is not None) is expected
    assert (smtp.transport is fake) is expected
    app_log = logging.getLogger("enjoy_router")
    assert app_log.getEffectiveLevel() == logging.INFO, "Application INFO logging suppressed"
    app_log.info("cms id=synthetic_id status=failed code=missing_key")
    assert "cms id=synthetic_id status=failed code=missing_key" in output.getvalue()
'''
        env = dict(os.environ)
        for name in ('ICDT_CMS_ENABLED', 'FUNCTIONS_EMULATOR', 'ICDT_STORE', 'ICDT_BREVO_SMTP_KEY'):
            env.pop(name, None)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        if enabled:
            env['ICDT_CMS_ENABLED'] = 'true'
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parent,
                                env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_discovery_without_flag_still_binds_secret_and_logs_info(self):
        self.check_discovery(False)

    def test_runtime_flag_enables_only_fake_transport(self):
        self.check_discovery(True)

    def test_emulator_overrides_enable_flag(self):
        with patch.dict(os.environ, {'ICDT_STORE':'memory','FUNCTIONS_EMULATOR':'true','ICDT_CMS_ENABLED':'true'}):
            import main
            self.assertFalse(main.CMS_ENABLED)
            self.assertIsNone(service.acknowledge)
            self.assertIsNone(smtp.transport)

    def test_entrypoint_secret_and_recorder_wiring_with_fakes(self):
        import main
        doc = copy.deepcopy(EXAMPLES['stored_examples']['acknowledgment_accepted'])
        store = MemoryDocStore()
        store.create(requests.REQUESTS.name, doc['id'], doc)
        fake = MagicMock(return_value=smtp.SendResult(True, 'accepted'))
        with patch.dict(os.environ, {'ICDT_BREVO_SMTP_KEY': KEY}), patch.object(smtp, 'transport', fake):
            self.assertTrue(main._acknowledge(doc).ok)
        self.assertEqual(fake.call_args.args[0], KEY)
        with patch.object(main, '_get_admin_store', return_value=store):
            self.assertTrue(main._record_acknowledgment(doc['id'], 'unknown', NOW.isoformat(), 'unknown').ok)
        self.assertEqual(store.get(requests.REQUESTS.name, doc['id'])['acknowledgment_email_status'], 'unknown')


if __name__ == '__main__':
    unittest.main(verbosity=1)
