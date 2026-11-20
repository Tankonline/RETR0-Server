# Physics and Simulation Analysis

Last updated: 2026-11-18 · Status: **timestep, complete substep and world-step phase order (both ABIs, §2c), world-step structure, fixed-point position integration and car-car collision broadphase confirmed (arm64). Force, tyre and suspension internals not yet analysed.**
Addresses are ELF virtual addresses (Ghidra = ELF + image base: arm64 `0x100000`, armv7 `0x10000`). Evidence files are under `02_NATIVE_ENGINE/ANALYSIS/PHYSICS/` and `…/GAME_SCENE/`.

## 1. Timestep model

| ID | Finding | arm64 | armv7 | Evidence | Confidence |
|---|---|---|---|---|---|
| PH-01 | **The race simulation runs at a fixed 16 ms step (62.5 Hz)** with an accumulator: `acc += dt; while (acc >= STEP) { substep(STEP); acc -= STEP; }`. The remainder carries into the next frame | `0xb150d0`; acc at `play+0x104f8` | `0x53e7f0`; acc at `play+0xe100` | Pseudocode of both; `STEP` is read from a `.rodata` int = **16** (arm64 var `0x5057a4`, armv7 `0x39b510`) | CONFIRMED |
| PH-02 | A runtime flag (`.bss`, arm64 GOT `0x1f6f2e0`) replaces the frame dt with `STEP` (one substep per frame, deterministic) | `0xb150d0` | `0x53e7f0` | Pseudocode `if (flag) dt = STEP` | CONFIRMED (behaviour); the flag's purpose (replay or automation) is unknown |
| PH-03 | Inside each substep, every active car slot receives `0x133b0a4(slot, STEP, play)` | `0x133b0a4` | `0xb6e966` (`FUN_00b7e966`) | Loop over `n_active` slots, stride 0xaa0 (arm64) / 0x928 (armv7) | **Corrected:** this is the per-car **camera/view** update, not physics. Its subtree references `Car became not visible - occluded crest`, `Follow`/`NoFollow`, `Saved cam %d`, `Restored cam %d` and `gridPosition`; it switches camera mode every 7,500 ms in some modes and runs a damped camera spring (ω²=20, damping 8.05). HIGH |
| PH-07 | **The physics world step** is `0xb15684(play)`, called once per 16 ms substep (when race sub-state ≠ 5 and the mode allows it) | `0xb15684` | `0x53ec04` (`FUN_0054ec04`, same loop position) | Pseudocode (§2a) | CONFIRMED (arm64); armv7 internals not yet compared |
| PH-04 | After the loop, each car gets `0xc29b18(car, n_steps*STEP, playerCar)`, and the function returns `n_steps*STEP` (simulated ms this frame) | `0xb150d0` | | Pseudocode | CONFIRMED (flow); role [likely] post-step interpolation/visual sync — MEDIUM |
| PH-05 | Upstream, the play state scales frame dt by a game-speed factor: `dt_s = (int)(powf(a, t) * powf(b, 1-t) * dt + 0.5)`, where `t` = elapsed/duration at `play+0x104f0/0x104ec` (a slow-motion style blend) | `0xb16024` | | Pseudocode | CONFIRMED (math); purpose MEDIUM |
| PH-06 | The top-level frame dt (ms) is clamped to 100 ms before it reaches the play state (`system_share.cpp` Update) | `0x1405868` | correlated | ENGINE_ARCHITECTURE §5.3 | CONFIRMED |

**Consequence for reconstruction:** the physics is frame-rate independent at 62.5 Hz. A reimplementation should keep a 16 ms fixed step plus accumulator to reproduce the original handling and lap-time behaviour.

## 2a. Physics world step `0xb15684(play)` (arm64, CONFIRMED structure)

`STEP = 16` and `INV = 0x10000 / STEP` (= 4096, a 16.16 fixed-point reciprocal) are passed to the phases.

