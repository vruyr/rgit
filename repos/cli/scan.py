from .registry import command


@command("scan")
class Scan(object):
	@classmethod
	def define_arguments(cls, parser):
		pass

	@classmethod
	def short_description(cls):
		return "walk the filesystem to discover new repositories"

	def __init__(self):
		pass

	async def execute(self):
		print("scan command is not implemented")
