import sys, os, pathlib, asyncio, subprocess, re, collections, shlex
from ..tools import draw_table, set_status_msg, add_status_msg
from .registry import command


@command("status")
class Status(object):
	@classmethod
	def define_arguments(cls, parser):
		parser.add_argument(
			"--shell", "--sh",
			dest="shell",
			action="store_true",
			default=False,
			help="display paths suitable to be copy-pasted into shell",
		)

	@classmethod
	def short_description(cls):
		return "display statuses for all repositories"

	def __init__(self):
		self._shellify_paths = False

	async def execute(self, *, opts, config):
		self._shellify_paths = opts.shell

		# TODO Add an optional command line parameter for folder from which status should be shown
		# TODO Implement remotes, configuration, and hook checking.
		# TODO Implement submodule checking (local vs remote commit, detached head, ...)

		# TODO fix the config
		config_path_dir = pathlib.Path(config["path"]).absolute().parent
		repositories = list(config_path_dir / repo for repo in config["repositories"])

		status_table = [
			["#", "Repository Path"] # TODO Implement a column sorting mechanism and remove this.
		]
		column_names = status_table[0]

		for repo in repositories:
			add_status_msg(".")
			statistics = await self.get_repo_status_stats(repo)
			row = await self.render_status_statistics_row(column_names, statistics)
			if row is not None:
				status_table.append(row)

		set_status_msg(None)

		num_index = column_names.index("#")
		for r, row in enumerate(status_table):
			if r == 0:
				continue
			row[num_index] = r

		draw_table(status_table, fo=sys.stdout, has_header=True, cell_filter=self.cell_filter)

	@staticmethod
	def cell_filter(*, row, column, value, width, fill):
		if row == 0 or column == 1:
			return str(value).ljust(width, fill)
		return str(value).rjust(width, fill)

	async def render_status_statistics_row(self, column_names, statistics):
		if statistics is None:
			return None
		row = [""] * len(column_names)
		for column_name in sorted(statistics.keys()):
			if column_name in column_names:
				column_index = column_names.index(column_name)
			else:
				column_names.append(column_name)
				column_index = len(column_names) - 1
			while len(row) <= column_index:
				row.append("")
			row[column_index] = statistics[column_name]
		return row

	async def get_repo_status_stats(self, repo):
		if await self.is_repo_bare(repo):
			return None
		stdout = await self.git("-C", os.fspath(repo), "status", "--porcelain")
		if not stdout:
			return None
		statistics = collections.defaultdict(int)
		statistics["Repository Path"] = str(self._decorate_path_for_output(repo))
		for line in stdout.splitlines():
			status = None
			m = re.match(self._status_line_pattern, line)
			index, worktree, dummy_filepath, dummy_renamed_to = m.groups()
			index = "•" if index == " " else index
			worktree = "•" if worktree == " " else worktree
			status = f"{index}{worktree}"
			statistics[status] += 1
		return statistics

	async def is_repo_bare(self, repo):
		stdout = await self.git("-C", os.fspath(repo), "rev-parse", "--is-bare-repository")
		return {"true": True, "false": False}[stdout.strip()]

	@staticmethod
	async def git(*args):
		p = await asyncio.create_subprocess_exec("git", *args, stdout=subprocess.PIPE)
		stdout, stderr = await p.communicate()
		assert p.returncode == 0
		assert not stderr
		return stdout.decode()

	_status_line_pattern = re.compile(r"^([ MADRCU?!])([ MADRCU?!]) (.*?)(?: -> (.*?))?$")

	_home_parts = list(pathlib.Path.home().parts)

	def _decorate_path_for_output(self, path):
		if self._shellify_paths:
			if shlex.quote(str(path)) == str(path):
				path = self.abbreviate_path_for_shell(path)
			elif shlex.quote(str(path).replace(" ", "")) == str(path).replace(" ", ""):
				path = self.abbreviate_path_for_shell(pathlib.Path(str(path).replace(" ", "\\ ")))
			else:
				path = shlex.quote(str(path))
		return path

	def abbreviate_path_for_shell(self, path):
		path_parts = list(path.parts)
		if path_parts[:len(self._home_parts)] == self._home_parts:
			path_parts[:len(self._home_parts)] = "~"
			path = pathlib.Path(*path_parts)
		return path


@command("add")
class Add(object):
	@classmethod
	def define_arguments(cls, parser):
		pass

	@classmethod
	def short_description(cls):
		return ""

	def __init__(self):
		pass

	async def execute(self, *, opts, config):
		pass


@command("remove", "rm")
class Remove(object):
	@classmethod
	def define_arguments(cls, parser):
		pass

	@classmethod
	def short_description(cls):
		return ""

	def __init__(self):
		pass

	async def execute(self, *, opts, config):
		pass


@command("cleanup")
class Cleanup(object):
	@classmethod
	def define_arguments(cls, parser):
		pass

	@classmethod
	def short_description(cls):
		return ""

	def __init__(self):
		pass

	async def execute(self, *, opts, config):
		pass


@command("foreach")
class Foreach(object):
	@classmethod
	def define_arguments(cls, parser):
		pass

	@classmethod
	def short_description(cls):
		return ""

	def __init__(self):
		pass

	async def execute(self, *, opts, config):
		pass
