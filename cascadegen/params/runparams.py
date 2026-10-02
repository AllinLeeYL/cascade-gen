import atexit
import os
import shutil
import tempfile

# Scratch directory for the intermediate ELFs and spike command files.
# Created by the process that first imports this module and removed when it exits.
PATH_TO_TMP = tempfile.mkdtemp(prefix='cascadegen-')
_TMP_OWNER_PID = os.getpid()
@atexit.register
def _remove_tmp():
    if os.getpid() == _TMP_OWNER_PID:
        shutil.rmtree(PATH_TO_TMP, ignore_errors=True)

DO_ASSERT = True
DO_EXPENSIVE_ASSERT = False # More expensive assertions

NO_REMOVE_TMPFILES = False # Used for debugging purposes.

# Master switch for the C extension. When True, eligible instructions are
# packed as a 16-bit compressed encoding plus c.nop into their 4-byte slot.
# This is enabled implicitly for designs whose marchflags include 'c'.
USE_COMPRESSED = True
