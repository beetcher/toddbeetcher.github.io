#!/usr/bin/env python3
"""Real-browser management check through in-process application transport.

No outbound network. Chromium IPC permission is still required. A failure to
launch or render is a failed/blocked verification, never a passing screenshot.
"""
import json,threading,sys,os,shutil
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from argparse import ArgumentParser
from pathlib import Path
from uuid import uuid4
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from ready.application import Application
from ready.services import ReadyService
from ready.crud.memory_store import MemoryStore
from ready.devserver import make_server
from playwright.sync_api import sync_playwright
parser=ArgumentParser()
parser.add_argument('--artifacts',default='/tmp/ready-browser-artifacts')
parser.add_argument('--transport', choices=['inprocess', 'http'], default='inprocess')
args=parser.parse_args()
ARTIFACTS=Path(args.artifacts);ARTIFACTS.mkdir(parents=True,exist_ok=True)
key='browser-test-only-not-a-real-secret-123456789'
service=ReadyService(MemoryStore()); app=Application(service,key)
server=None
errors=[]
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.environ.get('READY_BROWSER_EXECUTABLE') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1440,'height':1000})
  page.on('pageerror',lambda e:errors.append(str(e)))
  def bridge(route):
   request=route.request
   target=request.url.removeprefix('https://ready.local')
   status,headers,body=app.handle(request.method,target,request.headers,request.post_data_buffer or b'', 'browser')
   route.fulfill(status=status,headers=headers,body=body)
  if args.transport == 'http':
   server=make_server(app,port=0)
   threading.Thread(target=server.serve_forever,daemon=True).start()
   page.goto(f'http://127.0.0.1:{server.server_port}/ready/')
  else:
   page.route('https://ready.local/**',bridge)
   page.goto('https://ready.local/ready/')
  page.fill('#api-key',key);page.click('#connect-form button[type=submit]')
  page.wait_for_function("() => document.querySelector('#environment').textContent.includes('MemoryStore')")
  page.wait_for_function("() => !document.body.classList.contains('busy')")
  page.click('[data-tab=import]');page.click('#load-seed')
  page.wait_for_function("() => document.querySelector('#import-input').value.includes('q_10')")
  page.click('#import-form button[type=submit]')
  page.wait_for_function("() => document.querySelector('#import-report').textContent.includes('would_create')")
  assert service.list('questions')['count']==0
  page.click('#commit-import')
  page.wait_for_function("() => document.querySelector('#import-report').textContent.includes('created')")
  page.wait_for_function("() => !document.body.classList.contains('busy')")
  assert service.list('questions')['count']==10
  page.click('[data-tab=library]');page.select_option('#library-kind','sets')
  page.wait_for_function("() => document.querySelectorAll('#library-list .record-card').length === 10")
  page.click('[data-tab=builder]');page.fill('#selection-count','2');page.click('#selection-form button[type=submit]')
  page.wait_for_function("() => document.querySelector('#working-count').textContent === '2'")
  page.check('#allow-duplicates');page.fill('#duplicate-pairs','2');page.click('#arrange-pairs')
  page.wait_for_function("() => document.querySelector('#working-count').textContent === '4'")
  page.fill('#test-name','AI readiness · browser validation');page.fill('#test-author','READY builder')
  page.click('#test-form button[type=submit]')
  page.wait_for_function("() => document.querySelector('#test-json').textContent.includes('scoring_policy_version')")
  page.wait_for_function("() => !document.body.classList.contains('busy')")
  test=json.loads(page.locator('#test-json').text_content())
  assert len(test['items'])==4 and len({i['question_id'] for i in test['items']})==2
  # Inspect a saved card while the working assembly pushes its detail below the fold.
  # A fetched JSON document alone is insufficient: the selected test must be visible.
  page.click('#refresh-tests')
  page.wait_for_function("() => !document.body.classList.contains('busy')")
  page.get_by_role('button',name='Inspect test',exact=True).click()
  page.wait_for_function("() => !document.body.classList.contains('busy')")
  inspection=page.locator('#test-detail').evaluate('(el) => ({focused:document.activeElement === el, top:el.getBoundingClientRect().top, viewport:window.innerHeight, active:document.activeElement.id})')
  assert inspection['focused'] and -1 <= inspection['top'] < inspection['viewport']/2, inspection
  assert page.locator('#test-items > li').count()==4
  assert page.locator('#test-items > li').nth(0).locator('h3').inner_text()==test['items'][0]['question_text']
  page.set_viewport_size({'width':390,'height':844})
  page.click('#refresh-tests');page.wait_for_function("() => !document.body.classList.contains('busy')")
  page.get_by_role('button',name='Inspect test',exact=True).click()
  page.wait_for_function("() => !document.body.classList.contains('busy')")
  inspection=page.locator('#test-detail').evaluate('(el) => ({focused:document.activeElement === el, top:el.getBoundingClientRect().top, viewport:window.innerHeight, active:document.activeElement.id})')
  assert inspection['focused'] and -1 <= inspection['top'] < inspection['viewport']/2, inspection
  assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
  page.screenshot(path=str(ARTIFACTS/'inspect-mobile.png'),full_page=False)
  page.set_viewport_size({'width':1440,'height':1000})
  with page.expect_download() as downloaded:
   page.click('#download-test')
  assert json.loads(Path(downloaded.value.path()).read_text())==test
  with page.expect_download() as pdf_download:
   page.click('#download-test-pdf')
  pdf=pdf_download.value
  assert pdf.suggested_filename=='ready-test-'+test['id']+'.pdf'
  assert Path(pdf.path()).read_bytes().startswith(b'%PDF-')
  pdf.save_as(str(ARTIFACTS/'saved-test-review.pdf'))
  page.wait_for_function("() => !document.body.classList.contains('busy')")
  assert service.get('tests',test['id'])['items']==test['items']
  page.screenshot(path=str(ARTIFACTS/'desktop.png'),full_page=True)
  report={'test_id':test['id'],'person_id':'browser_validation','test_taken_at':'2026-10-28T12:00:00Z','responses':[{'item_id':i['item_id'],'answer_ids':[a['answer_id'] for a in i['answers'] if a['role']=='strong']} for i in test['items']],'returned_score':{'points_earned':0,'points_possible':4},'idempotency_key':str(uuid4())}
  page.click('[data-tab=results]');page.fill('#result-input',json.dumps(report));page.click('#result-form button[type=submit]')
  page.wait_for_function("() => document.querySelectorAll('#result-detail .score strong').length === 2")
  assert page.locator('#result-detail .score strong').nth(0).inner_text()=='0 / 4'
  assert page.locator('#result-detail .score strong').nth(1).inner_text()=='4 / 4'
  page.wait_for_function("() => !document.body.classList.contains('busy')")
  report['idempotency_key']=str(uuid4());report['returned_score']['points_earned']=4
  page.fill('#result-input',json.dumps(report));page.click('#result-form button[type=submit]')
  page.wait_for_function("() => document.querySelector('#status').textContent.includes('recorded') && !document.body.classList.contains('busy')")
  page.check('#result-history')
  page.wait_for_function("() => document.querySelectorAll('#result-list .record-card').length === 2")
  page.screenshot(path=str(ARTIFACTS/'results.png'),full_page=True)
  page.set_viewport_size({'width':390,'height':844});page.click('[data-tab=library]')
  page.screenshot(path=str(ARTIFACTS/'mobile.png'),full_page=True)
  assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'mobile horizontal overflow'
  assert not errors,errors
  class QuietStatic(SimpleHTTPRequestHandler):
   def log_message(self,*_): pass
  preview_server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietStatic,directory=str(ROOT.parent)))
  threading.Thread(target=preview_server.serve_forever,daemon=True).start()
  try:
   page.goto(f'http://127.0.0.1:{preview_server.server_port}/ready/web/')
   assert page.locator('#preview-notice').is_visible()
   assert not page.locator('#connect-form').is_visible()
   assert page.locator('#api-key').is_disabled()
   assert page.evaluate('getComputedStyle(document.body).backgroundColor') == 'rgb(245, 243, 235)'
   for section in ['builder','results','guide','import']:
    page.click(f'[data-tab={section}]')
    assert page.locator(f'#panel-{section}').is_visible()
   page.click('#load-seed')
   page.wait_for_function("() => document.querySelector('#import-input').value.includes('q_10')")
   page.screenshot(path=str(ARTIFACTS/'preview-mobile.png'),full_page=True)
   assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
   assert not errors, errors
  finally:
   preview_server.shutdown();preview_server.server_close()
  browser.close()
 print('Browser passed: auth, seed preview/no-write, import, library, selection, two duplicate pairs, immutable test creation, dual-score discrepancy, preserved correction chain, mobile layout; no JS errors.')
finally:
 if server:
  server.shutdown();server.server_close()
