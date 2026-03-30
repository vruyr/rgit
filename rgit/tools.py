import sys, functools, os, pathlib, unicodedata, urllib.parse, re


# TODO Consider moving console output routines to a separate python package (can be named termtools).


BOX_ROW_HEADER_TOP = 0
BOX_ROW_HEADER_CONTENT = 1
BOX_ROW_HEADER_SEPARATOR = 2
BOX_ROW_HEADER_BOTTOM = 3
BOX_ROW_HEADER_BOTTOM_BODY_TOP = 4
BOX_ROW_BODY_TOP = 5
BOX_ROW_BODY_CONTENT = 6
BOX_ROW_BODY_SEPARATOR = 7
BOX_ROW_BODY_BOTTOM = 8

BOX_COL_LEFT = 0
BOX_COL_CONTENT = 1
BOX_COL_SEPARATOR = 2
BOX_COL_RIGHT = 3

box_with_header = [
	[
		"┏━┳┓",
		"┃h┃┃",
		"┣━╋┫",
		"┗━┻┛",
		"┡━╇┩",
		"┌─┬┐",
		"│b││",
		"├─┼┤",
		"└─┴┘",
	],
	[
		"┌─┬┐",
		"│h││",
		"├─┼┤",
		"└─┴┘",
		"╞═╪╡",
		"┌─┬┐",
		"│b││",
		"├─┼┤",
		"└─┴┘",
	],
][1]


def combine_box_symbols(box, first, second):
	if first is None:
		return second
	elif second == " ":
		return first
	elif first == second:
		return first
	elif first == box[BOX_ROW_HEADER_TOP][BOX_COL_LEFT] and second == box[BOX_ROW_HEADER_BOTTOM][BOX_COL_LEFT]:
		return box[BOX_ROW_HEADER_SEPARATOR][BOX_COL_LEFT]
	elif first == box[BOX_ROW_HEADER_TOP][BOX_COL_CONTENT] and second == box[BOX_ROW_HEADER_BOTTOM][BOX_COL_RIGHT]:
		return box[BOX_ROW_HEADER_BOTTOM][BOX_COL_SEPARATOR]
	elif first == box[BOX_ROW_HEADER_TOP][BOX_COL_SEPARATOR] and second == box[BOX_ROW_HEADER_BOTTOM][BOX_COL_RIGHT]:
		return box[BOX_ROW_HEADER_SEPARATOR][BOX_COL_SEPARATOR]
	elif first == box[BOX_ROW_HEADER_TOP][BOX_COL_SEPARATOR] and second == box[BOX_ROW_HEADER_BOTTOM][BOX_COL_CONTENT]:
		return first
	elif first == box[BOX_ROW_HEADER_TOP][BOX_COL_RIGHT] and second == box[BOX_ROW_HEADER_BOTTOM][BOX_COL_RIGHT]:
		return box[BOX_ROW_HEADER_SEPARATOR][BOX_COL_RIGHT]
	elif first == box[BOX_ROW_HEADER_TOP][BOX_COL_RIGHT] and second == box[BOX_ROW_HEADER_BOTTOM][BOX_COL_CONTENT]:
		return box[BOX_ROW_HEADER_TOP][BOX_COL_SEPARATOR]

	elif first == box[BOX_ROW_BODY_TOP][BOX_COL_LEFT] and second == box[BOX_ROW_BODY_BOTTOM][BOX_COL_LEFT]:
		return box[BOX_ROW_BODY_SEPARATOR][BOX_COL_LEFT]
	elif first == box[BOX_ROW_BODY_TOP][BOX_COL_CONTENT] and second == box[BOX_ROW_BODY_BOTTOM][BOX_COL_RIGHT]:
		return box[BOX_ROW_BODY_BOTTOM][BOX_COL_SEPARATOR]
	elif first == box[BOX_ROW_BODY_TOP][BOX_COL_SEPARATOR] and second == box[BOX_ROW_BODY_BOTTOM][BOX_COL_RIGHT]:
		return box[BOX_ROW_BODY_SEPARATOR][BOX_COL_SEPARATOR]
	elif first == box[BOX_ROW_BODY_TOP][BOX_COL_SEPARATOR] and second == box[BOX_ROW_BODY_BOTTOM][BOX_COL_CONTENT]:
		return first
	elif first == box[BOX_ROW_BODY_TOP][BOX_COL_RIGHT] and second == box[BOX_ROW_BODY_BOTTOM][BOX_COL_RIGHT]:
		return box[BOX_ROW_BODY_SEPARATOR][BOX_COL_RIGHT]
	elif first == box[BOX_ROW_BODY_TOP][BOX_COL_RIGHT] and second == box[BOX_ROW_BODY_BOTTOM][BOX_COL_CONTENT]:
		return box[BOX_ROW_BODY_TOP][BOX_COL_SEPARATOR]

	else:
		raise NotImplementedError(f"{(first, second)}")


