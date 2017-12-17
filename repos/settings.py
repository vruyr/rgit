import os, json, pathlib
from . import constants


# TODO Respect the options.
settings_file_path = pathlib.Path.home() / ("." + constants.SELF_NAME + ".json")


async def load():
	if not settings_file_path.exists():
		return None
	with settings_file_path.open("r") as fo:
		config = json.load(fo)
	config["path"] = os.fspath(settings_file_path)
	return config


async def save(opts, config):
	with settings_file_path.open("w") as fo:
		json.dump(config, fo, indent="\t")
