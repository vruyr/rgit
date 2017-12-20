import os
import sys
import pathlib

from ..tools import set_status_msg, add_status_msg
from .registry import command


@command("scan")
class Scan(object):
	@classmethod
	def define_arguments(cls, parser):
		parser.add_argument(
			"starting_folders",
			metavar="PATH",
			nargs="+",
			help="starting folders from where to conduct the search"
		)

	@classmethod
	def short_description(cls):
		return "walk the filesystem to discover new repositories"

	def __init__(self):
		pass

	async def execute(self, *, opts, config):
		# TODO Implement finding repositories in working copies of other repositories without proper
		#      submodule references. Also implement outgoing commits and local modifications
		#      detection in submodules. Also commits in submodules committed to super-repo but not
		#      yet pushed in the submodule.
		repositories = set(config.repositories)
		counter = 0
		# TODO walk all the folders, not just the first one
		assert len(opts.starting_folders) == 1
		for root, dirs, files in os.walk(opts.starting_folders[0], topdown=True):
			repo = None

			if ".git" in dirs or ".git" in files:
				repo = os.path.join(root, ".git")
			elif "refs" in dirs and "objects" in dirs and "HEAD" in files:
				repo = root

			if repo is not None:
				del dirs[:]
				if pathlib.Path(repo) not in repositories:
					set_status_msg(None)
					await self.report_new_repo(repo)

			counter += 1
			if counter >= 1000:
				add_status_msg(".")
				counter = 0

		set_status_msg(None)

	async def report_new_repo(self, path):
		sys.stdout.write(path + "\n")
		sys.stdout.flush()