```
for each of 43 car slots:  A  0x1585a2c(slot->phys(+0x280), slot, STEP)      uses atan2f/sincosf (orientation/steering)
for each car slot:         B  0xc28338(slot, STEP, INV)                      -> 0x1573600 (10.9 KB, largest), fmodf
                              0xb16cd8(play);  0x98b2bc(globalObj, STEP)
for each car slot:         C  0xc28758(slot, STEP); 0xc28f90(slot, STEP, INV) strings: IsBlocked, eSpeedLimiting, m_fAccelerationInput (control input)
                              0xc4df5c(play+0x5510)                         ordering list of 43 car pointers
inactive cars: zero body fields (+0x124, +0x100..0x108, +0x134)
car-vs-car pairs i<j from play+0x5510, both active (+0x6cc==0, +0x6da!=0):
     if |Δx|,|Δy|,|Δz| < 0x5dc (1500 units) on car+200/+0xcc/+0xd0
        D  0x1595e98(slot_i->phys, car_i, car_j, STEP, INV)   collision + damage ("Player damage: type:%s new damage:%d")
for each car slot:         E  0x1587000(slot->phys, slot, STEP, INV, 0, 0)   integration (PH-08) -> 0x1587600 (4.2 KB), 0x1589638 (6.5 KB), …
counter++ (max 1000); 0x98b38c(globalObj, STEP)
```

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| PH-08 | **Position integration is exact fixed-point.** Per axis: `acc = frac + vel_int*dt_ms; pos = car_pos + (acc >> 10); frac = acc & 0x3ff`. Velocity ints at `body+0x100/0x104/0x108`, new position at `body+0xd0..0xd8`, remainder at `body+0xdc..0xe4` (`body = *(phys+8)`) | `0x1587000` pseudocode | CONFIRMED |
| PH-09 | Float views of velocity use `vel_int / 256`. Rotation-like matrices elsewhere use `/16384` (2^14) and other fields `/65536`. The engine mixes integer fixed-point state with float force maths | Constants `0.00390625`, `6.1035156e-05`, `1.5258789e-05` | CONFIRMED (constants); exact units UNKNOWN |
| PH-10 | Accumulated impulses (`body+0x1d0..0x1d8`, /256) are added to velocity, and the resulting speed is **capped at max(pre-impulse speed, 1.0)**, so impulses can redirect but not increase speed. The step then re-integrates | `0x1587000` | CONFIRMED (math); design intent HIGH |
| PH-11 | Car-car collision uses an axis-aligned proximity test of 1500 units per axis, then a narrowphase/response function that applies damage | `0xb15684`, `0x1595e98` subtree | CONFIRMED |
| PH-12 | The physics compilation unit(s) lie in arm64 `0x1573600`–`0x159c158`, between `CarLightGlows.cpp` and `CarReplay.cpp` in the alphabetical link order. No assert strings. The literal string `CarPhysics` exists in the binary | Link order + B-01 | MEDIUM (that a file named `CarPhysics*.cpp` is here is an inference) |

Units: the relationship `Δpos = (vel_int·dt_ms) >> 10` is CONFIRMED, but the metre scale of one position unit is **UNKNOWN**. Resolve it against track or car data before any reimplementation uses SI units.

## 2b. Rigid body, tyres and drivetrain (arm64; evidence `PHYSICS/arm64-v8a/forces/`)

`body = *(phys+8)` is the per-car physics body (float and fixed-point fields). The functions below are reached from integration phase E `0x1587000`.

### Rigid-body solver `0x1589638(phys, car, dt_ms, …)`

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| PH-13 | Four wheel contact points at `(±0.5·body[+0xee4], ±0.5·body[+0xee0])`. Index bit 0 = left/right, index > 1 = the other axle. [likely] `+0xee4` = track width, `+0xee0` = wheelbase | Loop over 4 wheels, sign selection | CONFIRMED (geometry); field names MEDIUM |
| PH-14 | Per-wheel contact force and moment come from one of **two tyre/contact models**: `0x158d098` (A) or `0x158d898` (B), selected by the byte flag at `.data 0x1f8ac13` (GOT `0x1f79e30`). **Its initial value is 1 → model B is the default**; model A runs only if the flag is cleared at runtime (who clears it is UNKNOWN). The flag sits in a run of initialised-to-1 byte flags `0x1f8ac10`–`0x1f8ac15` ([likely] physics feature switches). Results are summed into total force F and moment T. Four more force contributions come from `0x158e220` with short parameters at `body+0xcb0/+0xcf0/+0xd30/+0xd70` | Pseudocode; flag byte read with lief | CONFIRMED (structure and default) |
| PH-15 | A wheel is **in contact** (`+0x930`, count at `body+0xebc`) if its suspension compression is > 0 and the contact-normal dot product is > 0.5 | Pseudocode | CONFIRMED |
| PH-16 | **Linear velocity:** `v += dt·F/m`, vertical `v_z += dt·(F_z − m·g)/m`; mass is a float at `body+0xedc`; **g is a runtime double** (global object `+0x63a8`, copied to `+0x63a0`). Velocity is stored as ints (×256) | Pseudocode | CONFIRMED |
| PH-17 | **Angular velocity** (`body+0x12c/0x130/0x134`) is stored as ints in **2^-24 revolutions per millisecond**: `ω[rad/s] = int · 2^-24 · 2π·1000`, converted back by `× 2670.1768 = 2^24/(2π·1000)`. It is updated by a world-frame 3×3 matrix (inverse-inertia form) applied to T | Constants `5.9604645e-08`, `6283.1855`, `2670.1768` | CONFIRMED (encoding); inertia-matrix source HIGH |
| PH-18 | **Orientation is integrated in 24-bit binary angle units** (2^24 = one turn): `angle += ω·dt_ms·0.001/(2π)·2^24`. This is skipped when fewer than 4 wheels touch and the angular change is small (`|Δ|² ≤ 4`) | Constants `0.15915494`, `16777216.0` | CONFIRMED |

