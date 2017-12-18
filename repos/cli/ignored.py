from .registry import command
from .. import git
from ..tools import strict_int


@command("ignored")
class Ignored(object):
	@classmethod
	def define_arguments(cls, parser):
		pass

	@classmethod
	def short_description(cls):
		return "show and manipulate ignored files in repositories"

	def __init__(self):
		self._config = None

	async def execute(self, *, opts, config):
		self._config = config

		stdout = None
		for repo in self._config.repositories:
			if await git.is_bare(repo):
				continue
			ignored_files = [
				path
				for _, path in filter(
					lambda x: x[0] == "ignored",
					await git.status(repo, "--ignored")
				)
			]
			if not ignored_files:
				continue
			stdout = await git.git(repo,
				"check-ignore", "-z", "--verbose", "--non-matching", "--stdin",
				stdin="\0".join(ignored_files),
				returncode_ok=lambda returncode: returncode in (0, 1),
			)
			stdout = stdout.split("\0")
			assert len(stdout) == 4 * len(ignored_files) + 1, (len(ignored_files), len(stdout))
			assert stdout.pop(-1) == ""
			ignored = map(lambda i: stdout[(i*4):(i*4+4)], range(len(stdout) // 4))

			print(repo)
			for ignore_file, ignore_file_line, ignore_pattern, path in ignored:
				ignore_file = None if ignore_file == "" else repo / ignore_file
				ignore_file_line = None if ignore_file_line == "" else strict_int(ignore_file_line)
				assert (ignore_file is None) == (ignore_file_line is None)
				print("\t" + repr([ignore_file, ignore_file_line, ignore_pattern, path]))
			print()
