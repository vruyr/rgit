import pathlib


def get_toplevel():
	return pathlib.Path(__file__).parent.parent
