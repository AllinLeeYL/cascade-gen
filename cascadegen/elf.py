# Copyright 2023 Flavien Solt, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

# Fast direct ELF emitter for the simple programs Cascade generates.
#
# The previous implementation went through ``makeelf``, whose ``__bytes__``
# routine XOR-merged each header into a zero-initialised buffer using a Python
# byte-by-byte loop, and then shelled out to ``objcopy`` to relocate the
# section and convert the format. With the 64-128 KiB sections Cascade emits,
# that combination dominated the per-program wall time (>80%).
#
# We now emit a minimal ELF directly with ``struct``: ELF32-littleriscv for
# 32-bit designs, ELF64-littleriscv for 64-bit. The section is placed at its
# final virtual address up front so no ``objcopy --change-section-address``
# pass is needed.

from cascadegen.params.runparams import DO_ASSERT
import os
import struct

# Layout constants for ELF32-littleriscv
_E32_EHDR_SIZE = 52
_E32_PHDR_SIZE = 32
_E32_SHDR_SIZE = 40

# Layout constants for ELF64-littleriscv
_E64_EHDR_SIZE = 64
_E64_PHDR_SIZE = 56
_E64_SHDR_SIZE = 64

_SHSTRTAB_BYTES = b"\x00.shstrtab\x00.text.init\x00"
_NUM_SHDRS = 3  # NULL, .shstrtab, .text.init


def _build_elf32_riscv(inbytes: bytes, start_addr: int, section_addr: int) -> bytes:
    section_size = len(inbytes)
    phoff = _E32_EHDR_SIZE
    shoff = phoff + _E32_PHDR_SIZE
    shstrtab_offset = shoff + _NUM_SHDRS * _E32_SHDR_SIZE
    section_data_offset = shstrtab_offset + len(_SHSTRTAB_BYTES)

    e_ident = b"\x7fELF\x01\x01\x01\x00" + b"\x00" * 8
    ehdr = e_ident + struct.pack(
        '<HHIIIIIHHHHHH',
        2, 0xf3, 1, start_addr,
        phoff, shoff, 0,
        _E32_EHDR_SIZE, _E32_PHDR_SIZE, 1, _E32_SHDR_SIZE, _NUM_SHDRS, 1,
    )
    phdr = struct.pack(
        '<IIIIIIII',
        1,                       # PT_LOAD
        section_data_offset,
        section_addr, section_addr,
        section_size, section_size,
        7,                       # PF_R | PF_W | PF_X
        1,
    )
    shdr_null = b"\x00" * _E32_SHDR_SIZE
    shdr_shstrtab = struct.pack(
        '<IIIIIIIIII',
        1, 3, 0, 0,
        shstrtab_offset, len(_SHSTRTAB_BYTES),
        0, 0, 1, 0,
    )
    shdr_text = struct.pack(
        '<IIIIIIIIII',
        11, 1, 6, section_addr,
        section_data_offset, section_size,
        0, 0, 4, 0,
    )
    return ehdr + phdr + shdr_null + shdr_shstrtab + shdr_text + _SHSTRTAB_BYTES + inbytes


def _build_elf64_riscv(inbytes: bytes, start_addr: int, section_addr: int) -> bytes:
    section_size = len(inbytes)
    phoff = _E64_EHDR_SIZE
    shoff = phoff + _E64_PHDR_SIZE
    shstrtab_offset = shoff + _NUM_SHDRS * _E64_SHDR_SIZE
    section_data_offset = shstrtab_offset + len(_SHSTRTAB_BYTES)

    # ELFCLASS64, little-endian
    e_ident = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
    ehdr = e_ident + struct.pack(
        '<HHIQQQIHHHHHH',
        2,            # e_type ET_EXEC
        0xf3,         # e_machine EM_RISCV
        1,            # e_version
        start_addr,   # e_entry (64-bit)
        phoff,        # e_phoff (64-bit)
        shoff,        # e_shoff (64-bit)
        0,            # e_flags
        _E64_EHDR_SIZE,
        _E64_PHDR_SIZE, 1,
        _E64_SHDR_SIZE, _NUM_SHDRS, 1,
    )
    # Phdr64: p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align
    phdr = struct.pack(
        '<IIQQQQQQ',
        1,                       # p_type PT_LOAD
        7,                       # p_flags
        section_data_offset,
        section_addr, section_addr,
        section_size, section_size,
        1,                       # p_align
    )
    shdr_null = b"\x00" * _E64_SHDR_SIZE
    shdr_shstrtab = struct.pack(
        '<IIQQQQIIQQ',
        1, 3, 0, 0,
        shstrtab_offset, len(_SHSTRTAB_BYTES),
        0, 0, 1, 0,
    )
    shdr_text = struct.pack(
        '<IIQQQQIIQQ',
        11, 1, 6, section_addr,
        section_data_offset, section_size,
        0, 0, 4, 0,
    )
    return ehdr + phdr + shdr_null + shdr_shstrtab + shdr_text + _SHSTRTAB_BYTES + inbytes


