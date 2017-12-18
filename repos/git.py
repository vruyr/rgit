import asyncio, subprocess, os


async def get_remotes(repo):
	return (await git(repo, "remote")).splitlines()


async def get_config_remote(repo, remote):
	text = await git(repo, "config", "--get-regex", f"remote\\.{remote}\\..*")
	for x in walk_config_regex_output(text, f"remote.{remote}."):
		yield x


async def get_config_branch(repo, branch, *, returncode_ok=False):
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


async def git(repo, *args, stderr_ok=False, returncode_ok=False):
	p = await asyncio.create_subprocess_exec(
		"git", "-C", os.fspath(repo), *args,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		stdin=subprocess.DEVNULL,
		env=update_env(
			GIT_TERMINAL_PROMPT="0"
		)
	)
	stdout, stderr = await p.communicate()
	if not returncode_ok:
		assert p.returncode == 0, (repo, p.returncode, stderr)
	if not stderr_ok:
		assert not stderr, (repo, p.returncode, stderr)
	return stdout.decode()


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
