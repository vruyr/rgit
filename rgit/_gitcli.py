import asyncio, os, pathlib, subprocess

_git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


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


async def run_async(*args, cwd=None, stdin=None, stderr_ok=False, returncode_ok=None):
	p = await asyncio.create_subprocess_exec(
		*args,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
		env=_git_env,
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
	assert returncode_checker(p.returncode), (args, p.returncode, stderr)
	if not stderr_ok:
		assert not stderr, (args, p.returncode, stderr)
	return stdout.decode("utf_8")


def git_describe(cwd=None):
	if cwd is None:
		cwd = _find_project_root()
	if cwd is None:
		return None
	try:
		return run_sync("git", "describe", "--dirty", cwd=cwd)
	except (subprocess.CalledProcessError, FileNotFoundError):
		return None


def _find_project_root():
	path = pathlib.Path(__file__).parent
	while path != path.parent:
		if (path / "pyproject.toml").exists():
			return path
		path = path.parent
	return None
