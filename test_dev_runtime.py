import json
import tempfile
import threading
import unittest
from pathlib import Path
from dev_runtime import DevelopmentState, fingerprint, watch_sources


class FakeWindow:
    def __init__(self, ready, stop):
        self.ready, self.stop = ready, stop
        self.reloads = []
        self.destroyed = False

    def evaluate_js(self, script):
        return json.dumps({'scene': {'version': '未保存场景'}, 'editor': 'invalid draft'})

    def get_current_url(self):
        return 'http://127.0.0.1:1234/'

    def load_url(self, url):
        self.reloads.append(url)
        self.ready.set()
        self.stop.set()

    def destroy(self):
        self.destroyed = True
        self.stop.set()


class DevelopmentTests(unittest.TestCase):
    def test_web_reload_and_python_restart_restore_draft(self):
        for filename in ['web/app.js', 'server.py']:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'web').mkdir()
                source = root / filename
                source.write_text('initial', encoding='utf-8')
                ready, stop, restart = threading.Event(), threading.Event(), threading.Event()
                ready.set()
                state = DevelopmentState(root / 'drafts')
                window = FakeWindow(ready, stop)
                worker = threading.Thread(target=watch_sources, args=(root, window, state, ready, stop, restart))
                worker.start()
                try:
                    stop.wait(.15)
                    source.write_text('changed source', encoding='utf-8')
                    worker.join(timeout=4)
                    self.assertFalse(worker.is_alive())
                    self.assertEqual(state.read_draft()['editor'], 'invalid draft')
                    self.assertEqual(state.read_draft()['scene']['version'], '未保存场景')
                    self.assertEqual(restart.is_set(), filename.endswith('.py'))
                    self.assertEqual(window.destroyed, filename.endswith('.py'))
                    self.assertEqual(len(window.reloads), int(filename.endswith('.js')))
                finally:
                    stop.set()
                    worker.join(timeout=2)

    def test_generated_files_do_not_trigger_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'web').mkdir()
            previous = fingerprint(root)
            (root / 'build').mkdir()
            (root / 'build' / 'draft.json').write_text('{}')
            self.assertEqual(fingerprint(root), previous)


if __name__ == '__main__':
    unittest.main()
