# Copyright 2023 Flavien Solt, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

# This utility defines which workaround should be disabled.
# This allows, for example, to measure time to bug detection.
# Some bugs must be reintroduced in hw and cannot simply be reintroduced as a non-workaround in the fuzzer.

__NO_INTERACTION_MINSTRET = False
def is_no_interaction_minstret(design_name):
    return __NO_INTERACTION_MINSTRET or 'cva6' in design_name

###
# BOOM
###

__TOLERATE_BOOM_MINSTRET = False
def is_tolerate_boom_minstret():
    return __TOLERATE_BOOM_MINSTRET
if __TOLERATE_BOOM_MINSTRET:
    print('WARNING: Tolerating one bug: __TOLERATE_BOOM_MINSTRET')

###
# Rocket
###

__TOLERATE_ROCKET_MINSTRET = False
def is_tolerate_rocket_minstret():
    return __TOLERATE_ROCKET_MINSTRET
if __TOLERATE_ROCKET_MINSTRET:
    print('WARNING: Tolerating one bug: __TOLERATE_ROCKET_MINSTRET')

###
# CVA6
###

# This specific one is not used because we use cva6-c1 where the bug is reinjected
__TOLERATE_CVA6_FMULD_RDN = False
def is_tolerate_cva6_fmuld_rdn():
    return __TOLERATE_CVA6_FMULD_RDN
if __TOLERATE_CVA6_FMULD_RDN:
    print('WARNING: Tolerating one bug: __TOLERATE_CVA6_FMULD_RDN')

__TOLERATE_CVA6_SINGLE_PRECISION = False
def is_tolerate_cva6_single_precision():
    return __TOLERATE_CVA6_SINGLE_PRECISION
if __TOLERATE_CVA6_SINGLE_PRECISION:
    print('WARNING: Tolerating one bug: __TOLERATE_CVA6_SINGLE_PRECISION')

__TOLERATE_CVA6_DIVISION = False
def is_tolerate_cva6_division():
    return __TOLERATE_CVA6_DIVISION
if __TOLERATE_CVA6_DIVISION:
    print('WARNING: Tolerating one bug: __TOLERATE_CVA6_DIVISION')

__TOLERATE_CVA6_FDIVS_FLAGS = False
def is_tolerate_cva6_fdivs_flags():
    return __TOLERATE_CVA6_FDIVS_FLAGS
if __TOLERATE_CVA6_FDIVS_FLAGS:
    print('WARNING: Tolerating one bug: __TOLERATE_CVA6_FDIVS_FLAGS')

__TOLERATE_CVA6_MHPMCOUNTER = False
def is_tolerate_cva6_mhpmcounter():
    return __TOLERATE_CVA6_MHPMCOUNTER
if __TOLERATE_CVA6_MHPMCOUNTER:
    print('WARNING: Tolerating one bug: __TOLERATE_CVA6_MHPMCOUNTER')

__TOLERATE_CVA6_MHPMEVENT31 = False
def is_tolerate_cva6_mhpmevent31():
    return __TOLERATE_CVA6_MHPMEVENT31
if __TOLERATE_CVA6_MHPMEVENT31:
    print('WARNING: Tolerating one bug: __TOLERATE_CVA6_MHPMEVENT31')

###
# Kronos
###

__TOLERATE_KRONOS_READBADCSR = False
def is_tolerate_kronos_readbadcsr():
    return __TOLERATE_KRONOS_READBADCSR
if __TOLERATE_KRONOS_READBADCSR:
    print('WARNING: Tolerating one bug: __TOLERATE_KRONOS_READBADCSR')

__TOLERATE_KRONOS_MINSTRET = False
def is_tolerate_kronos_minstret():
    return __TOLERATE_KRONOS_MINSTRET
if __TOLERATE_KRONOS_MINSTRET:
    print('WARNING: Tolerating one bug: __TOLERATE_KRONOS_MINSTRET')

__TOLERATE_KRONOS_FENCE = False
def is_tolerate_kronos_fence():
    return __TOLERATE_KRONOS_FENCE
if __TOLERATE_KRONOS_FENCE:
    print('WARNING: Tolerating one bug: __TOLERATE_KRONOS_FENCE')


###
# Picorv32
###

__TOLERATE_PICORV32_READNONIMPLCSR = False
def is_tolerate_picorv32_readnonimplcsr():
    return __TOLERATE_PICORV32_READNONIMPLCSR
if __TOLERATE_PICORV32_READNONIMPLCSR:
    print('WARNING: Tolerating one bug: __TOLERATE_PICORV32_READNONIMPLCSR')

__TOLERATE_PICORV32_MISSINGMANDATORYCSRS = False
def is_tolerate_picorv32_missingmandatorycsrs():
    return __TOLERATE_PICORV32_MISSINGMANDATORYCSRS
if __TOLERATE_PICORV32_MISSINGMANDATORYCSRS:
    print('WARNING: Tolerating one bug: __TOLERATE_PICORV32_MISSINGMANDATORYCSRS')

__TOLERATE_PICORV32_FENCE = False
def is_tolerate_picorv32_fence():
    return __TOLERATE_PICORV32_FENCE
