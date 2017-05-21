import os, json
from . import constants


#TODO Respect the options.
settings_file_path = os.path.join(
	os.path.expanduser("~"),
	"." + constants.SELF_NAME + ".json"
)


async def load():
	if not os.path.exists(settings_file_path):
		return None
	with open(settings_file_path, "r") as fo:
		config = json.load(fo)
	config["path"] = settings_file_path
	return config


async def save(opts, config):
	with open(settings_file_path, "w") as fo:
		json.dump(config, fo, indent="\t")
