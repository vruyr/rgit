import sys, os, pathlib, re, collections, shlex, itertools, json
from ..tools import draw_table, set_status_msg, add_status_msg, url_starts_with, gen_sort_index, is_path_in
from .registry import command
from .. import git


# TODO Implement detection of repositories in working copies of other repositories without proper submodule references.
# TODO Implement outgoing commits and local modifications detection in submodules.
# TODO Implement reporting commits in submodules committed to super-repo but not yet pushed in the submodule.
# TODO Implement configuration and hook checking.
# TODO Implement detached head detection in submodules.
# TODO Fix broken `rgit status --sh`
# TODO Use `git check-attr` to find all unconfigured filters.
# TODO Implement email address consistency checks in the history.
# TODO If a repo has more than one destination remote, chances are they have a same set of refs.
# TODO Implement worktree support.
# TODO Detect if the worktree is in the middle of merge, rebase, or anything like that.
# TODO Detect if the repo is missing and report that instead of crashing.
# TODO Reconsider semantics of the "Commits" column. Maybe having it show commits that do not exist in any/all of destination remotes would be better. Tracking references that are head of or diverged from upsteam could be done in the "Refs" column or a new column.
# TODO git ls-files --eol && file --mime-encoding


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
		parser.add_argument(
			"--json",
			dest="output_json",
			action="store_true",
			default=False,
			help="output the result in JSON format instead of a rendered table view",
		)
		parser.add_argument(
			"folders",
			nargs="*",
			metavar="FOLDER",
			help="only inspect repositories that are in one of specified folders"
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

		opts.folders = [pathlib.Path(f).resolve() for f in opts.folders]

		statistics_table = []

		for repo in self._config.repositories:
			if opts.folders and not any(is_path_in(f, repo) for f in opts.folders):
				add_status_msg("-")
				continue
			add_status_msg("*")
			statistics = {}
			gitdir_exists, worktree_exists = await git.exists(repo)
			if (gitdir_exists, worktree_exists) in ((True, True), (True, None)):
				await self.get_repo_remotes(repo, statistics)
				await self.get_repo_commit_statistics(repo, statistics)
				await self.get_repo_status_stats(repo, statistics)
			elif (gitdir_exists, worktree_exists) in ((True, False),):
				statistics["Notes"] = "missing worktree"
			else:
				statistics["Notes"] = "missing repo"
			await self.render_statistics_row(statistics_table, repo, statistics)

		set_status_msg(None)

		sort_order = [
			["#", "Path", "Notes", "Remotes", "Commits", "Refs"],
			["Unsupported Remote Config"],
		]
		def cell_filter(*, row, column, value, width, fill):
			if row == 0 or column == 1:
				return str(value).ljust(width, fill)
			if column == 2 and str(value).strip() == "-":
				return str(value).strip().center(width, fill)
			if isinstance(value, (int, float)):
				return str(value).rjust(width, fill)
			return str(value).ljust(width, fill)

		if statistics_table:
			statistics_table_sorted = []
			sort_index = gen_sort_index(statistics_table[0], sort_order)
			for row in statistics_table:
				row_sorted = []
				for i in sort_index:
					row_sorted.append(row[i] if i < len(row) else "")
				statistics_table_sorted.append(row_sorted)
			statistics_table = statistics_table_sorted

		if opts.output_json:
			result = {}
			header_row = statistics_table[0]
			num_columns = len(header_row)
			for row in statistics_table[1:]:
				r = {header_row[i]:row[i] for i in range(num_columns)}
				result[r["Path"]] = r
				del r["Path"]
				del r["#"]
			sys.stdout.write(json.dumps(result, indent="\t"))
			sys.stdout.write("\n")
		else:
			draw_table(statistics_table, fo=sys.stdout,
				title="Unclean Repositories",
				has_header=True,
				cell_filter=cell_filter
			)

	async def render_statistics_row(self, statistics_table, repo, statistics):
		if not statistics.keys():
			return
		if not statistics_table:
			statistics_table.append([])
		column_names = statistics_table[0]
		statistics["#"] = len(statistics_table)
		statistics["Path"] = self._decorate_path_for_output(repo)
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
		if await git.is_bare(repo):
			return
		# TODO Switch to using ..git.status() instead of calling the git command directly.
		stdout = await git.git(repo, "status", "--porcelain")
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
		async for remote_name, remote_config in git.enumerate_remotes(repo):
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
		for remote_url_prefix in self._config.destination_remotes_ignore:
			if url_starts_with(url, remote_url_prefix):
				return remote_url_prefix
		return None

	async def matching_ignore_folder(self, path):
		for folder in self._config.destination_folders_ignore:
			if folder.parts == path.parts[:len(folder.parts)]:
				return folder
		return None

	async def get_repo_commit_statistics(self, repo, statistics):
		remotes = {}
		other_remotes = {}

		ignored_remote_configs = []
		async for ignores in git.get_config(repo, "rgit.ignore-remote-config", returncode_ok=lambda x: True):
			ignored_remote_configs.extend(re.split(r"\s+", ignores))

		unsupported_remote_configs = {}
		d_remote_t = collections.namedtuple("d_remote_t", ["url", "fetch"])
		async for remote_name, remote_config in git.enumerate_remotes(repo):
			remote_url = remote_config.pop("url")
			#TODO Implement support for more than one fetch entry.
			remote_fetch = remote_config.pop("fetch", None)
			if remote_fetch is None:
				#TODO Reconsider the logic here - if there are no fetch refspecs, does it mean we have nothing to do?
				continue
			#TODO Implement tag support.
			# remote_push = remote_config.pop("push")
			# TODO Implement remote.<name>.push config support. This needs a redesign of local to remote branch mapping from a single link to a double link (fetch and push).
			remote_config.pop("push", None)

			#TODO Make sure these remote configurations do not affect commit statistics.
			remote_config.pop("receivepack", None)
			remote_config.pop("uploadpack", None)
			remote_config.pop("skipfetchall", None)
			for ignored in ignored_remote_configs:
				remote_config.pop(ignored, None)

			#TODO Implement calculating number of refs with commits not present in the local repo.
			ignored_remote_refs = remote_config.pop("rgit-ignore-refs", None)

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
				# TODO Extract refspec parsing to a standalone function.
				non_ff = False
				if refspec[0] == "+":
					non_ff = True
					refspec = refspec[1:]
				if refspec[0] == "^":
					#TODO Implement support for negative refspecs.
					continue
				src, sep, dst = refspec.partition(":")
				assert sep == ":"
				remote_refspecs[dst] = (src, remote_name)

		local_refs = {}
		remote_refs = {}

		for ref_str in (await git.git(repo, "show-ref")).splitlines():
			object_id, ref_name = ref_str.split(" ", maxsplit=1)
			ref = pathlib.PurePosixPath(ref_name)

			for dst, (src, remote_name) in remote_refspecs.items():
				remote_ref = match_refspec(ref_name, dst, src)
				if remote_ref is not None:
					remote_refs[(remote_name, remote_ref)] = (ref_name, object_id)
					break
			else:
				ref = list(ref.parts)

				assert ref[0] == "refs"

				if ref[1] == "heads":
					branch = "/".join(ref[2:])
					branch_remote = None
					branch_merge = None
					async for key, value in git.get_config_branch(repo, branch, returncode_ok=lambda x: True):
						if key == "remote":
							branch_remote = value
						elif key == "merge":
							branch_merge = value
						elif key in ("push", "pushremote"):
							# TODO Shall we do something special if branch push and pushremote are configured?
							pass
						else:
							raise ValueError("unrecognized branch config", (repo, key, value))
					local_refs[ref_name] = (object_id, branch_remote, branch_merge)
				elif ref[1] in ("tags", "notes"):
					# local_refs[ref_name] = (object_id, None, None)
					# TODO Implement refs/tags/ and refs/notes/ support.
					pass
				else:
					raise ValueError(f"Unrecognized Reference {ref_name} in repo {repo}")

		dangling_refs = []
		tracking_refs = []
		for ref, (object_id, branch_remote, branch_merge) in local_refs.items():
			if not branch_remote or branch_remote not in remotes:
				dangling_refs.append(ref)
				continue
			#TODO If the remote branch is deleted but the local branch is still tracking it, this will throw a KeyError
			remote_ref, remote_object_id = remote_refs[(branch_remote, branch_merge)]
			tracking_refs.append((ref, object_id, remote_ref, remote_object_id))

		if dangling_refs:
			statistics["Refs"] = len(dangling_refs)

		revs = []
		for ref, object_id, remote_ref, remote_object_id in tracking_refs:
			revs.extend((await git.git(repo, "rev-list", object_id, f"^{remote_object_id}")).splitlines())
		if revs:
			statistics["Commits"] = len(revs)

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


def match_refspec(ref, spec, other_spec):
	# https://git-scm.com/book/en/v2/Git-Internals-The-Refspec
	spec_pre, spec_asterisk, spec_post = spec.partition("*")
	other_spec_pre, other_spec_asterisk, other_spec_post = other_spec.partition("*")

	if spec_asterisk == "":
		assert other_spec_asterisk == ""
		return other_spec if ref == spec else None
	else:
		assert spec_asterisk == "*"
		assert other_spec_asterisk == "*"

	assert (
		(other_spec_pre == "" or other_spec_pre[-1] == "/") and
		(other_spec_post == "" or other_spec_post[0] == "/")
	)
	assert (
		(spec_pre == "" or spec_pre[-1] == "/") and
		(spec_post == "" or spec_post[0] == "/")
	)

	# TODO Double check this
	prefix = ref[:len(spec_pre)]
	infix = ref[len(spec_pre):(len(ref)-len(spec_post))]
	suffix = ref[(len(ref)-len(spec_post)):]

	if prefix == spec_pre and suffix == spec_post:
		return other_spec_pre + infix + other_spec_post
	else:
		return None


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
