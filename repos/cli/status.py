from .registry import command


@command("status")
class Status(object):
	@classmethod
	def define_arguments(cls, parser):
		pass

	@classmethod
	def short_description(cls):
		return "display statuses for all repositories"

	def __init__(self):
		pass

	async def execute(self):
		print("status command is not implemented")
