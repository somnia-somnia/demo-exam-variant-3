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
        if js('location.pathname') == path and js('document.readyState') == 'complete' and js("!!document.querySelector('main h1')"):
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
    assert js("document.querySelector('main [name=login]').getBoundingClientRect().bottom < innerHeight"), 'Login form is below the first mobile screen'
    assert js("Math.abs(document.querySelector('.slide').clientWidth / document.querySelector('.slide').clientHeight - 1.6) < .02"), 'Slider image is distorted'
    assert js('getComputedStyle(document.body).fontFamily').startswith('Montserrat')
    assert js("document.fonts.check('16px Montserrat')")
    assert js("document.querySelectorAll('.slide').length") == 4
    assert js("document.querySelectorAll('.slider [data-step]').length") == 2
    assert js("document.querySelectorAll('.slider .pause').length") == 0
    active_slide = "[...document.querySelectorAll('.slide')].findIndex(slide => !slide.hidden)"
    assert js(active_slide) == 0
    for expected in [1, 2, 3, 0]:
        time.sleep(3.05)
        assert js(active_slide) == expected, 'Automatic slideshow did not advance or wrap'
    js("document.querySelector('[data-step=\"-1\"]').click()")
    assert js(active_slide) == 3
    js("document.querySelector('[data-step=\"1\"]').click()")
    assert js(active_slide) == 0
    time.sleep(1.8)
    js("document.querySelector('[data-step=\"1\"]').click()")
    time.sleep(1.3)
    assert js(active_slide) == 1, 'Manual control did not restart the three-second interval'
    time.sleep(1.85)
    assert js(active_slide) == 2
    assert js("[...document.querySelectorAll('.slider [data-step]')].every(button=>{const b=button.getBoundingClientRect(),s=button.closest('.slider').getBoundingClientRect();return b.width>=44 && b.height>=44 && b.left>=s.left && b.right<=s.right && b.top>=s.top && b.bottom<=s.bottom})"), 'Slider arrows must fit inside the photo and have 44px targets'
    go('/register'); screenshot('register-mobile')
    assert js("document.querySelector('main [name=login]').getBoundingClientRect().bottom < innerHeight"), 'Registration form is below the first mobile screen'
    submit(dict(login='bad', password='123', full_name='John', phone='+7', email='<a>@x.ru'), '/register')
    assert js("document.querySelectorAll('main .error[role=alert]').length") == 5
    screenshot('register-errors-mobile')
    submit(dict(login='Browser01', password='password123', full_name='Иванов Иван',
                phone='8(999)123-45-67', email='browser@example.ru'), '/login')
    submit(dict(login='Browser01', password='wrong'), '/login')
    assert js("document.querySelectorAll('main .error[role=alert]').length") == 1
    screenshot('login-errors-mobile')
    submit(dict(login='Browser01', password='password123'), '/bookings')
    screenshot('bookings-empty-mobile')
    go('/bookings/new'); screenshot('new-mobile')
    submit(dict(car='', start_date='31.02.2026', payment=''), '/bookings/new')
    assert js("document.querySelectorAll('main .error[role=alert]').length") == 3
    screenshot('new-errors-mobile')
    submit(dict(car='Toyota Camry', start_date='02.12.2026', payment='Переводом по номеру телефона'), '/bookings')
    screenshot('bookings-mobile')
    assert js("!document.querySelector('.review-form:not([hidden])')")
    submit({}, '/login', 'header form')
    submit(dict(login='Admin', password='StartNET'), '/admin')
    screenshot('admin-mobile')
    submit(dict(status='Идет аренда'), '/admin', '.status-form')
    screenshot('admin-renting-mobile')
    submit(dict(status='Аренда завершена'), '/admin', '.status-form')
    js("document.querySelector('#filter select').value='Новая'")
    js("document.querySelector('#filter').requestSubmit()")
    time.sleep(.3)
    assert js("!document.querySelector('.booking')"), 'Status filter failed'
    go('/admin')
    submit({}, '/login', 'header form')
    submit(dict(login='Browser01', password='password123'), '/bookings')
    screenshot('review-mobile')
    submit(dict(text='Удобно <img src=x onerror=window.XSS=1> и быстро. Спасибо!'), '/bookings', 'main .review-form')
    assert js("document.querySelector('.review').textContent.includes('<img src=x onerror=window.XSS=1>') && !window.XSS && !document.querySelector('.review img')")
    screenshot('review-saved-mobile')
    go('/bookings/new')
    submit(dict(car='LADA Vesta', start_date='03.12.2026', payment='Наличными'), '/bookings')
    assert js("document.querySelectorAll('.booking').length") == 2
    screenshot('bookings-two-mobile')
    cmd('Emulation.setDeviceMetricsOverride', width=1440, height=1000, deviceScaleFactor=1, mobile=False)
    screenshot('bookings-desktop')
    submit({}, '/login', 'header form')
    submit(dict(login='Admin', password='StartNET'), '/admin')
    screenshot('admin-desktop')
    submit({}, '/login', 'header form')
    screenshot('login-desktop')
    assert not [e for e in events if e.get('method') == 'Runtime.exceptionThrown']
    external = [e['params']['request']['url'] for e in events if e.get('method') == 'Network.requestWillBeSent'
                and not e['params']['request']['url'].startswith(('http://127.0.0.1:', 'data:', 'about:'))]
    assert not external, external
    typography = js("({h1:getComputedStyle(document.querySelector('h1')).fontSize,h2:getComputedStyle(document.querySelector('h2')).fontSize,body:getComputedStyle(document.body).fontSize,family:getComputedStyle(document.body).fontFamily})")
    assert typography['h1'] == '36px' and typography['h2'] == '24px' and typography['body'] == '16px'
    report = dict(result='PASS', mobile='390x844', desktop='1440x1000', typography=typography, external_requests=external,
                  screenshots=sorted(p.name for p in OUT.glob('*.png')),
                  checks=['registration', 'login', 'booking', 'admin status', 'filter', 'review',
                          'owner review availability', 'slider 3000ms: all four slides and wrap', 'overlay arrows, no pause', 'manual control restarts timer',
                          'visible errors: five registration fields, login, three booking fields', 'mobile forms above fold', 'two mobile booking cards', 'XSS payload is visible plain text, not an image or executable code', 'server-rendered HTML forms and redirects', 'all pages: no horizontal overflow', 'fonts/images local', 'no JS exceptions'])
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