# ELF with a second, zero-filled loadable segment and a symbol table, for the HTIF
# mode (not in Cascade). Loaders such as fesvr find `tohost`/`fromhost` by symbol.
# @param extra_addr, extra_size address and size of the zero-filled segment (.htif).
# @param symbols dict name -> absolute address, all inside the .htif segment.
def _build_elf_riscv_with_symbols(inbytes: bytes, start_addr: int, section_addr: int, is_64bit: bool,
                                  extra_addr: int, extra_size: int, symbols: dict) -> bytes:
    if is_64bit:
        ehdr_size, phdr_size, shdr_size, sym_size = _E64_EHDR_SIZE, _E64_PHDR_SIZE, _E64_SHDR_SIZE, 24
        ehdr_fmt, shdr_fmt = '<HHIQQQIHHHHHH', '<IIQQQQIIQQ'
        def phdr(offset, addr, size, flags):
            return struct.pack('<IIQQQQQQ', 1, flags, offset, addr, addr, size, size, 1)
        def sym(name, value, info, shndx):
            return struct.pack('<IBBHQQ', name, info, 0, shndx, value, 8 if info else 0)
        ident = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
    else:
        ehdr_size, phdr_size, shdr_size, sym_size = _E32_EHDR_SIZE, _E32_PHDR_SIZE, _E32_SHDR_SIZE, 16
        ehdr_fmt, shdr_fmt = '<HHIIIIIHHHHHH', '<IIIIIIIIII'
        def phdr(offset, addr, size, flags):
            return struct.pack('<IIIIIIII', 1, offset, addr, addr, size, size, flags, 1)
        def sym(name, value, info, shndx):
            return struct.pack('<IIIBBH', name, value, 8 if info else 0, info, 0, shndx)
        ident = b"\x7fELF\x01\x01\x01\x00" + b"\x00" * 8

    # Sections: NULL, .shstrtab, .text.init, .htif, .symtab, .strtab
    shstrtab = b"\x00.shstrtab\x00.text.init\x00.htif\x00.symtab\x00.strtab\x00"
    name_off = {n: shstrtab.index(n.encode() + b"\x00") for n in ('.shstrtab', '.text.init', '.htif', '.symtab', '.strtab')}
    htif_shndx, strtab_shndx, num_shdrs = 3, 5, 6
    strtab = b"\x00"
    symtab = sym(0, 0, 0, 0)
    for name, addr in symbols.items():
        symtab += sym(len(strtab), addr, 0x11, htif_shndx) # STB_GLOBAL, STT_OBJECT
        strtab += name.encode() + b"\x00"

    phoff = ehdr_size
    shoff = phoff + 2 * phdr_size
    shstrtab_offset = shoff + num_shdrs * shdr_size
    strtab_offset = shstrtab_offset + len(shstrtab)
    symtab_offset = (strtab_offset + len(strtab) + 7) & ~7
    text_offset = symtab_offset + len(symtab)
    extra_offset = text_offset + len(inbytes)

    ehdr = ident + struct.pack(ehdr_fmt, 2, 0xf3, 1, start_addr, phoff, shoff, 0,
                               ehdr_size, phdr_size, 2, shdr_size, num_shdrs, 1)
    phdrs = phdr(text_offset, section_addr, len(inbytes), 7) + phdr(extra_offset, extra_addr, extra_size, 6)
    # sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link, sh_info, sh_addralign, sh_entsize
    shdrs = b"\x00" * shdr_size
    shdrs += struct.pack(shdr_fmt, name_off['.shstrtab'], 3, 0, 0, shstrtab_offset, len(shstrtab), 0, 0, 1, 0)
    shdrs += struct.pack(shdr_fmt, name_off['.text.init'], 1, 7, section_addr, text_offset, len(inbytes), 0, 0, 4, 0)
    shdrs += struct.pack(shdr_fmt, name_off['.htif'], 1, 3, extra_addr, extra_offset, extra_size, 0, 0, 64, 0)
    shdrs += struct.pack(shdr_fmt, name_off['.symtab'], 2, 0, 0, symtab_offset, len(symtab), strtab_shndx, 1, 8, sym_size)
    shdrs += struct.pack(shdr_fmt, name_off['.strtab'], 3, 0, 0, strtab_offset, len(strtab), 0, 0, 1, 0)
    padding = b"\x00" * (symtab_offset - strtab_offset - len(strtab))
    return ehdr + phdrs + shdrs + shstrtab + strtab + padding + symtab + inbytes + b"\x00" * extra_size


# @param inbytes the bytes to put into the ELF file. Be careful that they must be in little endian format already.
# @param start_addr the entry PC.
# @param section_addr address at which to load the .text.init section. May be None to use ``start_addr``.
# @param destination_path output ELF path.
# @param is_64bit if True emit ELF64-littleriscv, else ELF32-littleriscv.
# @param htif None, or (address, size, symbols) of a zero-filled HTIF segment and its symbols.
def gen_elf(inbytes: bytes, start_addr: int, section_addr: int, destination_path: str, is_64bit: bool, htif: tuple = None) -> None:
    if DO_ASSERT:
        assert destination_path

    if section_addr is None:
        section_addr = start_addr

    if htif is not None:
        elf_bytes = _build_elf_riscv_with_symbols(inbytes, start_addr, section_addr, is_64bit, *htif)
    elif is_64bit:
        elf_bytes = _build_elf64_riscv(inbytes, start_addr, section_addr)
    else:
        elf_bytes = _build_elf32_riscv(inbytes, start_addr, section_addr)

    with open(destination_path, 'wb') as f:
        f.write(elf_bytes)
