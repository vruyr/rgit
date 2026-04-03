import asyncio, subprocess, unittest, sys
from . import get_toplevel


sys.path.insert(0, get_toplevel())
import rgit._gitcli # pylint: disable=wrong-import-position,wrong-import-order


class TestRunSync(unittest.TestCase):
	def test_basic_command(self):
		result = rgit._gitcli.run_sync("git", "--version")
		self.assertTrue(result.startswith("git version"))

	def test_rstrip(self):
		result = rgit._gitcli.run_sync("git", "--version", rstrip=True)
		self.assertFalse(result.endswith("\n"))

	def test_no_rstrip(self):
		result = rgit._gitcli.run_sync("git", "--version", rstrip=False)
		self.assertTrue(result.endswith("\n"))

	def test_check_failure(self):
		with self.assertRaises(subprocess.CalledProcessError):
			rgit._gitcli.run_sync("git", "log", "--oneline", "-1", cwd="/tmp")

	def test_cwd(self):
		result = rgit._gitcli.run_sync("git", "rev-parse", "--is-inside-work-tree", cwd=str(get_toplevel()))
		self.assertEqual(result, "true")


class TestRunAsync(unittest.TestCase):
	def test_basic_command(self):
		result = asyncio.run(rgit._gitcli.run_async("git", "--version"))
		self.assertTrue(result.startswith("git version"))

	def test_returncode_ok(self):
		# git status in a non-repo should fail with non-zero, but we accept it
		result = asyncio.run(rgit._gitcli.run_async(
			"git", "status",
			cwd="/tmp",
			stderr_ok=True,
			returncode_ok=lambda rc: True,
		))
		self.assertIsInstance(result, str)


class TestGitDescribe(unittest.TestCase):
	def test_returns_string_in_repo(self):
		result = rgit._gitcli.git_describe(cwd=str(get_toplevel()))
		self.assertIsNotNone(result)
		self.assertIsInstance(result, str)

	def test_returns_none_outside_repo(self):
		result = rgit._gitcli.git_describe(cwd="/tmp")
		self.assertIsNone(result)

	def test_auto_find_project_root(self):
		result = rgit._gitcli.git_describe()
		self.assertIsNotNone(result)
