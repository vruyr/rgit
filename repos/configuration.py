import json, pathlib


async def load(*, config_file_path):
	result = FileBasedConfiguration(config_file_path)
	await result._load() # pylint: disable=protected-access
	return result


class FileBasedConfiguration(object):
	def __init__(self, path):
		self._path = pathlib.Path(path)
		self._content = {}

	async def _load(self):
		if not self._path.exists():
			return
		with self._path.open("r") as fo:
			config = json.load(fo)
		# TODO Validate loaded config against a schema
		self._content = config

	async def _save(self):
		with self._path.open("w") as fo:
			json.dump(self._content, fo, indent="\t")

	@property
	def basedir(self):
		return self._path.absolute().parent

	@property
	def repositories(self):
		for r in self._content.get("repositories", []):
			yield self.basedir / r

	@property
	def destination_remotes(self):
		for r in self._content.get("destination.remotes", []):
			yield r

	@property
	def destination_folders(self):
		for f in self._content.get("destination.folders", []):
			yield self.basedir / f

	@property
	def ignore_remotes(self):
		for r in self._content.get("ignore.remotes", []):
			yield r

	@property
	def ignore_folders(self):
		for f in self._content.get("ignore.folders", []):
			yield self.basedir / f
