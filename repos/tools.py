import functools
import sys


# TODO Consider moving this to a separate python package (can be named termtools).


box_with_header = [
	[
		"┏━┳┓",
		"┃h┃┃",
		"┡━╇┩",
		"┌─┬┐",
		"│b││",
		"├─┼┤",
		"└─┴┘",
	],
	[
		"┌─┬┐",
		"│h││",
		"╞═╪╡",
		"┌─┬┐",
		"│b││",
		"├─┼┤",
		"└─┴┘",
	],
][1]


def cell_filter_ljust(*, row, column, value, width, fill):
	return str(value).ljust(width, fill)


def draw_table(
	rows, *, fo, box=box_with_header, has_header=False, cell_filter=cell_filter_ljust,
	draw_separators_between_lines=False
):
	widths = []
	for r, row in enumerate(rows):
		widths.extend([0] * (len(row) - len(widths)))
		for c, v in enumerate(row):
			widths[c] = max(widths[c], len(cell_filter(
				row=r, column=c, value=v, width=0, fill=" "
			)))

	template_row = 0 if has_header else 3
	draw_line(
		fo,
		box[template_row],
		(("", w, box[template_row][1]) for w in widths),
		functools.partial(cell_filter_ljust, row=0)
	)
	for r, row in enumerate(rows):
		row = row + ([""] * (len(widths) - len(row)))
		template_row = 4
		if r == 0 and has_header:
			template_row = 1
		draw_line(
			fo,
			box[template_row],
			((value, widths[i], " ") for i, value in enumerate(row)),
			functools.partial(cell_filter, row=r)
		)
		template_row = 5 if draw_separators_between_lines else None
		if r == len(rows) - 1:
			template_row = 6
		elif r == 0 and has_header:
			template_row = 2
		if template_row is not None:
			draw_line(
				fo,
				box[template_row],
				(("", w, box[template_row][1]) for w in widths),
				functools.partial(cell_filter_ljust, row=r)
			)
	fo.flush()


def draw_line(fo, template, columns, cell_filter):
	"""
	:param fo: file object to write to
	:param template: box drawing template line
	:param columns: sequence of 3-tuples - value, width, fill
	:param cell_filter: function
	:return: None
	"""
	fo.write(template[0])
	fo.write(template[2].join(
		(
			cell_filter(column=i, value=value, width=width, fill=fill)[:width]
		) for i, (value, width, fill) in enumerate(columns)
	))
	fo.write(template[3])
	fo.write("\n")


def set_status_msg(msg, *, fo=sys.stderr):
	max_length = 157
	fo.write("\r\x1b[2K")
	if msg:
		fo.write(" ")
		fo.write(msg[:max_length])
		fo.write("\r")
	fo.flush()


def add_status_msg(msg, *, fo=sys.stderr):
	fo.write(msg)
	fo.flush()
