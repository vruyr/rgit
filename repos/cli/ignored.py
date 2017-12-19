import re, itertools, os
from .registry import command
from .. import git
from ..tools import strict_int


@command("ignored")
class Ignored(object):
	@classmethod
	def define_arguments(cls, parser):
		parser.add_argument(
			"--group", "-g",
			dest="groups",
			action="append",
			default=[],
			help=(
				"case-insensitive name of ignore group as defined in .gitignore files by putting "
				"the group name immediately after \"#{{{\" which will include every pattern "
				"until \"#}}}\""
			),
		)

	@classmethod
	def short_description(cls):
		return "show and manipulate ignored files in repositories"

	def __init__(self):
		self._config = None

	async def execute(self, *, opts, config):
		print(opts)
		self._config = config

		ignore_group_reader = IgnoreGroupReader()

		results = {}
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
				worktree=git.TOPLEVEL,
				# Ignored files are reported relative to repo work-tree, which check-ignore will
				# resolve using the current folder, so it must be the work-tree.
				cwd=git.WORKTREE,
			)
			stdout = stdout.split("\0")
			assert len(stdout) == 4 * len(ignored_files) + 1, (len(ignored_files), len(stdout))
			assert stdout.pop(-1) == ""
			ignored = map(lambda i: stdout[(i*4):(i*4+4)], range(len(stdout) // 4))

			worktree_path = await git.toplevel(repo)

			ignored_files_by_group = {}
			for ignore_file, ignore_file_line, ignore_pattern, path in ignored:
				ignore_file = None if ignore_file == "" else worktree_path / ignore_file
				ignore_file_line = None if ignore_file_line == "" else strict_int(ignore_file_line)
				assert (ignore_file is None) == (ignore_file_line is None)
				groups = ignore_group_reader.get_groups(ignore_file, ignore_file_line)
				if groups is None:
					group = "<error>"
				elif len(groups) < 1:
					group = ""
				else:
					assert len(groups) <= 1
					group = groups[0]
				ignored_files_by_group.setdefault(group, []).append(path)
			results[os.fspath(worktree_path)] = ignored_files_by_group

		import json
		print(json.dumps(results, indent="\t"))


class IgnoreGroupReader(object):
	def __init__(self):
		self._cache = {}

	def get_groups(self, path, lineno):
		if path is None or lineno is None:
			return None
		if path not in self._cache:
			self._cache[path] = self._read_ignore_file(path)
		ignore_file_map = self._cache[path]
		assert 0 <= (lineno - 1) <= len(ignore_file_map), (lineno, len(ignore_file_map))
		return ignore_file_map[lineno - 1]

	@staticmethod
	def _read_ignore_file(path):
		result = []
		start_marker = "#{{{"
		end_marker = "#}}}"
		group_name_pattern = re.compile(r"^[a-zA-Z0-9_]+$")
		group_stack = []
		with path.open("r") as fo:
			for line in fo:
				if line.startswith(start_marker):
					group = line[len(start_marker):].strip()
					if not group_name_pattern.match(group):
						raise ValueError(f"invalid group name - {repr(group)}")
					group_stack.append(group)
				elif line.startswith(end_marker):
					group_stack.pop(-1)
				if len(group_stack) > 1:
					raise ValueError("nested groups are not supported yet")
				result.append(list(set(group_stack)))
		return result
