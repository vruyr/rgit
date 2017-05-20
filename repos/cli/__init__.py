import argparse
from .. import settings, constants
from . import registry, scan, status


async def main(args, *, loop=None):
	opts = _parse_args(args=args)
	config = await settings.load()
	handler = registry.get_command_handler(opts.command)
	if handler is None:
		print("external commands are not supported yet")
	await handler.execute(config)


def _parse_args(args=None):
	parser = argparse.ArgumentParser(
		prog=constants.SELF_NAME,
		description=None,
		epilog=None
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

	parser_help = subparsers.add_parser(
		"help",
		aliases=[],
		help="show help and exit",
	)

	opts = parser.parse_args(args)

	if opts.command is None:
		#TODO This is not a good solution
		parser.parse_args(["--help"])

	return opts
