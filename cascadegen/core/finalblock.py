# Copyright 2023 Flavien Solt, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

# This module defines the final block.

from cascadegen.params.runparams import DO_ASSERT
from cascadegen.rv.csrids import CSR_IDS
from cascadegen.params.fuzzparams import RDEP_MASK_REGISTER_ID, MAX_NUM_PICKABLE_REGS, MAX_NUM_PICKABLE_FLOATING_REGS, FPU_ENDIS_REGISTER_ID
from cascadegen.core.privilegestate import PrivilegeStateEnum
from cascadegen.rv.asmutil import li_into_reg
from cascadegen.core.cfinstructionclasses import ImmRdInstruction, RegImmInstruction, IntStoreInstruction, FloatStoreInstruction, JALInstruction, SpecialInstruction, CSRRegInstruction

def get_finalblock_max_size():
    return (10 + 2*MAX_NUM_PICKABLE_REGS + 2*MAX_NUM_PICKABLE_FLOATING_REGS - 1) * 4

# HTIF mode (not in Cascade): instead of Cascade's per-design testbench addresses, the
# final block dumps the registers to, and stops through, a block of memory placed just
# after the program, as the HTIF protocol of spike/Chipyard/riscv-tests expects.
# Offsets inside that block. tohost and fromhost are 64-byte aligned, as in riscv-tests.
HTIF_TOHOST_OFFSET = 0x0
HTIF_FROMHOST_OFFSET = 0x40
HTIF_REGDUMP_OFFSET = 0x80
HTIF_BLOCK_SIZE = 0x100

# @return the offset of the HTIF block from the boot address, after the program memory.
def htif_block_offset(memsize: int) -> int:
    return (memsize + 0x3f) & ~0x3f

# auipc+addi that puts the absolute address of `target_offset` into `rd`, both offsets
# being relative to the boot address. Unlike lui+addi, it needs no sign-extension
# handling for addresses above 0x80000000 on RV64.
def _pcrel_into_reg(rd: int, target_offset: int, instr_offset: int, is_design_64bit: bool):
    auipc_imm, addi_imm = li_into_reg(target_offset - instr_offset)
    return [
        ImmRdInstruction("auipc", rd, auipc_imm, is_design_64bit),
        RegImmInstruction("addi", rd, rd, addi_imm, is_design_64bit)
    ]

