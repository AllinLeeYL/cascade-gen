# cascadegen

The RISC-V program generator of [Cascade](https://github.com/cascade-artifacts-designs/cascade-meta)
(Solt et al., *Cascade: CPU Fuzzing via Intricate Program Generation*, USENIX Security 2024),
extracted from the fuzzer as a standalone command-line tool that writes ELF files.

The generation logic is Cascade's, unchanged: for the same parameters, the
programs are byte-identical to those of the original code (see [Fidelity](#fidelity)).
Everything else in Cascade (RTL simulation, Verilator/Modelsim flows, program
reduction, design processing, evaluation and plotting scripts) is removed.

## Requirements

- Python 3.9+ with `numpy`.
- [spike](https://github.com/riscv-software-src/riscv-isa-sim) in `PATH` (or passed with `--spike`).
  Cascade runs every program once on spike to resolve its control flow and data
  dependencies, so spike is required to generate programs.

## Install

```sh
pip install -e .          # installs the `cascade-gen` command
# or run in place, without installing:
python -m cascadegen --help
```

## Usage

Generate a single program:

```sh
cascade-gen one --design rocket --seed 42 -o rvprog.elf
```

Generate a batch of programs in parallel:

```sh
cascade-gen many --design rocket -n 1000 --seed 0 -o elfs -j 16
```

ELF `i` of a batch is written to `elfs/<i>.elf` and uses seed `seed+i`, so
`many --seed 0` produces exactly the programs of `one --seed 0`, `one --seed 1`, and so on.
Without `--seed`, a random seed is used and printed.

List the built-in design profiles:

```sh
cascade-gen designs
```

Run `cascade-gen one --help` or `cascade-gen many --help` for all options.

### Target options

A target is a design profile plus optional overrides.

- `--design`: `rocket`, `boom`, `cva6`, `vexriscv`, `kronos`, or `picorv32` (default: `rocket`).
  The profiles reproduce each design's Cascade `cfg.json`. Cascade also enables
  design-specific workarounds by name (e.g., it avoids CSRs that VexRiscv lacks).
  Any other name, e.g. `--design generic`, gives a `rv64gc` MSU core without workarounds.
- `--xlen`, `--isa`: register width and extensions. `--isa` takes a comma-separated list
  among `i,m,a,f,d,c,g` (e.g. `--xlen 32 --isa i,m,c`) or a full ISA string (`--isa rv64gc`).
  Zicsr and Zifencei are always used. Cascade does not generate any other extension.
- `--priv`: privilege levels, a subset of `msu` that contains `m`.
- `--misaligned/--no-misaligned`, `--pmp/--no-pmp`: whether the core supports misaligned data accesses or implements PMP.
- `--boot-addr`: load and entry address (default `0x80000000`).
- `--stop-addr`, `--regdump-addr`: termination protocol (see below).
- `--htif`: end through the HTIF `tohost` protocol instead, for stock harnesses such as
  Chipyard's, spike, or riscv-tests environments (see below). Not in Cascade.
- `--medeleg-mask`: medeleg bits that the core implements. Cascade got this by simulating
  the RTL. Here it defaults to spike's mask (`0xb3ff`) and should be set to the core's mask.

### Program options

- `--memsize`: size of the program's memory region (default: random in [2^14, 2^20)).
- `--num-bbs`: maximum number of basic blocks (default: random in [20, 100)).
- `--max-instrs`: stop after this many instructions (default: no limit).
- `--privileges on|off|random`: allow privilege-level changes. `random` enables them with
  probability 0.05, as Cascade does.
- `--no-dependency-bias`: Cascade's ablation that does not favor recently produced registers.

Unset parameters are drawn from the seed in the same way as Cascade's `gen_new_test_instance`.

### Generation options

- `--check`: re-run each final ELF on spike and check its PC trace and final registers (Cascade's `check_pc_spike_again`).
- `--no-meta`: do not write the JSON metadata.
- `--spike PATH`: spike binary.

## Output

Each ELF contains one loadable RWX section of `memsize` bytes at the boot address,
and its entry point is the boot address. The program ends with Cascade's final block:

1. It stores `x1`..`x24` to `regdump_addr`, one store per register, with each store
   separated by a `fence`. In some cases it also stores the FP registers to `regdump_addr + 8`,
   under conditions inherited from Cascade (see `cascadegen/core/finalblock.py`).
2. It stores `0` to `stop_addr`, then loops forever (`jal x0, 0`).

With `--htif`, the final block instead stores the registers to `tohost + 0x80` (FP
registers to `tohost + 0x88`) and then writes `1` (exit code 0) to `tohost`. `tohost` lies
just after the program memory, at `boot_addr + memsize` rounded up to 64 bytes, and the
final block addresses it PC-relatively (`auipc`). The ELF gains a second, zero-filled
256-byte segment holding `tohost` (`fromhost` at `+0x40`), and a symbol table with both
symbols. `--stop-addr`/`--regdump-addr` are then ignored. The program layout and every
instruction outside the final block are unchanged. Without `--htif`, the output is
Cascade's, as checked by the golden tests.

Unless `--no-meta` is given, a JSON file next to each ELF records the parameters
(seed, memsize, number of basic blocks, privileges, target) and these values:

- `entry_addr`, `final_block_addr`: start of the program and of the final block.
- `num_instrs`: number of instructions in the program, including the final block.
- `tohost_addr`: with `--htif`, the address of `tohost`.
- `expected_intregs`, `expected_fpregs`: final register values computed by spike. As in
  Cascade's checker, only the integer registers that are not transient at the end of
  the program are listed. A core under test should end with these values. The values
  assume the boot address is `0x80000000`, where spike runs the program.

## Fidelity

`tests/test_golden.py` regenerates 24 programs (4 seeds × 6 designs, with and
without privilege changes) and compares their SHA-256 with the outputs of the
original Cascade code (cascade-meta commit `782e0e7`):

```sh
pip install -e '.[test]' && pytest tests
```

The generated programs differ from the original Cascade code in these ways:

- The ELF entry point is the absolute boot address. Cascade wrote the relative offset (`0`)
  because its testbenches ignored the field.
- The medeleg mask is a parameter (default `0xb3ff`). Cascade measured it on the RTL.
  This only matters for targets with supervisor mode.
- In a batch, each program's random parameters come from its own seed. Cascade drew
  them in sequence from one RNG. The distribution of the parameters is the same.

## Layout

- `cascadegen/cli.py`: command-line interface.
- `cascadegen/generate.py`: generation of one program from a descriptor, and its metadata.
- `cascadegen/target.py`: target description and the built-in design profiles. Replaces Cascade's `designcfgs.py`.
- `cascadegen/core/`: Cascade's generator, which was `fuzzer/cascade/`: basic blocks, initial and final blocks,
  register and memory state, spike resolution, and ELF layout. `core/randomize/` holds the instruction pickers.
- `cascadegen/rv/`: RISC-V instruction encodings (RV32/64 IMFD, C, Zicsr, Zifencei, privileged).
- `cascadegen/params/`: generation parameters (`fuzzparams.py`) and switches (`runparams.py`).
- `cascadegen/spike.py`: spike driver. `cascadegen/elf.py`: ELF writer.

## License

GPL-3.0-only, as Cascade. See `LICENSE.txt`.