### Tyre model A `0x158d098` (per wheel)

| ID | Finding | Confidence |
|---|---|---|
| PH-19 | Tyre forces only apply when the contact normal is within **30°** of the wheel's up axis (`dot ≥ 0.866`) | CONFIRMED |
| PH-20 | **Surface grip μ** comes from a 16-bit material-flags word at the contact: default 1.0; bit 14 → 0.8; bit 13 → 0.65; bit 12 → 0.6; bit 11 → 0.7; sign bit (bit 15) → 0.5. Which surfaces these are (grass, gravel, kerb, wet…) is UNKNOWN (track data) | CONFIRMED (values); surface names UNKNOWN |
| PH-21 | **Friction limit:** `F_max = m · μ · k_wheel · c · 0.25 · g`, where `k_wheel` is a per-wheel float and `c` = 1.0 or 0.7 by a per-wheel flag. Each wheel uses a **fixed quarter of the weight** here; no dynamic load transfer appears in this formula | CONFIRMED (formula); `k_wheel` and `c` meanings UNKNOWN |
| PH-22 | Low slip speed (`|v_slip|² < 49`): lateral force from `0x158e5bc`, clamped to ±F_max | CONFIRMED |
| PH-23 | Otherwise **slip-angle curve**: `α = |slip| · 57.2958` (degrees); `F = 1500·α + 200·max(α − 6, 0)`. If `F > F_max`, it blends toward `1.1·F_max` (exact blend clamp uncertain in the pseudocode). The sign follows the slip; the per-wheel "gripping" flag is `F/F_max ≤ 1` | CONFIRMED (constants and structure); blend detail MEDIUM |
| PH-24 | Non-tyre contact branch: a force proportional to `μ·m·(projected relative velocity)/(sum of 4 wheel loads)`, limited to `1.5·μ` | MEDIUM |
| — | Model B `0x158d898` uses similar constants (0.6/0.65/0.7/0.8/0.866) plus 0.26 and 0.602; not yet compared in detail | — |

### Drivetrain `0x1588cf8` and mass-dependent per-wheel update `0x158afdc`

| ID | Finding | Confidence |
|---|---|---|
| PH-25 | Drivetrain: wheel angular speeds decoded with PH-17's encoding; wheel circumference `2πr`; a front-axle 0.75 factor; **500 rpm threshold**; gear ratio from `CarDesc` (`0xc67338`); a clutch-style ramp `(rpm − 500)/500 · 0.5 · ratio`; 0.95 / 1.05 rev-matching factors; it calls the engine/gear helpers `0x15a4334`, `0x15a4cf8`, `0x15a5a18` | CONFIRMED (constants and calls); exact semantics MEDIUM |
| PH-26 | **Car mass is stored in pounds** in the car description (`CarDesc` at `car->desc(+0x278)->…+0x4938`, int at `+0x5dc`) and converted by `× 0.453592`. `0x158afdc` is the vertical integration and suspension-displacement function (PH-37..40); the `v²·k·7/mass_kg` term is the downforce acceleration | CONFIRMED |

**Revision of §4:** `0x15a5a18` (gear speed) is also called by the drivetrain `0x1588cf8`. The `0x15a4xxx`–`0x15a8xxx` engine/gearbox model is therefore **shared by physics and audio**. The earlier "engine-sound only" reading of the debugger at `0x15a85d4` is downgraded from HIGH to MEDIUM.

