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
		#TODO fix the config
		config_path_dir = pathlib.Path(config["path"]).absolute().parent
		repositories = set(config_path_dir / repo for repo in config["repositories"])
		counter = 0
		#TODO walk all the folders, not just the first one
		for root, dirs, files in os.walk(opts.starting_folders[0], topdown=True):
			if ".git" in dirs or ".git" in files or ("refs" in dirs and "objects" in dirs and "HEAD" in files):
				del dirs[:]
				if pathlib.Path(root) not in repositories:
					set_status_msg(None)
					await self.report_new_repo(root)

			counter += 1
			if counter >= 1000:
				add_status_msg(".")
				counter = 0

		set_status_msg(None)

	async def report_new_repo(self, path):
		sys.stdout.write(path + "\n")


