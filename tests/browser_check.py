"""Real Edge checks via CDP; development-only dependency: websocket-client."""
import base64
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4
import websocket

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests/screenshots'
OUT.mkdir(exist_ok=True)
WORK = ROOT / 'tmp' / ('browser-' + uuid4().hex)
WORK.mkdir(parents=True)
EDGE = Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe'
def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


port, debug_port = free_port(), free_port()
base_url = f'http://127.0.0.1:{port}'
env = dict(os.environ, RENTAL_DB=str(WORK / 'browser.db'), PORT=str(port))
server = subprocess.Popen([sys.executable, 'app.py'], cwd=ROOT, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
browser = subprocess.Popen([str(EDGE), '--headless=new', '--disable-gpu', '--no-first-run',
                            f'--remote-debugging-port={debug_port}', '--remote-allow-origins=*',
                            '--user-data-dir=' + str(WORK / 'profile'), 'about:blank'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ws = None
events, serial = [], 0


def cmd(method, **params):
    global serial
    serial += 1
    number = serial
    ws.send(json.dumps(dict(id=number, method=method, params=params)))
    while True:
        message = json.loads(ws.recv())
        if message.get('id') == number:
            assert 'error' not in message, message
            return message.get('result', {})
        events.append(message)


def js(expression):
    result = cmd('Runtime.evaluate', expression=expression, returnByValue=True)
    assert 'exceptionDetails' not in result, result
    return result.get('result', {}).get('value')


def wait_path(path):
    for _ in range(100):
        if js('location.pathname') == path and js('document.readyState') == 'complete':
            return
        time.sleep(.05)
    raise AssertionError('Navigation did not reach ' + path)


def go(path):
    cmd('Page.navigate', url=base_url + path)
    wait_path(path)


def submit(values, path, selector='main form'):
    js('Object.entries(' + json.dumps(values) + ').forEach(([k,v])=>document.querySelector(' +
       json.dumps(selector) + ').elements[k].value=v)')
    js('document.querySelector(' + json.dumps(selector) + ').requestSubmit()')
    time.sleep(.2)
    wait_path(path)


def screenshot(name):
    js('document.fonts.ready')
    time.sleep(.45)
    assert js('document.documentElement.scrollWidth <= innerWidth'), name + ' horizontal overflow'
    assert js('[...document.images].every(i => i.complete && i.naturalWidth > 0)'), name + ' broken image'
    result = cmd('Page.captureScreenshot', format='png', captureBeyondViewport=True)
    (OUT / (name + '.png')).write_bytes(base64.b64decode(result['data']))


try:
    for _ in range(100):
        try:
            targets = json.load(urllib.request.urlopen(f'http://127.0.0.1:{debug_port}/json', timeout=1))
            urllib.request.urlopen(base_url + '/login', timeout=1).close()
            break
        except OSError:
            time.sleep(.1)
    else:
        raise AssertionError('Test server or Edge did not start')
    ws = websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in targets if t['type'] == 'page'), timeout=15)
    cmd('Page.enable'); cmd('Runtime.enable'); cmd('Network.enable')
    cmd('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=1, mobile=True)
    go('/login'); screenshot('login-mobile')
    assert js("Math.abs(document.querySelector('.slide img').clientWidth / document.querySelector('.slide img').clientHeight - 1.6) < .02"), 'Slider image is distorted'
    assert js('getComputedStyle(document.body).fontFamily').startswith('Montserrat')
    assert js("document.fonts.check('16px Montserrat')")
    assert js("document.querySelector('.slide-count').textContent") == '1 / 4'
    time.sleep(3.15)
    assert js("document.querySelector('.slide-count').textContent") == '2 / 4'
    js("document.querySelector('[data-step=\"-1\"]').click()")
    assert js("document.querySelector('.slide-count').textContent") == '1 / 4'
    js("document.querySelector('.pause').click()")
    time.sleep(3.1)
    assert js("document.querySelector('.slide-count').textContent") == '1 / 4'
    go('/register'); screenshot('register-mobile')
    js("document.querySelector('[name=phone]').focus()")
    cmd('Input.insertText', text='89991234567')
    assert js("document.querySelector('[name=phone]').value") == '8(999)123-45-67', 'Mobile phone separators missing'
    submit(dict(login='Browser01', password='password123', full_name='Иванов Иван',
                phone='8(999)123-45-67', email='browser@example.ru'), '/login')
    submit(dict(login='Browser01', password='password123'), '/bookings')
    screenshot('bookings-empty-mobile')
    go('/bookings/new'); screenshot('new-mobile')
    js("document.querySelector('[name=start_date]').focus()")
    cmd('Input.insertText', text='02122026')
    assert js("document.querySelector('[name=start_date]').value") == '02.12.2026', 'Mobile date separators missing'
    submit(dict(car='Toyota Camry', start_date='02.12.2026', payment='Переводом по номеру телефона'), '/bookings')
    screenshot('bookings-mobile')
    assert js("!document.querySelector('textarea')")
    submit({}, '/login', 'header form')
    submit(dict(login='Admin', password='StartNET'), '/admin')
    screenshot('admin-mobile')
    submit(dict(status='Аренда завершена'), '/admin', '.status-form')
    js("document.querySelector('#filter').value='Новая'")
    js("document.querySelector('.filter').requestSubmit()")
    time.sleep(.3)
    assert js("!document.querySelector('.booking')"), 'Status filter failed'
    go('/admin')
    submit({}, '/login', 'header form')
    submit(dict(login='Browser01', password='password123'), '/bookings')
    screenshot('review-mobile')
    submit(dict(text='Удобно и быстро. Спасибо!'), '/bookings', 'main .review')
    assert js("document.querySelector('.review').textContent.includes('Удобно и быстро')")
    screenshot('review-saved-mobile')
    cmd('Emulation.setDeviceMetricsOverride', width=1440, height=1000, deviceScaleFactor=1, mobile=False)
    screenshot('bookings-desktop')
    submit({}, '/login', 'header form')
    screenshot('login-desktop')
    assert not [e for e in events if e.get('method') == 'Runtime.exceptionThrown']
    external = [e['params']['request']['url'] for e in events if e.get('method') == 'Network.requestWillBeSent'
                and not e['params']['request']['url'].startswith(('http://127.0.0.1:', 'data:', 'about:'))]
    assert not external, external
    report = dict(result='PASS', mobile='390x844', desktop='1440x1000', external_requests=external,
                  screenshots=sorted(p.name for p in OUT.glob('*.png')),
                  checks=['registration', 'login', 'booking', 'admin status', 'filter', 'review',
                          'owner review availability', 'slider 3000ms', 'previous button', 'pause',
                          'mobile phone/date input masks', 'all pages: no horizontal overflow', 'fonts/images local', 'no JS exceptions'])
    (ROOT / 'docs/browser-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
finally:
    if ws:
        try:
            cmd('Browser.close')
        except (OSError, websocket.WebSocketException):
            pass
        ws.close()
    for process in (browser, server):
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