### Tyre model B `0x158d898` (default, PH-14)

| ID | Finding | Confidence |
|---|---|---|
| PH-27 | It shares model A's surface μ table (1.0/0.8/0.7/0.65/0.6) and the 30° contact rule (`0.866`) | CONFIRMED |
| PH-28 | It adds a **longitudinal drive/brake term**: values from car fields `+0x7f0` / `+0x7f4` via `0xc2aaf4` / `0xc2abe4` / `0xc2aca0`, converted as `(value/256) / (dt_ms·0.001)` (impulse per step → force) | CONFIRMED (structure); which is drive and which is brake MEDIUM |
| PH-29 | It adds an **aerodynamic drag term** `−0.8 · a · b · v² · 0.602 · 0.26 / m`. **0.602 = ½·ρ_air with ρ = 1.204 kg/m³** (sea-level air at 20 °C), and **0.26 is consistent with a drag coefficient Cd**. `a`, `b` are /256 car fields ([likely] frontal-area terms) | Constants CONFIRMED; physical identification HIGH. This suggests the float physics uses **SI units (m, s, kg)**: MEDIUM until the position scale is resolved |

### Suspension, ground and wall contact (`0x1587600` and callees)

| ID | Finding | Confidence |
|---|---|---|
| PH-30 | `0x1587600` is the **per-wheel ground-contact driver**. For 4 wheels it queries the track through `0x9a7688` (a functor dispatcher next to `CGroundCollision.cpp`) on the world collision object (`world+0x54b8`), adds a speed-scaled road "rumble" (`sinf(x·π)·0.03`, `(|v|−10)/18`) and a `sinf(angle)·1966` offset, then runs the wall/contact handlers | CONFIRMED (structure) |
| PH-31 | **Wheel mount points** come from the car description: `desc + 0x33b0 + wheel·0x18` (24-byte entries, floats scaled ×8), rotated by the body orientation (`0x15857f8`) | CONFIRMED |
| PH-32 | **Suspension travel check** (`0x158547c`): a wheel counts while `ground_gap ≤ 1.1 × travel`, where `travel` is field `+0x24` of the car's **suspension-data object** (`CarDesc + 0x670`, [likely] from `*.suspensiondata.nct`), with body defaults as a fallback | CONFIRMED (formula); data-file link MEDIUM |
| PH-33 | **Wall/barrier contact** (`0x1590458`, `0x1590950`): a contact with `|n·up| ≤ 0.4` is treated as a wall, with a scrape response factor `0.85 + 0.13·x`. Effects go through `0xc0d510` (global effects manager, given speed and impact); speed > 1000 sets a per-wheel scrape/damage flag (`0xc2d700(car, wheel, 1)`) | CONFIRMED (structure); unit of the 1000 threshold UNKNOWN |
| PH-34 | **Post-contact limits** (`0x1590fd4`): linear speed is capped at **140** and angular speed at **4** (rad/s, decoded with PH-17); an event fires if the impact speed is < −2 | CONFIRMED (constants); if velocity is m/s, 140 m/s ≈ 504 km/h (MEDIUM) |
| PH-35 | Orientation matrix is rebuilt from three 24-bit car angles (`car+0x104`, `+0xfc`, `+0x100`) with `(int>>8)·360/65536` degrees, composed of three axis rotations (`0x1586024`) | CONFIRMED |
| PH-36 | **Vertical dynamics and suspension are kinematic; there is no spring/damper force.** Resolved 2026-11-14: see PH-37..PH-41. Neither tyre model produces a normal (vertical) force term: model B outputs only the in-plane tyre force and its moment r×F, and `0x158e220` is off-road drag (PH-39) | HIGH (no spring term in the solver, tyre models A/B, contact or integration functions examined; the vertical path is fully accounted for by PH-37/38) |
| PH-37 | **Vertical integration** (`0x158afdc`): effective downward acceleration `a = g + extra`. With the flag at global `+0x6420` set, `extra = v²·k_df·7 / m_kg`, where `v` = `body+0x154`/256, `k_df` = `CarPerformance` getter `0x12f4d44`, and `m_kg` = `CarDesc+0x5dc` (lb) × 0.453592; with the flag clear, `extra = 3·g`. Then `z += v_z·dt/1000 − a·dt²/2000`, `v_z −= a·dt` (×256 ints; `z` = `car+0xd0`, `v_z` = `body+0x108`) | CONFIRMED (formula); `k_df` = downforce coefficient is HIGH (consistent with `TWEAKABLE_CAR_DOWNFORCE_*`) |
| PH-38 | **Ground clamp:** when all four wheels touch (`body+0xec0 == 4`) and the new `z` would fall below the ground plane under the wheels, `z` is snapped to the ground (`ground − offset`) and `v_z` is set from the ground's rise rate (capped at `0x3e900`) | CONFIRMED |
| PH-39 | `0x158e220` is **off-road drag**, not a spring. It is enabled by surface flag bit 12 (the same bit as μ = 0.6). Tangential speed `v_t` is opposed with coefficient `−(0.05 + 0.15·min(v_t/v₀ − 1, 1))`, where `v₀ = 5.555556` (**= 20 km/h in m/s**) while throttle or brake input (`car+0x7f0`/`+0x7f4` > 0.1) or flag `+0x80c` is active, else `v₀ = max(v_t, 0.01)` | CONFIRMED (formula); confirms `+0x7f0/+0x7f4` are driver inputs (HIGH) |
| PH-40 | **Per-wheel suspension displacement is geometric:** `d_i = max(0, (car_z + mount_i − ground_h_i + max(travel_F, travel_R)) − ride_height)`, using `travel_F` = suspension-data `+0x24`, `travel_R` = `+0x34` (`0x158599c` returns +0x24 for wheels 0–1, +0x34 for 2–3) and `ride_height` = `CarDesc+0x526c`; stored per wheel via `0xc2d710` | CONFIRMED |
| PH-41 | **Wheel load signal:** per wheel, the summed vertical contact contribution is smoothed by a 4-sample moving average (ring buffer `+0x938`, sum `+0x948`, index `+0x950 mod 4`, result `+0x94c`; per-wheel blocks of 0x1b8 bytes). Values below **10.0** count as zero. This feeds the in-contact test (PH-15) | CONFIRMED |
| PH-42 | **Units:** `v₀ = 5.555556` (exactly 20 km/h in m/s) and drag `0.602 = ½·1.204 kg/m³` indicate the float velocity is in **m/s** and mass in **kg** | HIGH. The integer position scale still follows from `Δpos = (v_int·dt_ms) >> 10` with `v_int = 256·v[m/s]`, i.e. **1 position unit = 1/250 m = 4 mm** if that relation holds; **Independent check 2026-11-18 (VEHICLE_SYSTEM_ANALYSIS VH-11):** the wheel radii used as `ω = (v_int/256)/r` are real-car radii in metres (2–4 %), and the same function's other branch uses rev/s × 2π, so `v_int/256` is m/s, i.e. `v_int = 256·v[m/s]`, which gives **1 position unit = 4 mm** through the integration formula. Upgraded to HIGH; a track-length check would make it CONFIRMED |

