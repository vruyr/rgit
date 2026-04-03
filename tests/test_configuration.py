import asyncio, json, pathlib, tempfile, unittest, sys
from . import get_toplevel


sys.path.insert(0, get_toplevel())
import rgit.configuration # pylint: disable=wrong-import-position,wrong-import-order


class TestConfiguration(unittest.TestCase):
	def test_load_with_none_path(self):
		config = asyncio.run(rgit.configuration.load(config_file_path=None))
		self.assertEqual(list(config.repositories), [])

	def test_load_with_nonexistent_path(self):
		config = asyncio.run(rgit.configuration.load(config_file_path=pathlib.Path("/nonexistent/path/config.json")))
		self.assertEqual(list(config.repositories), [])

	def test_load_with_valid_path(self):
		with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
			json.dump({"repositories": ["foo/bar"]}, f)
			f.flush()
			config = asyncio.run(rgit.configuration.load(config_file_path=pathlib.Path(f.name)))
		self.assertEqual(list(config.repositories), [pathlib.Path.home() / "foo/bar"])
