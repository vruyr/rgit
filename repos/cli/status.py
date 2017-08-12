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
			# TODO Implement a column sorting mechanism and remove this.
			["#", "Repository Path", "Out"]
		]
		column_names = status_table[0]

		for repo in repositories:
			add_status_msg(".")
			statistics = collections.defaultdict(int)
			await self.get_repo_status_stats(repo, statistics)
			await self.get_repo_commit_statistics(repo, statistics)
			if not statistics.keys():
				continue
			statistics["Repository Path"] = str(self._decorate_path_for_output(repo))
			row = await self.render_statistics_row(column_names, statistics)
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

	async def render_statistics_row(self, column_names, statistics):
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

	async def get_repo_status_stats(self, repo, statistics):
		if await self.is_repo_bare(repo):
			return
		stdout = await self.git(repo, "status", "--porcelain")
		if not stdout:
			return
		for line in stdout.splitlines():
			status = None
			m = re.match(self._status_line_pattern, line)
			index, worktree, dummy_filepath, dummy_renamed_to = m.groups()
			index = "•" if index == " " else index
			worktree = "•" if worktree == " " else worktree
			status = f"{index}{worktree}"
			statistics[status] += 1

	async def get_repo_commit_statistics(self, repo, statistics, *, without_remotes=False, even_bare=False):
		local_revs = set()
		remote_revs = set()

		for ref_str in (await self.git(repo, "show-ref")).splitlines():
			object_id, ref_name = ref_str.split(" ", maxsplit=1)
			ref = list(pathlib.PurePosixPath(ref_name).parts)

			assert ref[0] == "refs"

			if ref[1] == "heads":
				local_revs.add(object_id)
			elif ref[1] == "remotes":
				remote_revs.add(object_id)
			elif ref[1] in ("tags",):
				# TODO Implement tag support
				pass
			else:
				raise ValueError(f"Unrecognized Reference {ref_name}")

		if not remote_revs:
			if without_remotes and (even_bare or not (await self.is_repo_bare(repo))):
				statistics["Out"] = " - "
		else:
			revs = [*local_revs, *map(lambda x: f"^{x}", remote_revs)]
			count = len((await self.git(repo, "rev-list", *revs)).splitlines())
			if count:
				statistics["Out"] = count

			# TODO As a temporary measure, showing all the commits not present in any of the remotes
			#      will give some useful info, but that is not a correct representation of the
			#      situation. Instead, for each local branch (refs/heads/*) a corresponding tracking
			#      branches (@{upstream}, @{push}) should be inspected. If a local branch does not
			#      have a tracking remote branch, the closes point towards the first commit
			#      available in any remote should be considered and outstanding commits reported as
			#      outgoing. If the repository have a remote but have no local branches tracking any
			#      of the branches of that remote, it is effectively the same as not having that
			#      remote.

	async def get_tracking_branches(self, repo, branch):
		try:
			upstream = await self.git(repo, "rev-parse", "--symbolic-full-name", branch + "@{upstream}")
			upstream = upstream.strip()
		except:
			upstream = None
		try:
			push = await self.git(repo, "rev-parse", "--symbolic-full-name", branch + "@{push}")
			push = push.strip()
		except:
			push = None
		return (upstream, push)

	async def is_repo_bare(self, repo):
		stdout = await self.git(repo, "rev-parse", "--is-bare-repository")
		return {"true": True, "false": False}[stdout.strip()]

	@staticmethod
	async def git(repo, *args):
		p = await asyncio.create_subprocess_exec(
			"git", "-C", os.fspath(repo), *args,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			stdin=subprocess.DEVNULL,
			env=update_env(
				GIT_TERMINAL_PROMPT="0"
			)
		)
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


def update_env(*args, **kwargs):
	new_env = dict(os.environ.items())
	new_env.update(args)
	new_env.update(kwargs.items())
	return new_env


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
