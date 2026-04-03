import importlib.metadata, sys
from .registry import command
from .. import constants
from .._gitcli import git_describe


@command("version")
class Version(object):
	@classmethod
	def define_arguments(cls, parser):
		pass

	@classmethod
	def short_description(cls):
		return "print version"

	def __init__(self):
		pass

	@classmethod
	def get_version(cls):
		if git_version := git_describe():
			return git_version
		else:
			try:
				return importlib.metadata.version(constants.SELF_NAME)
			except importlib.metadata.PackageNotFoundError:
				return "unknown"


	async def execute(self, *, opts, config):
		sys.stdout.write(self.get_version() + "\n")