## 2c. Tick phase order: one 16 ms substep, complete (arm64; world step cross-checked on armv7)

Added 2026-11-18. Evidence: `06_RECONSTRUCTION/SOURCE_EVIDENCE/world_step/` (pseudocode of arm64 `0xb15684` and armv7 `0x53ec04`), call trees with string references in `02_NATIVE_ENGINE/ANALYSIS/PHYSICS/arm64-v8a/tick_phases/` (`RETR0_CallTree.java`, read-only, on the `_recovered` project) and earlier trees in `…/fixed_loop/`. Source files come from the B-01 attribution table; "region X .. Y" means the function lies between two attributed functions in the alphabetical link order, so its file is only narrowed down. C++ scheduling: `06_RECONSTRUCTION/SOURCE/sim/WorldStep.{h,cpp}`.

**Per frame** (`0xb150d0`, PH-01..04): profiler marker `0x12d2a70(prof, 2)` → accumulator loop of substeps (below) → after the loop, every car whose appearance flag `0x156440c(desc)` is set (`CarAppearance.cpp`, HIGH) gets `0xc29b18(car, n·STEP, playerCar)` → profiler marker `0x12d2bd8(prof, 2)` → return `n·STEP`.

**Per substep, in order** (`0xb150d0` loop body):

| # | Call | What it does | Confidence |
|---|---|---|---|
| 1 | `0x12c4c10()` then `0x12c4c84()` when `play+0x118` is clear | A static-singleton getter and an **empty** function: a hook compiled out of this build (region `Wrapper.cpp` .. `fmProfiler.cpp`) | CONFIRMED (empty) |
| 2 | `0xf1c0a8(play+0x10d90, STEP)` | If the game-mode object (`+8`) exists: its virtual slot **+0x170** (pre-substep). Region `GameMode.cpp` .. | CONFIRMED (dispatch); the slot's name UNKNOWN |
| 3 | `0xb1495c(play, 1)` | **Sorts the 43 cars by track position** into the order list `play+0x5510` and writes each car's index to `car+0x850`. Key: the car's track-progress value `body+0x1a8` relative to car slot 0, wrapped to ±half of `body+0x198`; tie-break `body+0x1c8`. Cars in state 3 or 10 (`car+0x6d4`) or disabled are handled separately | CONFIRMED (structure); `+0x198/+0x1a8` = track length / progress is HIGH (also used that way by `0xb16cd8`); exact handling of excluded cars MEDIUM |
| 4 | **World step `0xb15684(play)`** when `(!play+0x118 ‖ play+0x119) && race sub-state (+0x1b18) ≠ 5 && (mode object play+0x10d88 is null ‖ its vfunc +0x60 returns true)` | See the next table | CONFIRMED |
| 5 | `0x115bd58(play+0x128, play, STEP)`, `0x115be70(play+0x128, play, flag, STEP)` | Two exponential smoothing filters on the object at `play+0x128`: a 3-D point with time constant 1/15 s, and an angle with a time constant read from a global double. `flag` = race sub-state 4 and player-car mode 1. The object's role is UNKNOWN (region `ImageResManager.cpp` .. `JobSystem`) | CONFIRMED (math); role UNKNOWN |
| 6 | `0x1344518` / `0x1344618(playerCar, play)` | Conditional one-shot calls driven by two objects from `play+0x10558` and timers `play+0x10c9c/0x10ca0` (region `RaceCamera.cpp`) | MEDIUM (camera-related by location only) |
| 7 | for each viewed car (1, or the split-screen count): `0x1346e9c(angle, car, flag)` then `0x133b0a4(car, STEP, play)` | Per-car **camera** (PH-03) | HIGH |
| 8 | `0xf1c0b8(play+0x10d90, STEP)` | Game-mode virtual slot **+0x178** (post-substep) | CONFIRMED (dispatch) |
| 9 | `0x1319878(...)`, `0x12f06c4(..., STEP)` under the same gate as #4 | Both are **empty** in this build | CONFIRMED (empty) |

