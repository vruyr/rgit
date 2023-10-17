import asyncio, subprocess, os, pathlib, re


async def status(repo, *args):
	def process_status_porcelain_v2_output(stdout):
		result = []
		if stdout:
			assert stdout[-1] == "\0"
			stdout = stdout[:-1].split("\0")
		while stdout:
			entry = stdout.pop(0)
			t, sp = entry[:2]
			status_line = entry[2:]
			assert sp == " "
			if t == "#":
				result.append(process_header(status_line))
			elif t == "?":
				result.append(process_untracked(status_line))
			elif t == "!":
				result.append(process_ignored(status_line))
			elif t == "1":
				result.append(process_ordinary(status_line))
			elif t == "2":
				result.append(process_rename(status_line, stdout.pop(0)))
			elif t == "u":
				result.append(process_unmerged(status_line))
			else:
				raise ValueError(f"unrecognized status line {entry}")
		return result

	def process_header(header):
		name, sep, value = header.partition(" ")
		assert sep == " "
		return ("header", name, value)

	def process_untracked(path):
		return ("untracked", path)

	def process_ignored(path):
		return ("ignored", path)

	def process_ordinary(status_line):
		return ("ordinary", *split_ordinary_or_first_part_of_renamed(status_line))

	def process_rename(status_line, path2):
		parts = split_ordinary_or_first_part_of_renamed(status_line)
		parts, status_line = parts[:-1], parts[-1]
		Xscore, sep, path1 = status_line.partition(" ")
		assert sep == " "
		return ("rename", *parts, Xscore, path1, path2)

	def process_unmerged(status_line):
		xy = status_line[:2]
		assert status_line[2] == " "
		status_line = status_line[3:]
		sub = status_line[:4]
		assert status_line[4] == " ", status_line
		status_line = status_line[5:]
		m1, sep, status_line = status_line.partition(" ")
		assert sep == " "
		m2, sep, status_line = status_line.partition(" ")
		assert sep == " "
		m3, sep, status_line = status_line.partition(" ")
		assert sep == " "
		mW, sep, status_line = status_line.partition(" ")
		assert sep == " "
		h1, sep, status_line = status_line.partition(" ")
		assert sep == " "
		h2, sep, status_line = status_line.partition(" ")
		assert sep == " "
		h3, sep, path = status_line.partition(" ")
		assert sep == " "
		return ("unmerged", xy, sub, m1, m2, m3, mW, h1, h2, h3, path)

	def split_ordinary_or_first_part_of_renamed(status_line):
		xy, status_line = status_line[:2], status_line[2:]
		assert status_line[0] == " "
		sub, status_line = status_line[1:5], status_line[5:]
		assert status_line[0] == " "
		status_line = status_line[1:]

		mH, sep, status_line = status_line.partition(" ")
		assert sep == " "
		mI, sep, status_line = status_line.partition(" ")
		assert sep == " "
		mW, sep, status_line = status_line.partition(" ")
		assert sep == " "
		hH, sep, status_line = status_line.partition(" ")
		assert sep == " "
		hI, sep, status_line = status_line.partition(" ")
		assert sep == " "

		return (xy, sub, mH, mI, mW, hH, hI, status_line)

	return process_status_porcelain_v2_output(
		await git(repo, "status", *args, "-z", "--porcelain=v2")
	)


async def get_remotes(repo):
	return (await git(repo, "remote")).splitlines()


async def list_config(repo, *, returncode_ok=None):
	text = await git(repo, "config", "--list", "--local", "--null",returncode_ok=returncode_ok)
	assert not text or text.endswith("\0"), repr(text)
	text = text[:-1]
	for v in text.split("\0"):
		yield v


async def get_config(repo, name, *, returncode_ok=None):
	text = await git(repo, "config", "--get-all", "--null", name, returncode_ok=returncode_ok)
	assert not text or text.endswith("\0"), repr(text)
	text = text[:-1]
	for v in text.split("\0"):
		yield v


