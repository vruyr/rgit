from setuptools import setup, find_packages


# rm -rf _build && python3 -m pip install --target=_build/stuff . && python3 -m zipapp -o "_build/rgit-$(git describe)-$(python3 -c 'import sys; print(f"py{sys.version_info.major}{sys.version_info.minor}")').pyz" --main rgit.__main__:_ssmain -p "/usr/bin/env python3" _build/stuff


setup(
	name="rgit",
	version="0.0.0",
	description="",
	url="",
	license="UNLICENSED",
	packages=find_packages(
		".",
		include=[
			"rgit", "rgit.*",
		],
	),
	entry_points={
		"console_scripts": [
			"rgit = rgit.__main__:_ssmain",
		],
	},
	package_data={
	},
	install_requires=[
	]
)
