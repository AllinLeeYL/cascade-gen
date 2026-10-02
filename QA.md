**Question**: 

How does Cascade know when to terminate the simulation? It does not define `.tohost` and `.fromhost` symbol. Normally both the ISA simulator and RTL simulator hangs.

**Answer**:

Cascade doesn't use the HTIF tohost/fromhost protocol. Spike and the RTL sim each stop in their own way, and neither one needs the program to halt itself. The program ends in a `jal x0, 0` self-loop on purpose, and the harness stops each simulator from outside.

1. Spike: debug-mode script stops at a known PC

Spike always runs with `-d --debug-cmd=<file>` (fuzzer/common/spike.py:137-144). Because Cascade generates the program, it knows the address of the final basic block (fuzzerstate.final_bb_base_addr). The generated command file looks like:

```
until pc 0 0x80000000
until pc 0 <pc of each producer>   ; reg 0 xN   (register values needed to resolve control flow)
...
until pc 0 <SPIKE_STARTADDR + final_bb_base_addr>
reg 0                               ; dump final int regs
freg 0 ft0 ...                      ; dump final FP regs
q
```

The q makes Spike quit once it reaches the final block, so the self-loop never actually runs (spike.py:60-90, called from spikeresolution.py:279). The pc-trace variant uses r 1 repeated N times and then q (spike.py:94-114). As a backstop, subprocess.run(..., timeout=get_spike_timeout_seconds()) kills Spike if it runs too long (spike.py:246-255).

For Spike, the ELF's final block is just jal x0, 0 (finalblock.py:94-97, finalblock_spike_resolution). The comment there says Spike can't handle stores to the signaling addresses.

2. RTL: a store to a magic MMIO address, seen by the testbench

For the RTL ELF, the final block (finalblock.py:20-92) does this:
1. It runs li to load regdumpaddr into a register, then stores each of x1…xN (and the FP regs) to that address, with a fence after each store.
2. It runs li to load stopsigaddr and then sd/sw x0 to that address.
3. It runs `jal x0, 0` to spin forever.

regdumpaddr and stopsigaddr are set per design in <design>/meta/cfg.json (common/designcfgs.py:61-69). The memory model in each design's testbench watches for writes to those addresses. It prints Dump of reg xNN: 0x… for register-dump writes and Found a stop request. for the stop write, then ends the sim. The Python side only parses stdout: is_stop_successful = 'Found a stop request.' in exec_out.stdout (fuzzsim.py:50, 113).

If the stop write never arrives (because of a hang or a bug), two bounds end the run:
- SIMLEN: the C++ tick loop runs at most this many cycles (design-processing/common/dv/ticks.h:31-41). The value is MAX_CYCLES_PER_INSTR(30) * num_instrs + SETUP_CYCLES(1000) (fuzzsim.py:24-26). A run that hits the limit without printing the stop message is reported as a failed stop.
- A wall-clock timeout on the ModelSim subprocess: min(4*simlen + 20, 1800) s (fuzzsim.py:107).

Why your sims hang

The program really does loop forever by design. If you run Spike directly (spike foo.elf) without the --debug-cmd script, it spins in the jal 0 loop. Without tohost it also has no HTIF exit path. If you run an RTL sim whose testbench doesn't watch stopsigaddr (for example a stock CVA6/Rocket harness that waits on tohost), the stop store is just a normal memory write, so it spins too. You need either Cascade's per-design testbench with SIMLEN set, or Spike driven by a debug script that ends in q.

One caveat: the testbench code that matches stopsigaddr lives in the per-design repos (../../cascade-designs/..., from design_repos.json), and those aren't checked out on this machine. So I've described that side from the strings and config the fuzzer depends on, not from reading the SV/C++ source.

---

**Question**: 

I observed that Cascade only defines regdump_addr and stop_addr for rocket, boom, and vecriscv, but not for cva6, kronos, or picorv32. You mentioned a testbench watches for writes to magic MMIO address. Does it means that Cascade develop a customized testbench for each design? You also mentioned a C++ tick loop. Can this tick loop be used for all designs? Is this ticks.h a customized loop for some specific design?

**Answer**: 

Yes, every design gets its own customized testbench. `ticks.h` is a shared generic helper, but it is not the loop that stops the simulation.

