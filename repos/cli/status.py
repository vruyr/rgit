import sys, os, pathlib, asyncio, subprocess, re, collections, shlex, itertools
from ..tools import draw_table, set_status_msg, add_status_msg, url_starts_with, gen_sort_index
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
		# TODO Implement configuration and hook checking.
		# TODO Implement submodule checking (local vs remote commit, detached head, ...)

		statistics_table = []

		for repo in self._config.repositories:
			add_status_msg(".")
			statistics = {}
			await self.get_repo_remotes(repo, statistics)
			await self.get_repo_commit_statistics(repo, statistics)
			await self.get_repo_status_stats(repo, statistics)
			await self.render_statistics_row(statistics_table, repo, statistics)

		set_status_msg(None)

		sort_order = ["#", "Repository Path", "Remotes", "Commits"]
		def cell_filter(*, row, column, value, width, fill):
			if row == 0 or column == 1:
				return str(value).ljust(width, fill)
			if column == 2 and str(value).strip() == "-":
				return str(value).strip().center(width, fill)
			return str(value).rjust(width, fill)

		statistics_table_sorted = []
		sort_index = gen_sort_index(statistics_table[0], sort_order)
		for row in statistics_table:
			row_sorted = []
			for i in sort_index:
				row_sorted.append(row[i] if i < len(row) else "")
			statistics_table_sorted.append(row_sorted)

		draw_table(statistics_table_sorted, fo=sys.stdout, has_header=True, cell_filter=cell_filter)

	async def render_statistics_row(self, statistics_table, repo, statistics):
		if not statistics.keys():
			return
		if not statistics_table:
			statistics_table.append([])
		column_names = statistics_table[0]
		statistics["#"] = len(statistics_table)
		statistics["Repository Path"] = self._decorate_path_for_output(repo)
		row = [""] * len(column_names)
		for column_name in statistics.keys():
			if column_name in column_names:
				column_index = column_names.index(column_name)
			else:
				column_names.append(column_name)
				column_index = len(column_names) - 1
			while len(row) <= column_index:
				row.append("")
			row[column_index] = statistics[column_name]
		statistics_table.append(row)

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
			statistics.setdefault(status, 0)
			statistics[status] += 1

	async def get_repo_remotes(self, repo, statistics):
		destination_remotes = set()
		other_remotes = set()
		if await self.matching_ignore_folder(repo) is not None:
			return
		async for remote_name, remote_config in self.enumerate_remotes(repo):
			remote_url = remote_config["url"][-1]
			if await self.matching_destination_remote(remote_url) is not None:
				destination_remotes.add(remote_name)
			else:
				if await self.matching_ignore_remote(remote_url) is None:
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
		for remote_url_prefix in self._config.destination_remotes:
			if url_starts_with(url, remote_url_prefix):
				return remote_url_prefix
		return None

	async def matching_destination_folder(self, path):
		for folder in self._config.destination_folders:
			if folder.parts == path.parts[:len(folder.parts)]:
				return folder
		return None

	async def matching_ignore_remote(self, url):
		for remote_url_prefix in self._config.ignore_remotes:
			if url_starts_with(url, remote_url_prefix):
				return remote_url_prefix
		return None

	async def matching_ignore_folder(self, path):
		for folder in self._config.ignore_folders:
			if folder.parts == path.parts[:len(folder.parts)]:
				return folder
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

		local_refs = {}
		remote_refs = {}

		for ref_str in (await self.git(repo, "show-ref")).splitlines():
			object_id, ref_name = ref_str.split(" ", maxsplit=1)
			ref = pathlib.PurePosixPath(ref_name)

			for dst, (src, remote_name) in remote_refspecs.items():
				if ref.match(dst):
					# TODO PurePosixPath.match() have a little different logic than git's globs
					src_parts = list(pathlib.PurePosixPath(src).parts)
					dst_parts = list(pathlib.PurePosixPath(dst).parts)
					assert src_parts[-1] == "*"
					assert dst_parts[-1] == "*"
					remote_ref = src_parts[:-1]
					remote_ref.extend(ref.parts[(len(dst_parts) - 1):])
					remote_ref = "/".join(remote_ref)
					remote_refs[(remote_name, remote_ref)] = (ref_name, object_id)
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
					local_refs[ref_name] = (object_id, branch_remote, branch_merge)
				elif ref[1] in ("tags", "notes"):
					# local_refs[ref_name] = (object_id, None, None)
					# TODO Implement tag and notes support
					pass
				else:
					raise ValueError(f"Unrecognized Reference {ref_name}")

		dangling_refs = []
		tracking_refs = []
		for ref, (object_id, branch_remote, branch_merge) in local_refs.items():
			if not branch_remote or branch_remote not in remotes:
				dangling_refs.append(ref)
				continue
			remote_ref, remote_object_id = remote_refs[(branch_remote, branch_merge)]
			tracking_refs.append((ref, object_id, remote_ref, remote_object_id))

		if dangling_refs:
			statistics["Refs"] = len(dangling_refs)

		revs = []
		for ref, object_id, remote_ref, remote_object_id in tracking_refs:
			revs.extend((await self.git(repo, "rev-list", object_id, f"^{remote_object_id}")).splitlines())
		if revs:
			statistics["Commits"] = len(revs)

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
