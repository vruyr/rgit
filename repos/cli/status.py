import sys, os, pathlib, asyncio, subprocess, re, collections, shlex, itertools
from ..tools import draw_table, set_status_msg, add_status_msg, url_starts_with
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
		self._config = None
		self._shellify_paths = False

	async def execute(self, *, opts, config):
		self._config = config
		self._shellify_paths = opts.shell

		# TODO Add an optional command line parameter for folder from which status should be shown
		# TODO Implement remotes, configuration, and hook checking.
		# TODO Implement submodule checking (local vs remote commit, detached head, ...)

		status_table = [
			# TODO Implement a column sorting mechanism and remove this.
			["#", "Repository Path"]
		]
		column_names = status_table[0]

		for repo in self._config.repositories:
			add_status_msg(".")
			statistics = collections.defaultdict(int)
			await self.get_repo_status_stats(repo, statistics)
			await self.get_repo_remotes(repo, statistics)
			await self.get_repo_commit_statistics(repo, statistics)
			if not statistics.keys():
				continue
			statistics["Repository Path"] = self._decorate_path_for_output(repo)
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
		if await self.git_is_bare(repo):
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

	async def get_repo_remotes(self, repo, statistics):
		destination_remotes = set()
		other_remotes = set()
		async for remote_name, remote_config in self.enumerate_remotes(repo):
			if await self.matching_destination_remote(remote_config["url"][-1]) is not None:
				destination_remotes.add(remote_name)
			else:
				other_remotes.add(remote_name)

		if await self.matching_destination_folder(repo) is not None:
			if destination_remotes:
				statistics["Remotes"] = ", ".join(sorted(destination_remotes))
		else:
			if not destination_remotes:
				statistics["Remotes"] = " - "

		if other_remotes:
			statistics["Other Remotes"] = ", ".join(sorted(other_remotes))

	async def git_get_remotes(self, repo):
		return (await self.git(repo, "remote")).splitlines()

	async def git_get_remote_config(self, repo, remote):
		text = await self.git(repo, "config", "--get-regex", f"remote\\.{remote}\\..*")
		for x in self.walk_git_config_regex_output(text, f"remote.{remote}."):
			yield x

	async def git_get_branch_config(self, repo, branch, *, returncode_ok=False):
		text = await self.git(
			repo, "config", "--get-regex", f"branch\\.{branch}\\..*", returncode_ok=returncode_ok
		)
		for x in self.walk_git_config_regex_output(text, f"branch.{branch}."):
			yield x

	def walk_git_config_regex_output(self, text, prefix):
		for line in text.splitlines():
			key, value = line.split(" ", maxsplit=1)
			assert key.startswith(prefix), (prefix, key)
			key = key[len(prefix):].strip()
			value = value.strip()
			yield key, value

	async def enumerate_remotes(self, repo, *, remotes=None):
		if remotes is None:
			remotes = await self.git_get_remotes(repo)
		for remote in remotes:
			remote_config = {}
			async for key, value in self.git_get_remote_config(repo, remote):
				remote_config.setdefault(key, []).append(value)
			yield (remote.strip(), remote_config)

	async def matching_destination_remote(self, url):
		for destination_remote in self._config.destination_remotes:
			if url_starts_with(url, destination_remote):
				return destination_remote
		return None

	async def matching_destination_folder(self, path):
		for destination_folder in self._config.destination_folders:
			if destination_folder.parts == path.parts[:len(destination_folder.parts)]:
				return destination_folder
		return None

	async def get_repo_commit_statistics(self, repo, statistics):
		remotes = {}
		other_remotes = {}

		unsupported_remote_configs = {}
		d_remote_t = collections.namedtuple("d_remote_t", ["url", "fetch"])
		async for remote_name, remote_config in self.enumerate_remotes(repo):
			remote_url = remote_config.pop("url")
			remote_fetch = remote_config.pop("fetch")
			if remote_config:
				unsupported_remote_configs[remote_name] = remote_config
			remote = d_remote_t(remote_url, remote_fetch)
			if await self.matching_destination_remote(remote.url[-1]) is not None:
				remotes[remote_name] = remote
			else:
				other_remotes[remote_name] = remote
		if unsupported_remote_configs:
			statistics["Unsupported Remote Config"] = unsupported_remote_configs
			return

		if not remotes:
			return

		remote_refspecs = {}

		for remote_name, remote_config in itertools.chain(remotes.items(), other_remotes.items()):
			# https://git-scm.com/book/en/v2/Git-Internals-The-Refspec
			for refspec in remote_config.fetch:
				non_ff = False
				if refspec[0] == "+":
					non_ff = True
					refspec = refspec[1:]
				src, sep, dst = refspec.partition(":")
				assert sep == ":"
				remote_refspecs[dst] = (src, remote_name)

		local_revs = {}
		remote_revs = {}

		for ref_str in (await self.git(repo, "show-ref")).splitlines():
			object_id, ref_name = ref_str.split(" ", maxsplit=1)
			ref = pathlib.PurePosixPath(ref_name)

			for dst, (src, remote_name) in remote_refspecs.items():
				if ref.match(dst):
					# TODO PurePosixPath.match() have a little different logic than git's globs
					remote_revs[object_id] = (ref_name, dst, src, remote_name)
					break
			else:
				ref = list(ref.parts)

				assert ref[0] == "refs"

				if ref[1] == "heads":
					branch = "/".join(ref[2:])
					branch_remote = None
					branch_merge = None
					async for key, value in self.git_get_branch_config(repo, branch, returncode_ok=True):
						if key == "remote":
							branch_remote = value
						elif key == "merge":
							branch_merge = value
						elif key in ("push", "pushremote"):
							# TODO Shall we do something special here?
							pass
						else:
							raise ValueError("unrecognized branch config", (repo, key, value))
					local_revs[object_id] = (ref_name, branch_remote, branch_merge)
				elif ref[1] in ("tags", "notes"):
					# TODO Implement tag and notes support
					pass
				else:
					raise ValueError(f"Unrecognized Reference {ref_name}")

		# TODO Only check outgoing changes to "safe" remotes

		if remote_revs:
			revs = [*(local_revs.keys()), *map(lambda x: f"^{x}", remote_revs.keys())]
			count = len((await self.git(repo, "rev-list", *revs)).splitlines())
			if count:
				statistics["Out"] = count

	async def git_get_tracking_branches(self, repo, branch):
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

	async def git_is_bare(self, repo):
		stdout = await self.git(repo, "rev-parse", "--is-bare-repository")
		return {"true": True, "false": False}[stdout.strip()]

	@staticmethod
	async def git(repo, *args, stderr_ok=False, returncode_ok=False):
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
		if not returncode_ok:
			assert p.returncode == 0, (repo, p.returncode, stderr)
		if not stderr_ok:
			assert not stderr, (repo, p.returncode, stderr)
		return stdout.decode()

	_status_line_pattern = re.compile(r"^([ MADRCUT?!])([ MADRCUT?!]) (.*?)(?: -> (.*?))?$")

	_home_parts = list(pathlib.Path.home().parts)

	def _decorate_path_for_output(self, path):
		if self._shellify_paths:
			try:
				path = path.relative_to(pathlib.Path.cwd())
			except ValueError:
				pass
			path_str = os.fspath(path)
			path_str = path_str.replace("\\", "/")
			if shlex.quote(path_str) == path_str:
				path = self.abbreviate_path_for_shell(path)
			elif shlex.quote(path_str.replace(" ", "")) == path_str.replace(" ", ""):
				path = self.abbreviate_path_for_shell(pathlib.Path(path_str.replace(" ", "\\ ")))
			else:
				path = shlex.quote(path_str)
		else:
			path_str = os.fspath(path)
		return path_str

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
