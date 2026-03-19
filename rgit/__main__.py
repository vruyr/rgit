import sys, asyncio
from . import cli


def _smain(args):
	asyncio.run(cli.main(args))


def _ssmain():
	try:
		sys.exit(_smain(sys.argv[1:]))
	except KeyboardInterrupt:
		sys.stderr.write("\n")


if __name__ == "__main__":
	_ssmain()
