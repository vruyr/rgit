import sys
assert sys.version_info[0] == 3 and sys.version_info[1] >= 6, sys.version_info
from . import cli as _cli
