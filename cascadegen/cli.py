# SPDX-License-Identifier: GPL-3.0-only

# Command-line interface of the Cascade program generator.

import argparse
import json
import multiprocessing as mp
import os
import secrets
import shutil
import sys

from cascadegen import spike
from cascadegen.generate import Descriptor, generate, sample_descriptor
from cascadegen.target import DESIGNS, Target, get_target, make_isa


def parse_int(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer: `{value}`")


def add_common_args(parser: argparse.ArgumentParser):
    tgt = parser.add_argument_group('target')
    tgt.add_argument('--design', default='rocket', metavar='NAME',
        help=f"design profile: one of {', '.join(DESIGNS)}, or any other name for a generic core "
             "without design-specific workarounds (default: rocket)")
    tgt.add_argument('--xlen', type=int, choices=(32, 64), help="register width (default: from the design)")
    tgt.add_argument('--isa', metavar='EXTS',
        help="comma-separated extensions among i,m,a,f,d,c,g, or a full ISA string such as rv64gc "
             "(default: from the design); zicsr and zifencei are always used")
    tgt.add_argument('--priv', metavar='LEVELS', help="privilege levels, a subset of msu containing m (default: from the design)")
    tgt.add_argument('--misaligned', action=argparse.BooleanOptionalAction, default=None,
        help="whether the core supports misaligned data accesses (default: from the design)")
    tgt.add_argument('--pmp', action=argparse.BooleanOptionalAction, default=None,
        help="whether the core implements PMP (default: from the design)")
    tgt.add_argument('--boot-addr', type=parse_int, metavar='ADDR', help="load and entry address (default: 0x80000000)")
    tgt.add_argument('--stop-addr', type=parse_int, metavar='ADDR', help="address written to stop the simulation (default: from the design)")
    tgt.add_argument('--regdump-addr', type=parse_int, metavar='ADDR', help="address where the final registers are dumped (default: from the design)")
    tgt.add_argument('--htif', action='store_true', default=None,
        help="end through HTIF tohost (exit code 0) instead of --stop-addr/--regdump-addr, "
             "for harnesses such as Chipyard's; not in Cascade")
    tgt.add_argument('--medeleg-mask', type=parse_int, metavar='MASK', help="medeleg bits implemented by the core (default: spike's, 0xb3ff)")

    prog = parser.add_argument_group('program')
    prog.add_argument('--memsize', type=parse_int, metavar='BYTES', help="program memory size (default: random in [2^14, 2^20))")
    prog.add_argument('--num-bbs', type=int, metavar='N', help="maximum number of basic blocks (default: random in [20, 100))")
    prog.add_argument('--max-instrs', type=int, metavar='N', help="stop generating after this many instructions (default: no limit)")
    prog.add_argument('--privileges', choices=('random', 'on', 'off'), default='random',
        help="allow privilege-level changes: on, off, or with probability 0.05 as in Cascade (default: random)")
    prog.add_argument('--no-dependency-bias', action='store_true', help="pick among all registers instead of favoring recently produced ones")

    run = parser.add_argument_group('generation')
    run.add_argument('--check', action='store_true', help="re-run each final ELF on spike and check its PC trace and registers")
    run.add_argument('--no-meta', action='store_true', help="do not write the JSON metadata next to each ELF")
    run.add_argument('--spike', default='spike', metavar='PATH', help="spike binary used for address resolution (default: spike)")


def build_target(args) -> Target:
    isa = None
    if args.isa is not None or args.xlen is not None:
        base = get_target(args.design)
        if args.isa is not None and args.isa.lower().startswith('rv'):
            isa = args.isa.lower()
            if args.xlen is not None and not isa.startswith(f"rv{args.xlen}"):
                raise ValueError(f"--xlen {args.xlen} contradicts --isa {args.isa}.")
        else:
            xlen = args.xlen or (64 if base.is_64bit else 32)
            exts = args.isa.split(',') if args.isa is not None else base._base_letters()
            isa = make_isa(xlen, exts)
    fpregdump_addr = args.regdump_addr + 8 if args.regdump_addr is not None else None
    return get_target(args.design, isa=isa, privlvs=args.priv, misaligned=args.misaligned, pmp=args.pmp,
                      boot_addr=args.boot_addr, stop_addr=args.stop_addr, regdump_addr=args.regdump_addr,
                      fpregdump_addr=fpregdump_addr, medeleg_mask=args.medeleg_mask, htif=args.htif)


def build_descriptor(args, seed: int) -> Descriptor:
    privileges = {'random': None, 'on': True, 'off': False}[args.privileges]
    return sample_descriptor(seed, args.memsize, args.num_bbs, privileges, args.max_instrs, args.no_dependency_bias)


def _init_worker(spike_bin: str):
    spike.SPIKE_BIN = spike_bin
    # Forked workers inherit the calibration of the parent.
    if not spike.is_spikespeed_calibrated():
        spike.calibrate_spikespeed()


# Generates one program. Returns (index, error message or None).
def _gen_worker(job):
    index, target, desc, elf_path, check, write_meta = job
    try:
        meta = generate(target, desc, elf_path, check)
    except Exception as e:
        return index, f"{type(e).__name__}: {e}"
    if write_meta:
        with open(os.path.splitext(elf_path)[0] + '.json', 'w') as f:
            json.dump(meta, f, indent=2)
    return index, None


def _check_spike(spike_bin: str):
    if shutil.which(spike_bin) is None:
        raise RuntimeError(f"spike not found: `{spike_bin}`. Cascade needs spike to resolve the program addresses; install it or pass --spike.")


def cmd_one(args) -> int:
    target = build_target(args)
    _check_spike(args.spike)
    seed = args.seed if args.seed is not None else secrets.randbits(32)
    parent = os.path.dirname(args.output)
    if parent:
        os.makedirs(parent, exist_ok=True)
    _init_worker(args.spike)
    _, error = _gen_worker((0, target, build_descriptor(args, seed), args.output, args.check, not args.no_meta))
    if error is not None:
        print(f"error: generation failed for seed {seed}: {error}", file=sys.stderr)
        return 1
    print(f"{args.output} (seed {seed})", file=sys.stderr)
    return 0


def cmd_many(args) -> int:
    target = build_target(args)
    _check_spike(args.spike)
    base_seed = args.seed if args.seed is not None else secrets.randbits(32)
    os.makedirs(args.outdir, exist_ok=True)
    jobs = [(i, target, build_descriptor(args, base_seed + i), os.path.join(args.outdir, f"{i}.elf"), args.check, not args.no_meta)
            for i in range(args.num_elfs)]

    print(f"Generating {args.num_elfs} ELFs for {target.name} ({target.isa}) into {args.outdir} with seeds {base_seed}..{base_seed + args.num_elfs - 1}", file=sys.stderr)
    _init_worker(args.spike)
    failures = []
    show_progress = sys.stderr.isatty()
    with mp.Pool(args.jobs, initializer=_init_worker, initargs=(args.spike,)) as pool:
        for done, (index, error) in enumerate(pool.imap_unordered(_gen_worker, jobs), 1):
            if error is not None:
                failures.append((index, error))
                print(f"\rerror: ELF {index} (seed {base_seed + index}) failed: {error}", file=sys.stderr)
            if show_progress:
                print(f"\r[{done}/{args.num_elfs}]", end='', file=sys.stderr, flush=True)
    if show_progress:
        print(file=sys.stderr)
    if failures:
        print(f"{len(failures)} of {args.num_elfs} ELFs failed.", file=sys.stderr)
        return 1
    return 0


def cmd_designs(args) -> int:
    for name, t in DESIGNS.items():
        print(f"{name:<9} isa={t.isa:<9} priv={t.privlvs:<3} pmp={'yes' if t.pmp else 'no':<3} "
              f"stop={t.stop_addr:#x} regdump={t.regdump_addr:#x} medeleg={t.medeleg_mask:#x}")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='cascade-gen', description="Cascade RISC-V program generator")
    sub = parser.add_subparsers(dest='command', required=True)

    one = sub.add_parser('one', help="generate a single ELF")
    add_common_args(one)
    one.add_argument('-o', '--output', default='rvprog.elf', metavar='FILE', help="output ELF (default: rvprog.elf)")
    one.add_argument('--seed', type=parse_int, help="random seed (default: random)")
    one.set_defaults(func=cmd_one)

    many = sub.add_parser('many', help="generate a batch of ELFs in parallel")
    add_common_args(many)
    many.add_argument('-o', '--outdir', default='elfs', metavar='DIR', help="output directory (default: elfs)")
    many.add_argument('-n', '--num-elfs', type=int, default=100, metavar='N', help="number of ELFs (default: 100)")
    many.add_argument('--seed', type=parse_int,
        help="seed of the first ELF; ELF i uses seed+i, so it equals `one --seed <seed+i>` (default: random)")
    many.add_argument('-j', '--jobs', type=int, default=os.cpu_count(), metavar='N', help="parallel processes (default: number of CPUs)")
    many.set_defaults(func=cmd_many)

    designs = sub.add_parser('designs', help="list the built-in design profiles")
    designs.set_defaults(func=cmd_designs)
    return parser


def main(argv=None) -> int:
    args = make_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