**Inside the world step `0xb15684`** (same order on armv7 `0x53ec04`, which inlines the ML post-hook):

| ID | Phase | Function (arm64 / armv7) | What it does | Confidence |
|---|---|---|---|---|
| PH-43 | A, all 43 slots | `0x1585a2c` / `0xd3559c` | Orientation/steering pre-step (atan2f, sincosf; calls the wheel-travel check `0x158547c` and the orientation builder `0x1586024`) | MEDIUM (role) |
| PH-44 | B, all slots | `0xc28338` / `0x612abc` | Per-car state: wheel spin angles (`fmodf(angle + v/r·dt, 2π)` for 4 wheels), the 10.9 KB `0x1573600` evaluation, a 4-sample vertical-rate average (`0x158247c`), body updates `0x15862b0`/`0x1586310`. Skips disabled cars; copies the pause flag `play+0x1ad9` into `car+0x691` | CONFIRMED (structure); role MEDIUM |
| PH-45 | — | `0xb16cd8` / `0x53fd70` | **Car-pair closing-gap / time-to-contact estimate** for cars on the same track section and in the same group (`car+0x694`), using widths `body+0xed4` and speeds `body+0x154`; reads the setting `NewAIOnAllTracks` | MEDIUM |
| PH-46 | — | `0x98b2bc` / `0x419194` | Only if the **machine-learning agent** object exists (arm64 `.bss 0x1f94f30`): mode 1 sends sensor data over UDP (`MachineLearningAgentServer.cpp`); mode 2 records a frame (36,000 frames × 0x150 bytes = 9.6 min at 62.5 Hz) | HIGH. A developer/research tool; whether a shipped build ever creates the object is UNKNOWN |
| PH-47 | C, all slots, **two calls per car** | `0xc28758` then `0xc28f90` / `0x612e54` then `0x613604` | C1: driver-input path (writes `car+0x7f0`/`+0x7f4`, which PH-39 shows are throttle/brake inputs). C2: **AI driving** ("IsBlocked", "eSpeedLimiting", "m_fAccelerationInput", "m_fBrakingInput", AI debugging output) | C2 HIGH; C1 MEDIUM |
| PH-48 | — | `0xc4df5c` / `0x63016c` | **Slipstream detection** over the order list: for each pair in the same group, projects the relative position onto the leading car's direction and side axes, accepts `0 ≤ along ≤ 1` and `|side| ≤ 1`, then updates both cars' slipstream blocks at `car+0x2e0` (callees reference "slipstream"; region `Car\CarShadowBuffer.cpp` .. `CarAnimation.cpp`) | HIGH |
| PH-49 | — | inline | **Motion of non-simulated cars is zeroed** (`body+0x124`, velocity `+0x100..+0x108`, `+0x134`) when `0xc2d7c4(car)` is false and neither pause flag `play+0x1ad9/+0x1ada` is set. `0xc2d7c4` = `car+0x459 && car+0x45a && (global 0x1f8ac7c ‖ car+0x45b)` | CONFIRMED |
| PH-50 | D | `0x1595e98` / `0xd44098` | Car-car collision (PH-11) for pairs **i < j in the track-order list**, both enabled (`+0x6cc == 0`) and collidable (`+0x6da != 0`), with `|Δ| < 1500` on each axis computed in 32-bit wrap-around | CONFIRMED |
| PH-51 | E, all slots | `0x1587000` / `0xd36938` | Forces and integration (PH-08..42). After each car, if the grid object (arm64 `.bss 0x1f9ba70`) has byte `+0x14` set, `0xc97208` looks the car's float position up in a 3-D cell grid and stores the cell pointer in `CarDesc+0x5288` | CONFIRMED (structure); the grid's purpose UNKNOWN |
| PH-52 | — | inline | Step counter (arm64 `.bss 0x1f973dc`): `c = c < 1000 ? c + 1 : 0`. Then the ML recorder post-step `0x98b38c` (mode 2: time += STEP, frame += 1) | CONFIRMED (counter); who reads the counter UNKNOWN |

