import os
import sys
import pathlib

from ..tools import set_status_msg, add_status_msg
from .registry import command
from ..git import Repo


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
			"--ignore", "-i",
			dest="scan_folders_ignore",
			metavar="PATH",
			action="append",
			type=pathlib.Path,
			default=[],
			help="do not scan specified folders and their subfolders",
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
					repo = Repo(gitdir=(root / ".git"), worktree=root)
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
					repo = Repo(gitdir=root)
					if opts.skip_gitdirs:
						del dirs[:]

				if repo is None:
					continue

				if repo in repositories_found or repo in repositories_to_skip:
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
					await self.report_new_repo(repo)

		if opts.show_progress:
			set_status_msg(None)

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
