import os, sys, pathlib, collections, functools

from ..tools import set_status_msg, add_status_msg
from .registry import command
from .. import git

# pip install -U pyyaml==6.0.1
import yaml


# TODO Implement worktree support.


@command("scan")
class Scan(object):
	@classmethod
	def define_arguments(cls, parser):
		parser.add_argument(
			"starting_folders",
			metavar="PATH",
			nargs="*",
			help="starting folders from where to conduct the search",
		)
		parser.add_argument(
			"--output", "-o",
			dest="output_path",
			metavar="PATH",
			action="store",
			type=pathlib.Path,
			default=None,
			help="besides outputting found repositories on stdout, also write a YAML document at given path"
		)
		parser.add_argument(
			"--ignore", "-i",
			dest="scan_folders_ignore",
			metavar="PATH",
			action="append",
			type=pathlib.Path,
			default=[],
			help="do not scan specified folders and their sub-folders",
		)
		parser.add_argument(
			"--show-all",
			dest="show_all",
			action="store_true",
			default=False,
			help="report all found repositories, even those already added to configuration"
		)
		parser.add_argument(
			"--skip-gitdirs",
			dest="skip_gitdirs",
			action="store_true",
			default=False,
			help="do not traverse into gitdirs of discovered repos"
		)
		parser.add_argument(
			"--skip-worktrees",
			dest="skip_worktrees",
			action="store_true",
			default=False,
			help="do not traverse into worktrees of discovered repos"
		)

	@classmethod
	def short_description(cls):
		return "walk the filesystem to discover new repositories"

	def __init__(self):
		pass

	async def execute(self, *, opts, config):
		dirs_to_skip = {
			*(opts.scan_folders_ignore),
			*(config.scan_folders_ignore)
		}
		scan_folders = opts.starting_folders or list(config.scan_folders)
		repositories_to_skip = set(config.repositories) if not opts.show_all else set()
		repositories_found = set()
		counter = 0
		for starting_folder in scan_folders:
			for root, dirs, files in os.walk(starting_folder, topdown=True):
				root = pathlib.Path(root)
				dirs.sort(key=lambda x: x.lower())

				counter += 1
				if counter >= 100:
					if opts.show_progress:
						add_status_msg(".")
					counter = 0

				repo = None

				# Note that if traversing into gitdir-s, a regular non-bare repo will be detected
				# twice - once for the worktree and once for the .git folder. Duplicates will be
				# collapsed thought via the `repositories_found` set object.

				if ".git" in dirs or ".git" in files:
					repo = git.Repo(gitdir=(root / ".git"), worktree=root)
					if opts.skip_gitdirs:
						try:
							dirs.remove(".git")
						except:
							pass
					if opts.skip_worktrees:
						re_add_gitdir = ".git" in dirs
						del dirs[:]
						if re_add_gitdir:
							dirs.append(".git")
				elif "refs" in dirs and "objects" in dirs and "HEAD" in files:
					#TODO A repo might be set up such that the objects directory is elsewhere,
					#  e.g. via GIT_OBJECT_DIRECTORY.
					#  See https://github.com/git/git/blob/v2.42.0/setup.c#L345-L355
					repo = git.Repo(gitdir=root)
					if opts.skip_gitdirs:
						del dirs[:]

				if repo is None:
					continue

				if repo in repositories_found:
					continue

				for ignored_folder in dirs_to_skip:
					if repo.gitdir.is_relative_to(ignored_folder):
						break
					if repo.worktree and repo.worktree.is_relative_to(ignored_folder):
						break
				else:
					repositories_found.add(repo)
					if opts.show_progress:
						set_status_msg(None)
					if repo.gitdir not in repositories_to_skip:
						await self.report_new_repo(repo)

		if opts.show_progress:
			set_status_msg(None)

		if opts.output_path is not None:
			await self.write_output_yaml(repositories_found, opts.output_path)

	async def write_output_yaml(self, repositories_found, output_path):
		# We only consider a config to be common is more than half has the same value.
		config_yaml_common_config_threshold = len(repositories_found) // 2
		# The gitdir and worktree paths are relative to user's home folder.
		config_yaml_relative_to = pathlib.Path.home()
		def make_path_relative(path):
			try:
				return path.relative_to(config_yaml_relative_to)
			except:
				return path
		# This is the resulting object that will be serialized into the output YAML document.
		config_yaml = {
			# Initially this will hold {"git-config-key": {"git-config-value": count}}, but later
			# Will be changed to be {"git-config-key": "git-config-value"} where the value is the
			# one with with the highest count if it is above the threshold.
			"config": (config_yaml_common_config := collections.defaultdict(
				functools.partial(collections.defaultdict, int)
			)),
			"repositories": (config_yaml_repositories := [])
		}
		for repo in sorted(repositories_found, key=lambda r: r.gitdir):
			config_yaml_repositories.append(
				#TODO Change this to collections.OrderedDict() and make PyYAML to render it as a regular dict.
				repo_entry := {}
			)

			repo_entry["gitdir"] = make_path_relative(repo.gitdir).as_posix()
			#TODO The gitdir path above and worktree paths below should be added as pathlib.Path objects and rendered by the YAML library in quotes and unbroken.
			if repo.worktree and repo.is_worktree_custom():
				#TODO Handle bare repos explicitly
				repo_entry["worktrees"] = {
					#TODO Think through the schema of the worktrees sub-object.
					make_path_relative(repo.worktree).as_posix(): None
				}

			repo_entry["remotes"] = {}
			repo_entry["branches"] = {}
			repo_entry["config"] = {}

			async for c in git.list_config(repo.gitdir):
				key, sep, value = c.partition("\n")
				assert sep == "\n", c

				# Special Cases
				if key == "core.worktree":
					assert (repo.gitdir / pathlib.Path(value)).samefile(repo.worktree)
					continue

				if key.startswith("remote."):
					section, remote_name, name = git.split_config_key(key)
					assert section == "remote", (key, section, remote_name, name)
					if remote_name:
						if name == "url":
							repo_entry["remotes"][remote_name] = value
							continue

				if key.startswith("branch."):
					section, branch_name, name = git.split_config_key(key)
					assert section == "branch", (key, section, branch_name, name)
					if branch_name:
						repo_entry["branches"].setdefault(branch_name, [None, None])
						if name == "remote":
							repo_entry["branches"][branch_name][0] = value
							continue

						if name == "merge":
							repo_entry["branches"][branch_name][1] = value
							continue

				repo_entry["config"][key] = single_value_or_tuple(repo_entry["config"].get(key), value)

			remote_fetch_keys = [
				k for k in repo_entry["config"].keys()
					if k.startswith("remote.") and k.endswith(".fetch")
			]
			for key in remote_fetch_keys:
				section, remote_name, name = git.split_config_key(key)
				assert section == "remote" and name == "fetch", (key, section, remote_name, name)
				value = repo_entry["config"][key]

				# Instead of skipping this, decompose the string to components and compare.
				if value == f"+refs/heads/*:refs/remotes/{remote_name}/*":
					del repo_entry["config"][key]

					# In case the "remote.<name>.fetch" is either alone or came first
					repo_entry["remotes"].setdefault(remote_name, None)

			#TODO Instead of relying on dict preserving key order, the yaml renderer should sort these keys.
			repo_entry["remotes"] = dict(sorted(repo_entry["remotes"].items(), reverse=True))
			if not len(repo_entry["remotes"]):
				del repo_entry["remotes"]

			# Updating the common config values as a separate loop to accommodate multi-value keys.
			for key, value in repo_entry["config"].items():
				config_yaml_common_config[key][value] += 1
				#TODO The yaml renderer should be able to take tuples as lists.
				repo_entry["config"][key] = str_or_list(value)

			# Normalize the branches
			branches_flat = []
			for key, value in repo_entry["branches"].items():
				remote, branch = value
				branches_flat.append(f"{key} <- {remote}:{branch}")
			if len(branches_flat):
				repo_entry["branches"] = branches_flat
			else:
				del repo_entry["branches"]

		# Convert the initial object with counts to have a flat key-value mapping but only if
		# the same value for the key appears in more than the threshold count of repos.
		config_yaml_config = {}
		for k, v in config_yaml["config"].items():
			# Get the value which has the biggest count
			v, count = sorted(v.items(), key=lambda x: x[1], reverse=True)[0]
			if count < config_yaml_common_config_threshold:
				# Only continue if count of the most often occurring value is at or above the threshold
				continue
			config_yaml_config[k] = str_or_list(v)
		config_yaml["config"] = config_yaml_config

		for repo_entry in config_yaml["repositories"]:
			for common_config_key, common_config_value in config_yaml["config"].items():
				if common_config_key not in repo_entry["config"]:
					repo_entry["config"][common_config_key] = None
				elif repo_entry["config"][common_config_key] == common_config_value:
					del repo_entry["config"][common_config_key]
			if not len(repo_entry["config"]):
				del repo_entry["config"]

		with open(output_path, "w", encoding="UTF-8") as fo:
			yaml.dump(config_yaml, default_flow_style=False, sort_keys=False, stream=fo)

	async def report_new_repo(self, repo):
		gitdir = repo.gitdir
		try:
			gitdir = gitdir.relative_to(pathlib.Path.home())
		except:
			pass
		sys.stdout.write(gitdir.as_posix())
		if repo.is_worktree_custom():
			sys.stdout.write("\t-> ")
			sys.stdout.write(repo.worktree.as_posix() if repo.worktree else "(bare)")
		sys.stdout.write("\n")
		sys.stdout.flush()


def single_value_or_tuple(previous_value, new_value):
	if previous_value is None:
		return new_value
	elif isinstance(previous_value, str):
		return (previous_value, new_value)
	else:
		return (*previous_value, new_value)


def str_or_list(value):
	return value if isinstance(value, str) else list(value)
