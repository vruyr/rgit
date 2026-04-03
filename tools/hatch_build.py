import importlib.util, pathlib, re

# Load _gitcli.py directly to avoid importing the rgit package, which would trigger a dependency on pygit2.
_spec = importlib.util.spec_from_file_location("_gitcli", pathlib.Path(__file__).parent.parent / "rgit" / "_gitcli.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
git_describe = _mod.git_describe


def get_version():
	git_version = git_describe()
	if git_version is not None:
		pep440 = _git_describe_to_pep440(git_version)
		if pep440 is not None:
			return pep440
	raise RuntimeError("Could not determine version from git describe")


def _git_describe_to_pep440(git_describe):
	# v0.0.1 -> 0.0.1
	# v0.0.1-dirty -> 0.0.1+dirty
	# v0.0.1-3-g1a2b3c4 -> 0.0.1.dev3+g1a2b3c4
	# v0.0.1-3-g1a2b3c4-dirty -> 0.0.1.dev3+g1a2b3c4.dirty
	m = re.fullmatch(
		r"v?(?P<base>\d+\.\d+\.\d+)(?:-(?P<distance>\d+)-(?P<commit>g[0-9a-f]+))?(?:-(?P<dirty>dirty))?",
		git_describe,
	)
	if m is None:
		return None
	version = m.group("base")
	distance = m.group("distance")
	commit = m.group("commit")
	dirty = m.group("dirty")
	if distance:
		version += f".dev{distance}"
	local = []
	if commit:
		local.append(commit)
	if dirty:
		local.append(dirty)
	if local:
		version += "+" + ".".join(local)
	return version
