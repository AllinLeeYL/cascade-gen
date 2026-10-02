# SPDX-License-Identifier: GPL-3.0-only

# Description of the core that the generated programs target.
#
# Cascade originally read this from `meta/cfg.json` inside each design
# repository, and profiled medeleg by simulating the RTL. Here, the same
# information is carried by a `Target` object. The built-in profiles below
# reproduce the `cfg.json` of the designs evaluated in the Cascade paper.

from dataclasses import dataclass, asdict, replace

from cascadegen.spike import SPIKE_MEDELEG_MASK

# Extensions that Cascade can generate instructions for, in canonical order.
SUPPORTED_EXTENSIONS = 'imafdc'


@dataclass(frozen=True)
class Target:
    # Name of the design. Design-specific workarounds in the generator are
    # keyed on substrings of this name (e.g., `'vexriscv' in name`), so any
    # name that does not contain a known design name gets none of them.
    name: str
    # ISA string as passed to `-march` and to spike, e.g., `rv64gc`.
    isa: str
    # Supported privilege levels, a subset of `msu`. Must contain `m`.
    privlvs: str = 'msu'
    # Whether the core handles misaligned data accesses in hardware.
    misaligned: bool = False
    # Whether the core implements PMP CSRs.
    pmp: bool = True
    # Address at which the core starts executing; also where the ELF is loaded.
    boot_addr: int = 0x80000000
    # Address to which the final block writes to stop the simulation.
    stop_addr: int = 0x0
    # Address to which the final block dumps the integer registers.
    regdump_addr: int = 0x10
    # Address to which the final block dumps the floating-point registers.
    # Cascade requires it to be regdump_addr + 8.
    fpregdump_addr: int = 0x18
    # medeleg bits implemented by the core. Cascade profiled this by running
    # the RTL; here it must be provided.
    medeleg_mask: int = SPIKE_MEDELEG_MASK
    # Not in Cascade. If True, the program ends through the HTIF protocol instead of
    # stop_addr/regdump_addr: the final block dumps the registers to, and writes 1
    # (exit code 0) to `tohost`, in a block just after the program memory, and the ELF
    # carries `tohost`/`fromhost` symbols. For stock harnesses such as Chipyard's.
    htif: bool = False

    def __post_init__(self):
        isa = self.isa.lower()
        if not (isa.startswith('rv32') or isa.startswith('rv64')):
            raise ValueError(f"ISA string `{self.isa}` must start with rv32 or rv64.")
        letters = self._base_letters()
        if not letters.startswith(('i', 'g')):
            raise ValueError(f"ISA string `{self.isa}` must contain the I base.")
        unsupported = set(letters) - set(SUPPORTED_EXTENSIONS) - {'g'}
        if unsupported:
            raise ValueError(f"ISA string `{self.isa}` has unsupported extensions: {', '.join(sorted(unsupported))}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}.")
        if 'm' not in self.privlvs or set(self.privlvs) - set('msu'):
            raise ValueError(f"Privilege levels `{self.privlvs}` must contain `m` and be a subset of `msu`.")
        for field in ('stop_addr', 'regdump_addr', 'fpregdump_addr'):
            if getattr(self, field) >= 0x80000000:
                raise ValueError(f"{field} must be below 0x80000000.")
        if self.has_fpu and self.fpregdump_addr != self.regdump_addr + 8:
            raise ValueError("fpregdump_addr must be regdump_addr + 8.")

    def _base_letters(self) -> str:
        return self.isa.lower()[4:].split('_')[0]

    def _has_ext(self, ext: str) -> bool:
        letters = self._base_letters()
        return ext in letters or (ext in 'imafd' and 'g' in letters)

    @property
    def is_64bit(self) -> bool:
        return self.isa.lower().startswith('rv64')

    @property
    def has_fpu(self) -> bool:
        return self._has_ext('f')

    @property
    def has_fpud(self) -> bool:
        return self._has_ext('d')

    @property
    def has_muldiv(self) -> bool:
        return self._has_ext('m')

    @property
    def has_amo(self) -> bool:
        return self._has_ext('a')

    @property
    def has_compressed(self) -> bool:
        return self._has_ext('c')

    @property
    def has_supervisor_mode(self) -> bool:
        return 's' in self.privlvs

    @property
    def has_user_mode(self) -> bool:
        return 'u' in self.privlvs

    # ISA string for spike, without the C extension. Used for the spike
    # resolution ELF, which never contains compressed instructions.
    @property
    def isa_nocompressed(self) -> str:
        isa = self.isa.lower()
        prefix, base, rest = isa[:4], self._base_letters(), isa[4 + len(self._base_letters()):]
        return prefix + base.replace('c', '') + rest

    def to_dict(self) -> dict:
        return asdict(self)


def make_isa(xlen: int, extensions) -> str:
    """Builds an ISA string such as `rv64gc` from an XLEN and extension letters."""
    exts = set()
    for ext in extensions:
        ext = ext.strip().lower()
        if ext in ('', 'zicsr', 'zifencei'):
            continue # Always used by Cascade.
        if ext == 'g':
            exts |= set('imafd')
        elif len(ext) == 1:
            exts.add(ext)
        else:
            raise ValueError(f"Unsupported extension `{ext}`. Supported: {', '.join(SUPPORTED_EXTENSIONS)}, g.")
    exts.add('i')
    letters = ''.join(e for e in SUPPORTED_EXTENSIONS if e in exts)
    letters += ''.join(sorted(exts - set(SUPPORTED_EXTENSIONS)))
    if set('imafd') <= exts:
        letters = 'g' + letters[5:]
    return f"rv{xlen}{letters}"


# Profiles of the designs evaluated in the Cascade paper, from their `meta/cfg.json`.
# The medeleg masks default to spike's because Cascade obtained them from RTL simulation.
# picorv32 does not implement PMP, which Cascade hardcoded.
DESIGNS = {
    'rocket':   Target('rocket',   'rv64gc',   'msu', stop_addr=0x60000000, regdump_addr=0x60000010, fpregdump_addr=0x60000018),
    'boom':     Target('boom',     'rv64gc',   'msu', stop_addr=0x60000000, regdump_addr=0x60000010, fpregdump_addr=0x60000018),
    'cva6':     Target('cva6',     'rv64g',    'msu'),
    'vexriscv': Target('vexriscv', 'rv32imfd', 'msu', stop_addr=0x20),
    'kronos':   Target('kronos',   'rv32i',    'mu'),
    'picorv32': Target('picorv32', 'rv32im',   'm', pmp=False, medeleg_mask=0),
}


def get_target(design: str, **overrides) -> Target:
    """Returns the profile of `design`, with the non-None `overrides` applied.
    Unknown design names start from a generic rv64gc machine-supervisor-user core."""
    overrides = {k: v for k, v in overrides.items() if v is not None}
    base = DESIGNS.get(design, Target(design, 'rv64gc'))
    return replace(base, name=design, **overrides)