# We must instantiate it in the end because we must know whether we have the privileges to turn on the FPU.
# Returns the instruction objects of the tail basic block
def finalblock(fuzzerstate):
    target = fuzzerstate.target
    stopsig_addr = target.stop_addr
    regdump_addr = target.regdump_addr

    if DO_ASSERT:
        assert regdump_addr < 0x80000000, f"For the destination address `{hex(regdump_addr)}`, we will need to manage sign extension, which is not yet implemented here."
        assert stopsig_addr < 0x80000000, f"For the destination address `{hex(stopsig_addr)}`, we will need to manage sign extension, which is not yet implemented here."

    ret = []
    is_design_64bit = target.is_64bit
    design_has_fpu = target.has_fpu
    design_has_fpudouble = target.has_fpud

    ###
    # Dump registers
    ###

    # We re-purpose RDEP_MASK_REGISTER_ID, because we will not need it anymore.
    # Compute the register dump address
    if target.htif:
        htif_offset = htif_block_offset(fuzzerstate.memsize)
        ret += _pcrel_into_reg(RDEP_MASK_REGISTER_ID, htif_offset + HTIF_REGDUMP_OFFSET, fuzzerstate.final_bb_base_addr, is_design_64bit)
    else:
        lui_imm_regdump, addi_imm_regdump = li_into_reg(regdump_addr)
        ret += [
            ImmRdInstruction("lui", RDEP_MASK_REGISTER_ID, lui_imm_regdump, is_design_64bit),
            RegImmInstruction("addi", RDEP_MASK_REGISTER_ID, RDEP_MASK_REGISTER_ID, addi_imm_regdump, is_design_64bit)
        ]

    # Store the register values to the register dump address
    ret.append(SpecialInstruction("fence")) # Hopefully this prevents speculative execution of the stores
    for reg_id in range(1, MAX_NUM_PICKABLE_REGS):
        ret.append(IntStoreInstruction("sd" if is_design_64bit else "sw", RDEP_MASK_REGISTER_ID, reg_id, 0, -1, is_design_64bit))
        ret.append(SpecialInstruction("fence"))

    # Store the floating values as well, if FPU is supported and if there is no risk of it being deactivated
    if design_has_fpu and not fuzzerstate.is_fpu_activated:
        # Check that the fpregdump addr is correctly positioned
        if DO_ASSERT and not target.htif:
            assert target.fpregdump_addr == regdump_addr + 8, f"We make the assumption that the FP regdump addr is the int regdump address + 8. However, currently, they are respectively {hex(target.fpregdump_addr)} and regdump_addr={hex(regdump_addr)}"
        if fuzzerstate.privilegestate.privstate == PrivilegeStateEnum.MACHINE:
            # Enable the FPU
            ret.append(CSRRegInstruction("csrrw", 0, FPU_ENDIS_REGISTER_ID, CSR_IDS.MSTATUS))
            fuzzerstate.is_fpu_activated = True
        if fuzzerstate.is_fpu_activated:
            for reg_id in range(MAX_NUM_PICKABLE_FLOATING_REGS):
                ret.append(FloatStoreInstruction("fsd" if design_has_fpudouble else "fsw", RDEP_MASK_REGISTER_ID, reg_id, 8, -1, is_design_64bit))
                ret.append(SpecialInstruction("fence"))

    ###
    # Stop request
    ###

    if target.htif:
        # RDEP_MASK_REGISTER_ID still holds the register dump address. x1 is already dumped.
        # Writing 1 to tohost asks the HTIF host to exit with code 0.
        ret += [
            RegImmInstruction("addi", RDEP_MASK_REGISTER_ID, RDEP_MASK_REGISTER_ID, HTIF_TOHOST_OFFSET - HTIF_REGDUMP_OFFSET, is_design_64bit),
            RegImmInstruction("addi", 1, 0, 1, is_design_64bit),
            IntStoreInstruction("sd" if is_design_64bit else "sw", RDEP_MASK_REGISTER_ID, 1, 0, -1, is_design_64bit),
            SpecialInstruction("fence")
        ]
    else:
        lui_imm_stopreq, addi_imm_stopreq = li_into_reg(stopsig_addr)

        # We re-purpose RDEP_MASK_REGISTER_ID, because we will not need it anymore.
        # Compute the stop request address
        ret += [
            ImmRdInstruction("lui", RDEP_MASK_REGISTER_ID, lui_imm_stopreq, is_design_64bit),
            RegImmInstruction("addi", RDEP_MASK_REGISTER_ID, RDEP_MASK_REGISTER_ID, addi_imm_stopreq, is_design_64bit)
        ]

        # Store the register values to the register dump address
        ret.append(IntStoreInstruction("sd" if is_design_64bit else "sw", RDEP_MASK_REGISTER_ID, 0, 0 & 0xFFFF, -1, is_design_64bit))
        ret.append(SpecialInstruction("fence"))

    # Infinite loop in the end of the simulation
    ret.append(JALInstruction("jal", 0, 0))

    if DO_ASSERT:
        assert len(ret) * 4 <= get_finalblock_max_size(), f"The final block is larger than expected: {len(ret) * 4} > {get_finalblock_max_size()}"

    return ret

# Spike does not support writing to some signaling addresses, but at the same time, we do not need it for spike resolution anyway. So let's replace it with an infinite loop.
def finalblock_spike_resolution():
    # Infinite loop in the end of the simulation
    return [JALInstruction("jal", 0, 0)]