def cell_filter_ljust(*, row, column, value, width, fill):
	return str(value).ljust(width, fill)


def draw_table(rows, *, fo,
	# Optional Parameters
	title=None,
	box=box_with_header,
	has_header=False,
	cell_filter=cell_filter_ljust,
	draw_separators_between_lines=False,
):
	widths = []
	for row_num, row in enumerate(rows):
		widths.extend([0] * (len(row) - len(widths)))
		for c, v in enumerate(row):
			widths[c] = max(widths[c], len(cell_filter(
				row=row_num, column=c, value=v, width=0, fill=" "
			)))

	template_row = None
	row_num = None

	def render_row(row, fill=" "):
		nonlocal box, template_row, row_num, cell_filter, widths
		template = box[template_row]
		_cell_filter = cell_filter
		if row is None:
			_cell_filter = cell_filter_ljust
			fill = box[template_row][BOX_COL_CONTENT]
			row = [""] * len(widths)
		result = ""
		result += template[BOX_COL_LEFT]
		result += template[BOX_COL_SEPARATOR].join(
			(
				_cell_filter(
					row=row_num, column=i, value=value, width=widths[i], fill=fill
				)[:widths[i]]
			) for i, value in enumerate(row)
		)
		result += template[BOX_COL_RIGHT]
		return result

	if title is not None:
		assert isinstance(title, str)
		template_row = BOX_ROW_HEADER_TOP if has_header else BOX_ROW_BODY_TOP
		fo.write(box[template_row][BOX_COL_LEFT])
		fo.write(box[template_row][BOX_COL_CONTENT] * len(title))
		fo.write(box[template_row][BOX_COL_RIGHT])
		fo.write("\n")
		template_row = BOX_ROW_HEADER_CONTENT if has_header else BOX_ROW_BODY_CONTENT
		fo.write(box[template_row][BOX_COL_LEFT])
		fo.write(title)
		fo.write(box[template_row][BOX_COL_RIGHT])
		fo.write("\n")

	row_num = None
	template_row = BOX_ROW_HEADER_TOP if has_header else BOX_ROW_BODY_TOP
	first_line = render_row(None)

	if title is not None:
		first_line_patch = ""
		template_row = BOX_ROW_HEADER_BOTTOM if has_header else BOX_ROW_BODY_BOTTOM
		first_line_patch += box[template_row][BOX_COL_LEFT]
		first_line_patch += box[template_row][BOX_COL_CONTENT] * len(title)
		first_line_patch += box[template_row][BOX_COL_RIGHT]
		new_first_line = ""
		for i, c in enumerate(first_line_patch):
			new_first_line += combine_box_symbols(box, first_line[i] if i < len(first_line) else None, c)
		new_first_line += first_line[len(new_first_line):]
		first_line = new_first_line

	fo.write(first_line)
	fo.write("\n")

	for row_num, row in enumerate(rows):
		row = row + ([""] * (len(widths) - len(row)))

		template_row = BOX_ROW_BODY_CONTENT
		if row_num == 0 and has_header:
			template_row = BOX_ROW_HEADER_CONTENT

		fo.write(render_row(row))
		fo.write("\n")

		template_row = None
		if row_num == 0 and has_header:
			template_row = BOX_ROW_HEADER_BOTTOM_BODY_TOP
		elif draw_separators_between_lines:
			template_row = BOX_ROW_BODY_SEPARATOR
		if template_row is not None:
			fo.write(render_row(None))
			fo.write("\n")

	template_row = BOX_ROW_BODY_BOTTOM
	fo.write(render_row(None))
	fo.write("\n")
	fo.flush()


