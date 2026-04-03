# Publishing to PyPI


## Prerequisites

- A git tag matching the version to publish.
- A PyPI API token.


## Steps

1. Tag the release:

   ```
   git tag -a -m vM.N.P vM.N.P
   ```

2. Clean the working tree:

   ```
   git clean -xdf
   ```

3. Build:

   ```
   uv build
   ```

4. Publish:

   ```
   uv publish --token="$(<path/to/pypi-api-token)"
   ```

5. Push the branch and tag:

   ```
   git push gh main:main vM.N.P
   ```


## Notes

- The tag must be created before building because `git describe` derives the package version from it.
- `git clean -xdf` removes all untracked and ignored files to ensure a clean build.
- PyPI rejects versions with local segments (the `+` in PEP 440), so a dirty or untagged build cannot be published accidentally.
