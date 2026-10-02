# SPDX-License-Identifier: GPL-3.0-only

# Checks that the generated programs did not change. The reference hashes were
# produced by the original Cascade code (commit 782e0e7 of cascade-meta), with
# only the ELF entry point changed from 0 to the boot address.
# If a change to the generator is intended, regenerate tests/golden.json.

import hashlib
import json
import os
import shutil

import pytest

from cascadegen import spike
from cascadegen.generate import Descriptor, generate
from cascadegen.target import get_target

GOLDEN = json.load(open(os.path.join(os.path.dirname(__file__), 'golden.json')))

pytestmark = pytest.mark.skipif(shutil.which('spike') is None, reason="spike not found")


@pytest.mark.parametrize('case', sorted(GOLDEN))
def test_golden(case, tmp_path):
    design, seed = case.rsplit('_', 1)
    seed = int(seed)
    if not spike.is_spikespeed_calibrated():
        spike.calibrate_spikespeed()
    desc = Descriptor(seed, memsize=40000 + seed*37000, num_bbs=20 + seed*7, authorize_privileges=seed % 2 == 1)
    elf_path = tmp_path / f"{case}.elf"
    generate(get_target(design), desc, str(elf_path))
    assert hashlib.sha256(elf_path.read_bytes()).hexdigest() == GOLDEN[case]
