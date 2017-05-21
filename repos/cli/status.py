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

		#TODO add an optional command line parameter to signify the folder from which status should be shown
		#TODO Implement remote reference, configuration, and hook checking.

		#TODO fix the config
		config_path_dir = pathlib.Path(config["path"]).absolute().parent
		repositories = list(config_path_dir / repo for repo in config["repositories"])

		result = [
			["#", "Repository Path"] #TODO Implement a column sorting mechanism and remove this.
		]
		header_row = result[0]

		for repo in repositories:
			p = await asyncio.create_subprocess_exec("git", "-C", os.fspath(repo), "rev-parse", "--is-bare-repository", stdout=subprocess.PIPE)
			stdout, stderr = await p.communicate()
			assert p.returncode == 0
			assert not stderr
			if stdout.decode().strip() != "false":
				continue
			p = await asyncio.create_subprocess_exec("git", "-C", os.fspath(repo), "status", "--porcelain", stdout=subprocess.PIPE)
			stdout, stderr = await p.communicate()
			assert p.returncode == 0
			assert not stderr
			if not stdout:
				continue
			statistics = collections.defaultdict(int)
			statistics["Repository Path"] = str(self._decorate_path_for_output(repo))
			for line in stdout.decode().splitlines():
				status = None
				index, worktree, filepath, renamed_to = re.match(self._status_line_pattern, line).groups()
				index = "•" if index == " " else index
				worktree = "•" if worktree == " " else worktree
				status = f"{index}{worktree}"
				statistics[status] += 1

			row = [""] * len(header_row)
			for column_name in sorted(statistics.keys()):
				if column_name in header_row:
					column_index = header_row.index(column_name)
				else:
					header_row.append(column_name)
					column_index = len(header_row) - 1
				while len(row) <= column_index:
					row.append("")
				row[column_index] = statistics[column_name]
			result.append(row)
			add_status_msg(".")

		set_status_msg(None)

		num_index = header_row.index("#")
		for r, row in enumerate(result):
			if r == 0:
				continue
			row[num_index] = r

		def cell_filter(*, row, column, value, width, fill):
			if row == 0 or column == 1:
				return str(value).ljust(width, fill)
			else:
				return str(value).rjust(width, fill)

		draw_table(result, fo=sys.stdout, has_header=True, cell_filter=cell_filter)

	_status_line_pattern = re.compile(r"^([ MADRCU?!])([ MADRCU?!]) (.*?)(?: -> (.*?))?$")

	_home_parts = list(pathlib.Path.home().parts)

	def _decorate_path_for_output(self, path):
		if self._shellify_paths:
			if shlex.quote(str(path)) == str(path):
				repo_parts = list(path.parts)
				if repo_parts[:len(self._home_parts)] == self._home_parts:
					repo_parts[:len(self._home_parts)] = "~"
					path = pathlib.Path(*repo_parts)
			else:
				path = shlex.quote(str(path))
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

