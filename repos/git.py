import asyncio, subprocess, os


async def status(repo, *args):
	def process_status_porcelain_v2_output(stdout):
		result = []
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


async def get_config_remote(repo, remote):
	text = await git(repo, "config", "--get-regex", f"remote\\.{remote}\\..*")
	for x in walk_config_regex_output(text, f"remote.{remote}."):
		yield x


async def get_config_branch(repo, branch, *, returncode_ok=None):
	text = await git(
		repo, "config", "--get-regex", f"branch\\.{branch}\\..*", returncode_ok=returncode_ok
	)
	for x in walk_config_regex_output(text, f"branch.{branch}."):
		yield x


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


async def git(repo, *args, stderr_ok=False, returncode_ok=None, stdin=None):
	p = await asyncio.create_subprocess_exec(
		"git", "-C", os.fspath(repo), *args,
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
	assert returncode_checker(p.returncode), (repo, p.returncode, stderr)
	if not stderr_ok:
		assert not stderr, (repo, p.returncode, stderr)
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
