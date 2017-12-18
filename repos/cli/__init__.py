import argparse, pathlib
from .. import configuration, constants
from . import registry, scan, status, ignored


async def main(args, *, loop=None):
	opts = _parse_args(args=args)
	config_path = opts.config_path
	if config_path is None:
		config_path = (pathlib.Path.home() / ("." + constants.SELF_NAME + ".json"))
	config = await configuration.load(config_file_path=pathlib.Path(config_path))
	handler = registry.get_command_handler(opts.command)
	if handler is not None:
		handler_instance = handler()
		await handler_instance.execute(opts=opts, config=config)
	else:
		print("external commands are not supported yet")


def _parse_args(args=None):
	parser = argparse.ArgumentParser(
		prog=constants.SELF_NAME,
		description=None,
		epilog=None
	)

	parser.add_argument(
		"--config-path",
		dest="config_path",
		action="store",
		metavar="PATH",
		default=None,
	)

	subparsers = parser.add_subparsers(
		title=None,
		dest="command",
		metavar="COMMAND",
	)

	for name, aliases, handler in registry.enumerate_command_handlers():
		handler.define_arguments(subparsers.add_parser(
			name,
			aliases=aliases,
			help=handler.short_description()
		))

	opts = parser.parse_args(args)

	return opts
