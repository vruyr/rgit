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
		self._config = None

	async def execute(self, *, opts, config):
		self._config = config
		repositories = set(config.repositories)
		counter = 0
		for starting_folder in opts.starting_folders:
			for root, dirs, files in os.walk(starting_folder, topdown=True):
				repo = None

				if ".git" in dirs or ".git" in files:
					repo = os.path.join(root, ".git")
				elif "refs" in dirs and "objects" in dirs and "HEAD" in files:
					repo = root

				if repo is not None:
					del dirs[:]
					# TODO This will report duplication repos if symlinks are used (e.g. folders in windows %USERPROFILE%).
					p = pathlib.Path(repo)
					if p not in repositories:
						for folder in self._config.scan_folders_ignore:
							if folder.parts == p.parts[:len(folder.parts)]:
								break
						else:
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
