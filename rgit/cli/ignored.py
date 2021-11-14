import re, os, sys, pathlib
from .registry import command
from .. import git
from ..tools import is_path_in, path_relative_to_or_unchanged, strict_int, add_status_msg, set_status_msg, draw_table


@command("ignored")
class Ignored(object):
	@classmethod
	def define_arguments(cls, parser):
		parser.add_argument(
			"--format", "-f",
			dest="format",
			action="store",
			choices=["table", "json"],
			default="table",
		)
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
		parser.add_argument(
			"--not-in-group", "-x",
			dest="not_in_groups",
			action="append",
			default=[],
			help="",
		)
		parser.add_argument(
			"--list", "-l",
			dest="show_lists_only",
			action="store",
			metavar="NAME",
			default=None,
			help="show list of groups only"
		)
		parser.add_argument(
			"folders",
			nargs="*",
			metavar="FOLDER",
			help="only inspect repositories worktrees of which are in one of specified folders"
		)
	@classmethod
	def short_description(cls):
		return "show and manipulate ignored files in repositories"

	def __init__(self):
		self._config = None

	async def execute(self, *, opts, config):
		self._config = config

		opts.folders = [pathlib.Path(f).resolve() for f in opts.folders]
		opts.groups = set(opts.groups)
		opts.not_in_groups = set(opts.not_in_groups)

		ignore_group_reader = IgnoreGroupReader()

		results = {}
		for repo in self._config.repositories:
			if await git.is_bare(repo):
				add_status_msg(".")
				continue

			worktree_path = await git.toplevel(repo)
			worktree_fspath = os.fspath(worktree_path)

			if opts.folders and not any(is_path_in(f, worktree_path) for f in opts.folders):
				add_status_msg("-")
				continue

			add_status_msg("*")

			ignored_files = [
				path
				for _, path in filter(
					lambda x: x[0] == "ignored",
					await git.status(repo, "--ignored=matching")
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

			for ignore_file, ignore_file_line, ignore_pattern, path in ignored:
				ignore_file = None if ignore_file == "" else worktree_path / ignore_file
				ignore_file_line = None if ignore_file_line == "" else strict_int(ignore_file_line)
				assert (ignore_file is None) == (ignore_file_line is None)
				groups = ignore_group_reader.get_groups(ignore_file, ignore_file_line)
				if groups is None:
					group = "<failed to identify matching ignore pattern>"
				elif len(groups) < 1:
					group = "-"
				else:
					assert len(groups) <= 1
					group = groups[0]
				if opts.groups and group not in opts.groups:
					continue
				if group in opts.not_in_groups:
					continue
				ignore_file_fspath = os.fspath(ignore_file) if ignore_file is not None else None
				results.setdefault(group, {}).setdefault(worktree_fspath, {})[path] = [
					ignore_file_fspath, ignore_file_line, ignore_pattern
				]
		set_status_msg(None)

		if opts.show_lists_only is not None:
			lists_to_show = set(re.split(r"[,\s]+", opts.show_lists_only))
			at_least_one_list_shown = False
			def show_list(thelist, *, sort=True):
				if sort:
					thelist = sorted(thelist)
				nonlocal at_least_one_list_shown
				if at_least_one_list_shown:
					sys.stdout.write("\n")
				else:
					at_least_one_list_shown = True
				if opts.format == "json":
					import json
					json.dump(thelist, sys.stdout, indent="\t")
					sys.stdout.write("\n")
				else:
					# TODO If the file name contains unprintable chars (like "Icon\r") this will produce an incorrect list. Consider adding an escape flavor like "python", "shell", "c", etc.
					sys.stdout.write("\n".join(thelist))
					if thelist:
						sys.stdout.write("\n")

			if "groups" in lists_to_show:
				lists_to_show.remove("groups")
				show_list(list(results.keys()))

			if "sources" in lists_to_show:
				lists_to_show.remove("sources")
				thelist = set()
				for group in results.values():
					for workdir in group.values():
						for file in workdir.values():
							thelist.add(f"{file[0]}:{file[1]}")
				show_list(map(str, thelist))

			if "files" in lists_to_show:
				lists_to_show.remove("files")
				thelist = set()
				for group in results.values():
					for workdir_path, workdir in group.items():
						for file in workdir.keys():
							thelist.add(os.path.join(workdir_path, file))
				show_list(thelist)

			if lists_to_show:
				raise ValueError(f"unsupported lists {lists_to_show}")
		else:
			if opts.format == "json":
				import json
				fo = sys.stdout
				json.dump(results, fo, indent="\t")
				fo.write("\n")
				fo.flush()
			elif opts.format == "table":
				for group, repos in results.items():
					rows = [
						["Work-tree Path", "File Path", "Source", "Pattern"]
					]
					for path, files in repos.items():
						for file, (ignore_path, ignore_line, ignore_pattern) in files.items():
							if file != repr(file)[1:-1]:
								file = repr(file)
							if ignore_path is not None:
								ignore_path_relative = path_relative_to_or_unchanged(path, ignore_path)
								ignore_rule_location = f"{ignore_path_relative}:{ignore_line}"
							else:
								ignore_rule_location = "<unknown>"
							rows.append([
								path, file, ignore_rule_location, ignore_pattern
							])
					draw_table(
						rows,
						title=group,
						has_header=True,
						fo=sys.stdout,
					)
			else:
				raise ValueError(f"unsupported output format {repr(opts.format)}")


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
		group_name_pattern = re.compile(r"^[a-z0-9_]+$")
		group_stack = []
		with path.open("r") as fo:
			for line in fo:
				if line.startswith(start_marker):
					# TODO Instead of converting to lowercase, use case-insensitive mapping and report any inconsistencies.
					group = line[len(start_marker):].strip().lower()
					if not group_name_pattern.match(group):
						raise ValueError(f"invalid group name - {repr(group)} in {repr(os.fspath(path))}")
					group_stack.append(group)
				elif line.startswith(end_marker):
					group_stack.pop(-1)
				if len(group_stack) > 1:
					raise ValueError("nested groups are not supported yet")
				result.append(list(set(group_stack)))
		return result