I cloned the design repos from GitHub (cascade-artifacts-designs/cascade-{cva6,kronos,picorv32,chipyard,vexriscv}) into the scratchpad to check this. They aren't checked out locally.

1. CVA6, Kronos and PicoRV32 do define the addresses

They just use addresses near zero, which are easy to read as "not set":

┌────────────────────────┬─────────────┬─────────────┬───────────────┐
│         Design         │ stopsigaddr │ regdumpaddr │ fpregdumpaddr │
├────────────────────────┼─────────────┼─────────────┼───────────────┤
│ cva6, kronos, picorv32 │ 0x0         │ 0x10        │ 0x18          │
├────────────────────────┼─────────────┼─────────────┼───────────────┤
│ vexriscv               │ 0x20        │ 0x10        │ 0x18          │
├────────────────────────┼─────────────┼─────────────┼───────────────┤
│ rocket, boom           │ 0x60000000  │ 0x60000010  │ 0x60000018    │
└────────────────────────┴─────────────┴─────────────┴───────────────┘

These come from each repo's meta/cfg.json. Rocket and BOOM are different because their wrapper sends these writes out through a dedicated MMIO port in the Chipyard SoC. The other designs' wrappers expose the raw data-memory port.

The C++ and SV testbenches hardcode the same constants. For example, testbench.h in cascade-cva6 checks (mem_addr_o & 0x7FFFFFFF) == 0x0. So cfg.json (read by the fuzzer) and the testbench (read by the sim) are kept in sync by hand. Changing one without the other breaks stop detection.

2. What is written per design

Each cascade-<design>/cascade/ repo has:

- src/<design>_tiny_soc.sv: a wrapper around the core with an SRAM. It brings the instruction- and data-memory request signals out as top-level
  outputs (data_mem_req/we/addr/wdata/strb, or mmio_* for R can watch them.
- dv/testbench.h: a Testbench class. Its tick() advances the clock and, on each write, compares the address against stop/regdump/fpregdump. It
  returns a tick_req_t of REQ_STOP, REQ_INTREGDUMP, REQ_FLOwith the written data.
- dv/toplevel.cc: the stoppable loop, tb_run_ticks_stoppable. It calls tb->tick() up to simlen times and handles each request type:
  - For a register dump it prints Dump of reg xNN: 0x….
  - On REQ_STOP it prints Found a stop request. and runs RUNMORETICKS_AFTER_STOP more cycles before exiting.
  - If it reaches simlen first, it prints Reached SIMLEN.
- dv/sv/tb_top.sv: the same logic written in SystemVerilog for the ModelSim/Questa flow.
- dv/rfuzz/ and dv/drfuzz/: variants for the coverage-instr

The toplevel.cc loop is nearly identical across designs. Eadoesn't share it. What really varies per design is the portnames and the address constants in testbench.h and tb_top.sv.

3. What ticks.h is

design-processing/common/dv/ticks.h is generic and shared by all designs. It provides:
- get_sim_length_cycles(): reads SIMLEN from the environmendesign can override the default of 5 with LEADTICKS_DESIGN,and TRAILTICKS works the same way.
- cl_get_tracefile(): reads TRACEFILE for VCD/FST tracing.
- tb_run_ticks(): a fixed-length run with no stop detection.

It begins with #include "testbench.h" and then uses the Testbench type. So it is only generic at the source level: it compiles against whichever
design's testbench.h the build puts on the include path. Thr in it is ARIANE_FLUSH_TICKS (CVA6).

This corrects my previous answer. I said the "C++ tick loop In fact ticks.h only reads SIMLEN. The bounded loop thatalso checks for the stop request is tb_run_ticks_stoppable, in each design's own toplevel.cc.

Reusing it for a new core

You can reuse ticks.h and common_functions.cc (the ELF-path lookups from environment variables) unchanged. To add a new core, you'd write:
1. A <core>_tiny_soc.sv wrapper that brings the data-memoryvel.
2. A testbench.h with a Testbench class whose tick() returns tick_req_t and checks your chosen addresses.
3. A copy of any existing toplevel.cc, with only the includ
4. A meta/cfg.json whose stopsigaddr, regdumpaddr and fpregdumpaddr match the testbench.                                                          
The stop address only needs to be one the core will actually issue as a data write. CVA6, Kronos and PicoRV32 use 0x0, which is not mapped to the SRAM, so the store goes out on the bus and the testbench se