async def get_config_prefix(repo, prefix, returncode_ok=None):
	prefix = prefix.rstrip(".")
	pattern = f"{re.escape(prefix)}\\..*"
	#TODO Switch to using `git config --null` and get rid of `walk_config_regex_output`.
	text = await git(repo, "config", "--get-regex", pattern, returncode_ok=returncode_ok)
	for x in walk_config_regex_output(text, f"{prefix}."):
		yield x


async def get_config_remote(repo, remote):
	async for x in get_config_prefix(repo, f"remote.{remote}"):
		yield x


async def get_config_branch(repo, branch, *, returncode_ok=None):
	async for x in get_config_prefix(repo, f"branch.{branch}", returncode_ok=returncode_ok):
		yield x


def split_config_key(key):
	#TODO:bug: Git allows dots (.) and dashes (-) in the section name, which makes the
	# output from `git config (--get|--list)` ambiguous. We will assume here that the section
	# and the name doesn't contain a dot (.).

	section, sep, subsection_and_name = key.partition(".")
	assert sep == "."
	subsection, sep, name = subsection_and_name.rpartition(".")
	if sep != ".":
		subsection = None

	return (section, subsection, name)


async def enumerate_remotes(repo, *, remotes=None):
	if remotes is None:
		remotes = await get_remotes(repo)
	for remote in remotes:
		remote_config = {}
		async for key, value in get_config_remote(repo, remote):
			remote_config.setdefault(key, []).append(value)
		yield (remote.strip(), remote_config)


async def is_bare(repo):
	stdout = await git(repo, "rev-parse", "--is-bare-repository")
	return {"true": True, "false": False}[stdout.strip()]


async def toplevel(repo):
	path = (await git(repo, "rev-parse", "--show-toplevel", worktree=None, cwd=None)).splitlines()
	if not path:
		return None
	assert len(path) == 1, repo
	return pathlib.Path(path[0])


WORKTREE = object()
TOPLEVEL = object()


async def git(
	repo,
	*args,
	stderr_ok=False, returncode_ok=None, stdin=None, worktree=None, cwd=WORKTREE
):
	if not isinstance(repo, pathlib.Path):
		repo = pathlib.Path(repo)

	if worktree is TOPLEVEL:
		worktree = await toplevel(repo)
	if worktree is None and repo.name == ".git":
		worktree = repo.parent
	if cwd is WORKTREE:
		cwd = worktree

	extra_args = [
		"--git-dir", os.fspath(repo)
	]
	if worktree is not None:
		extra_args.append("--work-tree")
		extra_args.append(os.fspath(worktree))
	if cwd is not None:
		extra_args.append("-C")
		extra_args.append(os.fspath(cwd))
	p = await asyncio.create_subprocess_exec(
		"git", *extra_args, *args,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
		env=update_env(
			GIT_TERMINAL_PROMPT="0"
		),
		encoding=None, # We want bytes
	)
	assert isinstance(stdin, (str, bytes, type(None)))
	if isinstance(stdin, str):
		stdin = stdin.encode("utf_8")
	stdout, stderr = await p.communicate(input=stdin)
	returncode_checker = None
	if callable(returncode_ok):
		returncode_checker = returncode_ok
	else:
		def assert_returncode(returncode):
			return returncode == (returncode_ok if returncode_ok is not None else 0)
		returncode_checker = assert_returncode
	assert returncode_checker(p.returncode), (repo, args, p.returncode, stderr)
	if not stderr_ok:
		assert not stderr, (repo, args, p.returncode, stderr)
	return stdout.decode("utf_8")


def update_env(*args, **kwargs):
	new_env = dict(os.environ.items())
	new_env.update(args)
	new_env.update(kwargs.items())
	return new_env


def walk_config_regex_output(text, prefix):
	for line in text.splitlines():
		key, value = line.split(" ", maxsplit=1)
		assert key.startswith(prefix), (prefix, key)
		key = key[len(prefix):].strip()
		value = value.strip()
		yield key, value