class ProgressDisplay:
	"""
	A multi-line, in-place progress display written to stderr.

	Each slot is a single character appended via `add()` and optionally
	replaced later via `update()`. On every change the display is redrawn
	in place: the cursor is repositioned using ANSI escape codes and the
	whole block is erased and reprinted.

	The terminal handles line wrapping naturally. The number of lines
	occupied is derived from `ceil(display_width / terminal_width)`, where
	display width is measured in cells via `unicodedata.east_asian_width`
	so wide characters (CJK, full-width forms, most emoji) count as two
	cells. Some terminals (e.g. Apple Terminal) may not render wide
	characters correctly.

	If the terminal width cannot be determined, cursor manipulation is
	skipped and progress characters are written as a plain character
	stream instead.
	"""

	def __init__(self, *, fo=sys.stderr):
		self._fo = fo
		self._chars = []
		self._rendered_lines = 0
		try:
			self._width = os.get_terminal_size(fo.fileno()).columns
		except OSError:
			self._width = None  # fall back to plain stream; see also: SIGWINCH
		if self._width <= 0:
			self._width = None

	def add(self, char):
		"""Append a new character slot, re-render, and return its index."""
		idx = len(self._chars)
		self._chars.append(char)
		if self._width is None:
			self._fo.write(char)
			self._fo.flush()
		else:
			self._render()
		return idx

	def update(self, idx, char):
		"""Replace the character at *idx* and re-render."""
		self._chars[idx] = char
		if self._width is not None:
			self._render()

	def clear(self):
		"""Erase the progress display entirely."""
		if self._width is None:
			self._fo.write("\n")
			self._fo.flush()
		else:
			self._erase()
		self._chars = []
		self._rendered_lines = 0

	# -- internals --

	@staticmethod
	def _char_width(c):
		eaw = unicodedata.east_asian_width(c)
		return 2 if eaw in ("W", "F") else 1

	def _render(self):
		content = "".join(self._chars)
		display_w = sum(self._char_width(c) for c in content)
		new_lines = max(1, (display_w + self._width - 1) // self._width)
		if self._rendered_lines > 0:
			self._fo.write(f"\033[{self._rendered_lines}A")
		self._fo.write("\r\033[J")
		self._fo.write(content)
		self._fo.write("\r\n")
		self._fo.flush()
		self._rendered_lines = new_lines

	def _erase(self):
		if self._rendered_lines == 0:
			return
		self._fo.write(f"\033[{self._rendered_lines}A")
		self._fo.write("\r\033[J")
		self._fo.flush()


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


def url_starts_with(url, prefix):
	url_parts = urllib.parse.urlsplit(url)
	prefix_parts = urllib.parse.urlsplit(prefix)
	assert len(url_parts) == 5, url_parts
	assert len(prefix_parts) == 5, prefix_parts
	# If prefix has no scheme and no netloc, treat it as a path
	if not prefix_parts.scheme and not prefix_parts.netloc:
		if url_parts.scheme or url_parts.netloc:
			# The prefix is a path but the url has a scheme or netloc, so it cannot match.
			return False
		url_path = pathlib.PurePosixPath(url_parts.path)
		prefix_path = pathlib.PurePosixPath(prefix_parts.path)
		if prefix_path.is_absolute() != url_path.is_absolute():
			return False
		prefix_path_parts = prefix_path.parts
		url_path_parts = url_path.parts
		if len(prefix_path_parts) > len(url_path_parts):
			return False
		return prefix_path_parts == url_path_parts[:len(prefix_path_parts)]
	if prefix_parts.scheme != url_parts.scheme:
		return False
	if prefix_parts.netloc != url_parts.netloc:
		return prefix_parts[1:] == ("", "", "", "")
	if prefix_parts.path or url_parts.path:
		url_path = pathlib.PurePosixPath(url_parts.path)
		prefix_path = pathlib.PurePosixPath(prefix_parts.path)
		if prefix_path.is_absolute() != url_path.is_absolute():
			return False
		prefix_path_parts = prefix_path.parts
		url_path_parts = url_path.parts
		if len(prefix_path_parts) > len(url_path_parts):
			return False
		if prefix_path_parts != url_path_parts[:len(prefix_path_parts)]:
			return False
	if prefix_parts.query and prefix_parts.query != url_parts.query:
		return False
	if prefix_parts.fragment and prefix_parts.fragment != url_parts.fragment:
		return False
	return True


def gen_sort_index(values, sort_order):
	values_len = len(values)
	sort_first, sort_last = sort_order
	sort_last_len = len(sort_last)
	sort_order_dict = {}
	sort_order_dict.update({e: i for i, e in enumerate(sort_first)})
	sort_order_dict.update({e: (values_len - sort_last_len + i) for i, e in enumerate(sort_last)})
	sort_index = list(range(values_len))
	sort_order_for_unspecified = len(sort_first)
	def sortkey(i):
		column = values[i]
		return (sort_order_dict.get(column, sort_order_for_unspecified), column)
	sort_index = sorted(sort_index, key=sortkey)
	return sort_index


def strict_int(x):
	assert re.match(r"^\d+$", x), repr(x)
	return int(x)


def is_path_in(parent, child):
	return child.parts[:len(parent.parts)] == parent.parts


def path_relative_to_or_unchanged(root_path, target_path):
	try:
		return pathlib.Path(target_path).relative_to(root_path)
	except ValueError:
		return target_path