**Consequences for reconstruction.** (1) AI and driver input (C) run **before** collision (D) and integration (E) in the same substep, so inputs act on the step in which they are produced. (2) Car-car collisions are visited in track order, not slot order; a reimplementation that iterates slots would apply pair responses in a different order. (3) Disabled cars are still passed to every per-car phase, and each phase returns early on `car+0x6cc`.

**Correction to PH-32/PH-40 (CONFIRMED 2026-11-18: the object at `CarDesc+0x670` is the car's appearance record from `carappearances.appearances.nct`, VH-09/VH-10, and the values are real wheel radii, VH-11) (was HIGH since 2026-11-18, VEHICLE_SYSTEM_ANALYSIS VH-06/VH-07 confirms it from two more functions):** phase B spins each wheel by `(speed/256) / suspensiondata[+0x24 front, +0x34 rear] · dt` radians. A divisor that turns linear speed into wheel angular speed is a **wheel radius**, so `+0x24/+0x34` may be the front/rear wheel radii rather than suspension travel. PH-40's displacement formula is also consistent with a radius (`car_z + mount − ground + radius − ride_height`).

## 2. Race-frame call structure (arm64)

```
play-state Update(play, dt)                              0xb16024   [game_state_play_share.cpp region, MEDIUM]
  dt_s = game-speed-scaled dt                            (PH-05)
  0xb16afc(play, dt_s, flag)                             "per-frame presentation" step
     0xb11ca8: sort up to 43 cars by distance to the player car;
               for each: 0xb10d6c(play, car, car+0x450, dt, …)   → per-car AUDIO (engine-sound model, nearest 4 cars at full detail)
               0x15a7e94 / 0x15a7ba8(car+0x450, dt)              → audio/FX sub-objects
     0xb122cc(...) per player car;  0xb121c8 → camera (0xc16648: "splitscreen | track | bumper")
  race time += dt_s                                      (play+0x1b24)
  0xb150d0(play, dt_s)                                   FIXED-STEP SIMULATION (PH-01..04); each substep: world step 0xb15684 (§2a), per-car camera 0x133b0a4 (PH-03)
  for 43 car slots (stride 0xaa0): if !car.disabled(+0x6cc): 0xc29ff8(car, dt_s)   → per-car timers/state (e.g. +0x848 countdown, state 5 → 0)
  … HUD, minimap, cameras and managers with dt
```

Car storage: **an array of 43 car structs** (arm64 size 0xaa0 = 2,720 bytes; armv7 0x928 = 2,344 bytes) at `play+0x5508`. The player car index is at `play+0x54f0` (CONFIRMED: loop bound `0x2b`, stride and index usage in several functions). Note that `play` is the same global system object as in ENGINE_ARCHITECTURE §5 (`+0x1c0` = scene id, `+0x1b18` = race sub-state).

## 3. Physics data inputs (static configuration)

| Evidence | Meaning | Confidence |
|---|---|---|
| Loader functions `0xc58be4`, `0xc5954c`, `0xc5acb0`, `0xc5b164` (just before `CarDataManager.cpp`) reference `.brakes.nct`, `.suspension.nct`, `.suspensiondata.nct`, `.tyres.nct`, `.tyrepacks.nct`, `.wheels.nct`, `.wheelpacks.nct`, `custom.*.nct`, `suspensionbehaviour.suspensiondata.nct`, `car.brakes.nct` | Per-car physics description data are loaded from `.nct` files | CONFIRMED |
| Strings `CarDataManager::loadGearboxData unable to load gearbox data file`, `…loadSuspensionData…` | Gearbox and suspension data loaders | CONFIRMED |
| Gearbox ratio get/set `0xc67338` / `0xc67364` inside `CarDesc.cpp`'s range | The gearbox belongs to the static car description (`CarDesc`) | HIGH |
| 233 `TWEAKABLE_*` names registered in `0x142c318` (e.g. `TWEAKABLE_DRIFT_GRIP_PERCENT`, `TWEAKABLE_SUSPENSION_WEIGHT_SHIFT_LR/BCK`, `TWEAKABLE_CAR_DOWNFORCE_*`, `TWEAKABLE_*SLIPSTREAMING*`) | A global tuning-constant table; values not yet extracted | CONFIRMED (names) |
| `CollisionResponse*` parameters registered in `0x100ad14` (e.g. `CollisionResponseAssistsSteeringPercent`, `…AiLossSteering`) | Collision-response tuning | CONFIRMED (names) |
| `src\CGroundCollision.cpp` (arm64 `0x9a82b4`, `0x9a84ec`) | Ground and track collision code | CONFIRMED (file) |
| `.nct` file format | **Not yet inspected.** Must be checked against the game data before any parser is written | — |

## 4. Corrections recorded during this analysis

| What was assumed | What the evidence shows |
|---|---|
| The ImGui car viewer at `0x15a85d4` ("Gear Speed vs RPM Plot", "Max Torque", "Engine Ramps") inspects vehicle physics | It operates on the `car+0x450` object, which the race loop updates for audio (`0xb10d6c`). **Revised (§2b):** its helper `0x15a5a18` is also used by the drivetrain, so the engine/gear model is shared by physics and audio. MEDIUM |
| `system+0x78` is a scene manager | It is the `AutomationController` (test automation). See ENGINE_ARCHITECTURE §5.3 correction |

## 5. Units and fixed point (observations, to be confirmed in the physics step)

- Car position fields at `car+0x458/+0x45c/+0x460` are converted to float with `* 0.03125` (1/32) for audio distance sorting. [MEDIUM] Positions are stored as fixed-point integers with 1/32 m (or 1/32 unit) resolution.
- Speed for audio: `CarPerformance` getter `0x12f4df4` → `(v * 262144.0 * 1.61) / 3600.0`. [MEDIUM] This is a km/h ↔ mph conversion combined with 2^18 fixed-point scaling.
- The audio engine model uses `value * 900 * (1/65536)` (16.16 fixed point).

## 6. Next steps

1. Verify the position scale (PH-42) against an independent length, e.g. track or car data.
2. Low-speed lateral function `0x158e5bc`; phase B `0x1573600` (10.9 KB, almost no maths: [likely] per-step setup/copy).
3. The value of g (runtime double): who writes global object `+0x63a8` (object at `.bss 0x1fb57f8`).
4. armv7 correlation of `0x53ec04` and the constants above. Establish the position-unit scale.
2. Find which `TWEAKABLE_*` values the step reads (getter calls with constant IDs).
3. Inspect one `.nct` file from the separately held game data, read-only, to establish the container format.