async def exists(gitdir):
	"""
	Returns a tuple (gitdir_exists, worktree_exists).
	"""

	if not isinstance(gitdir, pathlib.Path):
		gitdir = pathlib.Path(gitdir)

	if not gitdir.exists():
		return (False, False)

	config_file_path = gitdir / "config"

	#TODO Figure out a way to make git read config without specifying the config file path even in repositories with non-existent core.worktree config values.
	#TODO Only call "git" executable from a single place - it should be flexible enough to accommodate all the needs.

	p = await asyncio.create_subprocess_exec(
		"git", "config", "--file", os.fspath(config_file_path), "--get", "core.worktree",
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		stdin=subprocess.DEVNULL,
		env=update_env(
			GIT_TERMINAL_PROMPT="0"
		),
		encoding=None,
	)
	stdout, stderr = await p.communicate()
	assert not stderr, (stderr,)

	stdout = stdout.decode("UTF-8") #TODO Don't assume the encoding.
	stdout = stdout.rstrip("\r\n")

	if stdout:
		worktree = gitdir / pathlib.Path(stdout)
	elif gitdir.name == ".git":
		worktree = gitdir.parent
	else:
		worktree = None

	return (True, worktree.exists() if worktree is not None else None)


def run_sync(*args, cwd=None, encoding="UTF-8", capture_output=True, check=True, rstrip=True):
	p = subprocess.run(
		args,
		cwd=cwd if cwd is not None else pathlib.Path.home(),
		shell=False,
		check=check,
		capture_output=capture_output,
		encoding="UTF-8",
	)
	result = p.stdout
	if rstrip:
		result = result.rstrip()
	return result


class Repo(object):
	__slots__ = (
		"_gitdir",
		"_worktree",
	)
	def __init__(self, *, gitdir, worktree=WORKTREE) -> None:
		#TODO Convert this to an async function, switch to using the `git` function and embed it.
		self._gitdir = pathlib.Path(gitdir).resolve()
		if not self._gitdir.exists():
			raise ValueError("the passed gitdir doesn't exist", gitdir)

		if not self._gitdir.is_dir():
			try:
				self._gitdir = pathlib.Path(run_sync(
					"git", "--git-dir", self._gitdir.as_posix(), "rev-parse", "--git-dir"
				))
				if not self._gitdir.exists():
					raise ValueError("the determined gitdir path doesn't exist", self._gitdir)
			except subprocess.CalledProcessError as e:
				raise ValueError("failed to determine the actual path of passed gitdir", gitdir, p)

		if worktree is WORKTREE:
			if self._gitdir.name == ".git":
				self._worktree = self._gitdir.parent
			else:
				if "true" == run_sync("git", "--git-dir", self._gitdir.as_posix(), "config", "--get", "--bool", "core.bare"):
					self._worktree = None
				else:
					try:
						self._worktree = pathlib.Path(run_sync(
							"git", "--git-dir", self._gitdir.as_posix(), "rev-parse", "--show-toplevel"
						))
						if not self._worktree.exists():
							raise ValueError("the determined worktree path doesn't exist", self._worktree)
					except subprocess.CalledProcessError as e:
						raise ValueError("worktree is not passed and can not be determined", gitdir, worktree)
		else:
			self._worktree = pathlib.Path(worktree).resolve()
			if not self._worktree.exists():
				raise ValueError("the passed worktree doesn't exist")

	def __hash__(self) -> int:
		return (
			self.gitdir.as_posix(),
			self.worktree.as_posix() if self.worktree is not None else None
		).__hash__()

	def __eq__(self, __value: object) -> bool:
		return (self._gitdir, self._worktree).__eq__(
			(__value._gitdir, __value._worktree)
		)

	def __repr__(self) -> str:
		return f"<Repo gitdir={self._gitdir}, worktree={self._worktree}>"

	@property
	def gitdir(self):
		return self._gitdir

	@property
	def worktree(self):
		return (self._gitdir / self._worktree) if self._worktree else None

	def is_worktree_custom(self):
		return not (self._gitdir.name == ".git" and self._gitdir.parent == self._worktree)
