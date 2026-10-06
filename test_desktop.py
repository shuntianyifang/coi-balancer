import json
import tempfile
import unittest
from pathlib import Path
from desktop import ScenarioStore


class DesktopStorageTests(unittest.TestCase):
    def test_roundtrip_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ScenarioStore(directory)
            self.assertEqual(store.read_scenarios(), {})
            scene = {'核电方案': {'instances': [{'level': 4}], 'recipes': []}}
            store.write_scenarios(scene)
            self.assertEqual(ScenarioStore(directory).read_scenarios(), scene)
            self.assertFalse(Path(directory, 'scenarios.tmp').exists())

    def test_invalid_write_preserves_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ScenarioStore(directory)
            store.write_scenarios({'原方案': {}})
            with self.assertRaises(ValueError):
                store.write_scenarios([])
            self.assertEqual(store.read_scenarios(), {'原方案': {}})

    def test_corrupt_file_is_not_silently_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'scenarios.json').write_text('broken', encoding='utf-8')
            with self.assertRaises(json.JSONDecodeError):
                ScenarioStore(directory).read_scenarios()


if __name__ == '__main__':
    unittest.main()