if __TOLERATE_PICORV32_FENCE:
    print('WARNING: Tolerating one bug: __TOLERATE_PICORV32_FENCE')

__TOLERATE_PICORV32_WRITEHPM = False
def is_tolerate_picorv32_writehpm():
    return __TOLERATE_PICORV32_WRITEHPM
if __TOLERATE_PICORV32_WRITEHPM:
    print('WARNING: Tolerating one bug: __TOLERATE_PICORV32_WRITEHPM')

__TOLERATE_PICORV32_READHPM_NOCSRRS = False
def is_tolerate_picorv32_readhpm_nocsrrs():
    return __TOLERATE_PICORV32_READHPM_NOCSRRS
if __TOLERATE_PICORV32_READHPM_NOCSRRS:
    print('WARNING: Tolerating one bug: __TOLERATE_PICORV32_READHPM_NOCSRRS')

###
# VexRiscv
###

# This prevents detecting the other bugs when using the pre-fpu-fix Vexriscv version.
__FORBID_VEXRISCV_CSRS = False
def is_forbid_vexriscv_csrs():
    return __FORBID_VEXRISCV_CSRS
if __FORBID_VEXRISCV_CSRS:
    print('WARNING: Forbidding one bug: __FORBID_VEXRISCV_CSRS')



__TOLERATE_VEXRISCV_MINSTRET = False
def is_tolerate_vexriscv_minstret():
    return __TOLERATE_VEXRISCV_MINSTRET
if __TOLERATE_VEXRISCV_MINSTRET:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_MINSTRET')

__TOLERATE_VEXRISCV_IMPRECISE_FCVT = False
def is_tolerate_vexriscv_imprecise_fcvt():
    return __TOLERATE_VEXRISCV_IMPRECISE_FCVT
if __TOLERATE_VEXRISCV_IMPRECISE_FCVT:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_IMPRECISE_FCVT')

__TOLERATE_VEXRISCV_FMIN = False
def is_tolerate_vexriscv_fmin():
    return __TOLERATE_VEXRISCV_FMIN
if __TOLERATE_VEXRISCV_FMIN:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_FMIN')

__TOLERATE_VEXRISCV_DOUBLE_TO_FLOAT = False
def is_tolerate_vexriscv_double_to_float():
    return __TOLERATE_VEXRISCV_DOUBLE_TO_FLOAT
if __TOLERATE_VEXRISCV_DOUBLE_TO_FLOAT:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_DOUBLE_TO_FLOAT')

__TOLERATE_VEXRISCV_DEPENDENT_SINGLE_PRECISION = False
def is_tolerate_vexriscv_dependent_single_precision():
    return __TOLERATE_VEXRISCV_DEPENDENT_SINGLE_PRECISION
if __TOLERATE_VEXRISCV_DEPENDENT_SINGLE_PRECISION:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_DEPENDENT_SINGLE_PRECISION')

__TOLERATE_VEXRISCV_DEPENDENT_FLE_FEQ_RET1 = False
def is_tolerate_vexriscv_dependent_fle_feq_ret1():
    return __TOLERATE_VEXRISCV_DEPENDENT_FLE_FEQ_RET1
if __TOLERATE_VEXRISCV_DEPENDENT_FLE_FEQ_RET1:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_DEPENDENT_FLE_FEQ_RET1')

__TOLERATE_VEXRISCV_DEPENDENT_FLT_RET0 = False
def is_tolerate_vexriscv_dependent_flt_ret0():
    return __TOLERATE_VEXRISCV_DEPENDENT_FLT_RET0
if __TOLERATE_VEXRISCV_DEPENDENT_FLT_RET0:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_DEPENDENT_FLT_RET0')

__TOLERATE_VEXRISCV_SQRT = False
def is_tolerate_vexriscv_sqrt():
    return __TOLERATE_VEXRISCV_SQRT
if __TOLERATE_VEXRISCV_SQRT:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_SQRT')

__TOLERATE_VEXRISCV_MULDIV_CONVERSION = False
def is_tolerate_vexriscv_muldiv_conversion():
    return __TOLERATE_VEXRISCV_MULDIV_CONVERSION
if __TOLERATE_VEXRISCV_MULDIV_CONVERSION:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_MULDIV_CONVERSION')

__TOLERATE_VEXRISCV_FPU_DISABLED = False
def is_tolerate_vexriscv_fpu_disabled():
    return __TOLERATE_VEXRISCV_FPU_DISABLED
if __TOLERATE_VEXRISCV_FPU_DISABLED:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_FPU_DISABLED')

__TOLERATE_VEXRISCV_FPU_LEAK = False
def is_tolerate_vexriscv_fpu_leak():
    return __TOLERATE_VEXRISCV_FPU_LEAK
if __TOLERATE_VEXRISCV_FPU_LEAK:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_FPU_LEAK')

__TOLERATE_VEXRISCV_MHPMCOUNTERN = False
def is_tolerate_vexriscv_mhpmcountern():
    return __TOLERATE_VEXRISCV_MHPMCOUNTERN
if __TOLERATE_VEXRISCV_MHPMCOUNTERN:
    print('WARNING: Tolerating one bug: __TOLERATE_VEXRISCV_MHPMCOUNTERN')
