"""Source watcher and draft persistence used only by desktop development."""
import json
import threading
from pathlib import Path


def fingerprint(root):
    root = Path(root)
    python = tuple(sorted((str(p), p.stat().st_mtime_ns, p.stat().st_size)
                          for p in root.glob('*.py')))
    web = tuple(sorted((str(p), p.stat().st_mtime_ns, p.stat().st_size)
                       for p in (root / 'web').rglob('*') if p.is_file()))
    return python, web


class DevelopmentState:
    def __init__(self, directory):
        self.path = Path(directory) / 'draft.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read_draft(self):
        return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else None

    def capture(self, window):
        value = window.evaluate_js("JSON.stringify({scene:data,editor:document.getElementById('editor').value,example:document.getElementById('example').value})")
        parsed = json.loads(value)
        if not isinstance(parsed.get('scene'), dict):
            raise ValueError('Invalid development scene')
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(parsed, ensure_ascii=False), encoding='utf-8')
        temporary.replace(self.path)


def watch_sources(root, window, state, ready, stop, restart):
    previous = fingerprint(root)
    while not stop.wait(.4):
        if not ready.is_set():
            continue
        try:
            current = fingerprint(root)
            if current == previous:
                continue
            # Wait until editor writes have settled before reloading.
            if stop.wait(.3) or fingerprint(root) != current:
                continue
            state.capture(window)
            if current[0] != previous[0]:
                restart.set()
                window.destroy()
                return
            ready.clear()
            window.load_url(window.get_current_url())
            previous = current
        except Exception as error:
            print(f'自动更新失败（窗口保留）：{error}', flush=True)


def run():
    import subprocess
    import sys
    root = Path(__file__).parent
    while True:
        result = subprocess.run([sys.executable, str(root / 'desktop.py'), '--dev'], cwd=root)
        if result.returncode == 75:
            print('Python 文件已更新，重新启动桌面窗口…', flush=True)
            continue
        if result.returncode == 0:
            return
        print('启动失败。修复代码并保存后会重试；按 Ctrl+C 退出。', flush=True)
        previous = fingerprint(root)[0]
        event = threading.Event()
        while fingerprint(root)[0] == previous:
            event.wait(.5)


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        pass
