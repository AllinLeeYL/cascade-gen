I've cut the repo down to just Cascade's ELF generator, packaged as `cascadegen` with a `cascade-gen` command modeled on rvgen. The programs it generates are byte-identical to the original code's: I captured 24 ELFs from the unmodified code (4 seeds × 6 designs) and regenerated them through the new CLI. All 24 matched except for one ELF header field I changed on purpose (the entry point, below). The changes are staged but not committed.

**What was removed** (188 files, about 307k lines): the RTL simulation flows, program reduction, design processing, the toolchain submodules, the plotting and evaluation scripts, `env.sh`, and all the `CASCADE_*` environment variables. No environment setup is needed any more.

**What was kept:** Cascade's generator code, moved with `git mv` so `git blame` history survives. Its logic is unchanged; the only edits are import paths and swapping the design-config lookups for a `Target` object. The design-specific workarounds (e.g. VexRiscv's CSR avoidance) still apply, keyed on the design name as before.

**Usage:**
```sh
cascade-gen one  --design rocket --seed 42 -o rvprog.elf
cascade-gen many --design rocket -n 1000 --seed 0 -o elfs -j 16
cascade-gen one  --design generic --xlen 32 --isa i,m,c --priv mu
cascade-gen designs
```
- **Designs:** the built-in ones are rocket, boom, cva6, vexriscv, kronos and picorv32. Their settings come from each design's upstream `cfg.json`. Any other name gives a generic core with no workarounds.
- **Overrides:** you can change the ISA, privilege levels, PMP, misaligned-access support, and the boot, stop and register-dump addresses.
- **Seeds:** ELF `i` in a batch uses seed `seed+i`, so it is identical to `one --seed <seed+i>` (I checked this).
- **Metadata:** each ELF gets a JSON file with its parameters, the final-block address and spike's expected final register values. It lists only the registers Cascade's own checker compared, so your framework can use it as the oracle.
- **Speed:** 200 ELFs took about 3 seconds on 8 processes.
- **Tests:** `tests/test_golden.py` pins the 24 verified outputs by hash, so any change to the generation logic will fail the test.

**Where the output differs from the original:**
- **ELF entry point:** the original wrote `0` there instead of the boot address. Cascade's testbenches ignored it, but spike and other loaders jump to it. It's now the boot address.
- **medeleg mask:** Cascade measured this by simulating each design's RTL, which is no longer possible here. It's now `--medeleg-mask`, defaulting to spike's `0xb3ff`. It only matters for cores with supervisor mode, so for an exact Rocket/BOOM/CVA6 baseline you need to pass the real mask.
- **Batch parameters:** in `many`, each program's random parameters (memory size, block count, privileges) now come from its own seed rather than one shared random sequence. The distribution is the same.

**Things to know:**
- **Spike is required.** Cascade runs every program on spike once during generation, so this can't be avoided.
- **The `--check` option fails for a few programs even in the original code.** On rocket/boom seed 3, register `x19` is off by one, probably a retired-instruction count thrown off by the padding after compressed instructions. Batch generation in upstream Cascade runs with the check off, which is also the default here.
- **Running the tests in your `ml` environment:** an unrelated pytest plugin there crashes on load. Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests` or a fresh venv.
