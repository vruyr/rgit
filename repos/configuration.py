import os, json, pathlib
from . import constants


# TODO Make config file path configurable with cli parameters.
config_file_path = pathlib.Path.home() / ("." + constants.SELF_NAME + ".json")


async def load():
	if not config_file_path.exists():
		return None
	with config_file_path.open("r") as fo:
		config = json.load(fo)
	config["path"] = os.fspath(config_file_path)
	# TODO Return a typed object instead of a generic dictionary.
	return config


async def save(opts, config):
	with config_file_path.open("w") as fo:
		json.dump(config, fo, indent="\t")
