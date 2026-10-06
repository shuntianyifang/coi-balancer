"""Offline desktop entry point. No fixed port or external server required."""
import json
import os
import sys
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from server import Handler


def user_directory():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share'))
    directory = base / 'CoI Balancer'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class ScenarioStore:
    def __init__(self, directory):
        self.path = Path(directory) / 'scenarios.json'
        self.lock = threading.Lock()

    def read_scenarios(self):
        with self.lock:
            if not self.path.exists():
                return {}
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(value, dict):
                raise ValueError('方案文件格式无效，请检查 scenarios.json')
            return value

    def write_scenarios(self, value):
        if not isinstance(value, dict):
            raise ValueError('方案必须为对象')
        content = json.dumps(value, ensure_ascii=False, indent=2)
        if len(content.encode('utf-8')) > 20_000_000:
            raise ValueError('方案文件超过 20MB')
        with self.lock:
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(content, encoding='utf-8')
            os.replace(temporary, self.path)
        return True


def main():
    import webview
    smoke = len(sys.argv) == 3 and sys.argv[1] == '--smoke-test'
    if smoke:
        import tempfile
        temporary_directory = tempfile.TemporaryDirectory()
        directory = Path(temporary_directory.name)
    else:
        directory = user_directory()
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    httpd.daemon_threads = True
    worker = threading.Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    try:
        window = webview.create_window('CoI 配平工作台',
            f'http://127.0.0.1:{httpd.server_port}/?example=reactors',
            js_api=ScenarioStore(directory), width=1280, height=900,
            min_size=(800, 600), hidden=smoke)
        if smoke:
            outcome = {'ok': False, 'message': 'Window load timed out'}
            def check_window():
                import urllib.request
                try:
                    state = window.evaluate_js("({title:document.title,cards:document.querySelectorAll('.building-card').length,groups:typeof BuildingViews.groups})")
                    assert state['cards'] > 0 and state['groups'] == 'function', state
                    url = f'http://127.0.0.1:{httpd.server_port}'
                    scenario = {'recipes': [{'id':'test','name':'test','duration':60,'inputs':{'ore':1},'outputs':{'product':1},'count':1}], 'policies':{'ore':{'import':True},'product':{'target':1}}}
                    for mode in ['audit', 'solve', 'integer']:
                        request = urllib.request.Request(url+'/api/'+mode, data=json.dumps(scenario).encode(), headers={'Content-Type':'application/json'})
                        with urllib.request.urlopen(request) as response:
                            assert json.load(response)['ok'], mode
                    with urllib.request.urlopen(url+'/nuclear-catalog.json') as response:
                        catalog = json.load(response)
                    request = urllib.request.Request(url+'/api/plant', data=json.dumps(catalog).encode(), headers={'Content-Type':'application/json'})
                    with urllib.request.urlopen(request) as response:
                        assert json.load(response)['ok']
                    store = ScenarioStore(directory)
                    store.write_scenarios({'smoke': scenario})
                    assert ScenarioStore(directory).read_scenarios()['smoke'] == scenario
                    outcome.update(ok=True, message='WebView2, assets, all solver modes, nuclear model and persistence passed', dom=state)
                except Exception as error:
                    outcome.update(ok=False, message=str(error))
                finally:
                    window.destroy()
            window.events.loaded += check_window
            watchdog = threading.Timer(45, window.destroy)
            watchdog.daemon = True
            watchdog.start()
        webview.start(gui='edgechromium' if sys.platform == 'win32' else None,
                      private_mode=False, storage_path=str(directory / 'webview'))
    finally:
        httpd.shutdown()
        httpd.server_close()
        worker.join(timeout=3)
        if smoke:
            watchdog.cancel()
            outcome['serverStopped'] = not worker.is_alive()
            Path(sys.argv[2]).write_text(json.dumps(outcome, ensure_ascii=False), encoding='utf-8')
            temporary_directory.cleanup()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        details = traceback.format_exc()
        try:
            (user_directory() / 'desktop-error.log').write_text(details, encoding='utf-8')
        finally:
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.user32.MessageBoxW(None,
                    '无法启动桌面版。请确认已安装 Microsoft Edge WebView2 Runtime。\n'
                    '详细信息已保存到用户目录中的 desktop-error.log。', 'CoI 配平工作台', 16)
            else:
                print(details, file=sys.stderr)
        sys.exit(1)
