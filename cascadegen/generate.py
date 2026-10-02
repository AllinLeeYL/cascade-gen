# SPDX-License-Identifier: GPL-3.0-only

# Generation of a single Cascade program, from a descriptor to an ELF file.
# This replaces the program-generation half of Cascade's fuzzfromdescriptor.py;
# the generation steps themselves are unchanged.

from dataclasses import dataclass
import itertools
import random
import shutil

from cascadegen.core.basicblock import gen_basicblocks
from cascadegen.core.finalblock import htif_block_offset, HTIF_TOHOST_OFFSET
from cascadegen.core.fuzzerstate import FuzzerState
from cascadegen.core.genelf import gen_elf_from_bbs
from cascadegen.core.spikeresolution import spike_resolution
from cascadegen.core.util import IntRegIndivState
from cascadegen.params.fuzzparams import PROBA_AUTHORIZE_PRIVILEGES
from cascadegen.target import Target

# Bounds of the random program descriptors, as in Cascade.
LOG2_MEMSIZE_UPPERBOUND = 20
NUM_MAX_BBS_UPPERBOUND = 100


@dataclass(frozen=True)
class Descriptor:
    """Everything that determines a generated program, together with the target."""
    seed: int
    memsize: int
    num_bbs: int
    authorize_privileges: bool
    max_instrs: int = None
    no_dependency_bias: bool = False


def sample_descriptor(seed: int, memsize: int = None, num_bbs: int = None, privileges: bool = None, max_instrs: int = None, no_dependency_bias: bool = False) -> Descriptor:
    """Draws the unset parameters as Cascade's gen_new_test_instance does, from an RNG seeded with `seed`.
    `privileges` is True/False to force privilege-level changes on/off, or None to enable them with Cascade's probability."""
    random.seed(seed)
    if memsize is None:
        memsize = random.randrange(1 << 14, 1 << LOG2_MEMSIZE_UPPERBOUND)
    if num_bbs is None:
        num_bbs = random.randrange(20, NUM_MAX_BBS_UPPERBOUND)
    if privileges is None:
        privileges = random.random() < PROBA_AUTHORIZE_PRIVILEGES
    return Descriptor(seed, memsize, num_bbs, privileges, max_instrs, no_dependency_bias)


def generate(target: Target, desc: Descriptor, elf_path: str, check: bool = False) -> dict:
    """Generates the program described by `desc` for `target` and writes it to `elf_path`.
    If `check`, re-runs the final ELF on spike and checks its PC trace and register values.
    Returns the program metadata."""
    random.seed(desc.seed)
    fuzzerstate = FuzzerState(target, desc.memsize, desc.seed, desc.num_bbs, desc.authorize_privileges, desc.max_instrs, desc.no_dependency_bias)
    gen_basicblocks(fuzzerstate)
    expected_intregs, expected_fpregs = spike_resolution(fuzzerstate, check)
    tmp_elf_path = gen_elf_from_bbs(fuzzerstate, False, 'rtl', fuzzerstate.instance_to_str(), fuzzerstate.design_base_addr)
    shutil.move(tmp_elf_path, elf_path)
    return _metadata(fuzzerstate, desc, expected_intregs, expected_fpregs)


def _metadata(fuzzerstate, desc: Descriptor, expected_intregs: list, expected_fpregs: list) -> dict:
    num_instrs = len(fuzzerstate.final_bb) + sum(len(bb) for bb in fuzzerstate.instr_objs_seq)
    # As in Cascade's RTL check: only the registers that are not transient
    # (FREE or CONSUMED) at the end of the program have a reliable expected value.
    intregs = {
        f"x{reg_id}": hex(expected_intregs[reg_id-1])
        for reg_id in range(1, fuzzerstate.num_pickable_regs)
        if fuzzerstate.intregpickstate.get_regstate(reg_id) in (IntRegIndivState.FREE, IntRegIndivState.CONSUMED)
    }
    fpregs = {f"f{reg_id}": hex(val) for reg_id, val in enumerate(expected_fpregs)} if fuzzerstate.design_has_fpu else {}
    htif = {}
    if fuzzerstate.target.htif:
        htif['tohost_addr'] = hex(fuzzerstate.design_base_addr + htif_block_offset(desc.memsize) + HTIF_TOHOST_OFFSET)
    return {
        'seed': desc.seed,
        'memsize': desc.memsize,
        'num_bbs': desc.num_bbs,
        'authorize_privileges': desc.authorize_privileges,
        'max_instrs': desc.max_instrs,
        'no_dependency_bias': desc.no_dependency_bias,
        'target': {k: hex(v) if isinstance(v, int) and not isinstance(v, bool) else v for k, v in fuzzerstate.target.to_dict().items()},
        'entry_addr': hex(fuzzerstate.design_base_addr + fuzzerstate.bb_start_addr_seq[0]),
        'final_block_addr': hex(fuzzerstate.design_base_addr + fuzzerstate.final_bb_base_addr),
        **htif,
        'num_instrs': num_instrs,
        'num_executed_instrs': len(list(itertools.chain.from_iterable(fuzzerstate.instr_objs_seq))),
        'expected_intregs': intregs,
        'expected_fpregs': fpregs,
    }
