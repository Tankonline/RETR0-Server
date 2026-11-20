# Reference set

These are the project's **working documents**, published as they were kept during the work (sanitised of personal
paths). Every finding has an ID, evidence and a confidence label. They are dense; the [guide](../README.md) is the
readable entry point and links here for details.

Paths inside these documents refer to the project's internal folder layout (`02_NATIVE_ENGINE/`, `08_TESTING/`,
`SCRIPTS/`, `06_RECONSTRUCTION/`, …). Only the server, client patches, tests and some tools from that layout are in
this repository; analysis outputs, Ghidra databases and decompiler exports are not published.

| Document | IDs | Contents |
|---|---|---|
| [MASTER_REVERSE_ENGINEERING_REPORT.md](MASTER_REVERSE_ENGINEERING_REPORT.md) | K-xx | Index and key confirmed findings |
| [00_INITIAL_ASSESSMENT.md](00_INITIAL_ASSESSMENT.md) | | Starting environment, tools, first inventory |
| [P1_ANDROID_LAYER.md](P1_ANDROID_LAYER.md) | | DEX census, manifest, boot path, signing |
| [P2_NATIVE_ENGINE.md](P2_NATIVE_ENGINE.md) | | Native libraries, symbols/RTTI, third-party code, Ghidra setup |
| [JNI_MAPPING.md](JNI_MAPPING.md) | | Java ↔ native bindings |
| [NATIVE_FUNCTION_CATALOGUE.md](NATIVE_FUNCTION_CATALOGUE.md) | | Function → original source-file attribution |
| [ENGINE_ARCHITECTURE.md](ENGINE_ARCHITECTURE.md) | | Startup, frame loop, scenes |
| [PHYSICS_ANALYSIS.md](PHYSICS_ANALYSIS.md) | PH-xx | Timestep, integration, tyres, suspension |
| [RACE_SYSTEM_ANALYSIS.md](RACE_SYSTEM_ANALYSIS.md) | | GameMode hierarchy, race state |
| [VEHICLE_SYSTEM_ANALYSIS.md](VEHICLE_SYSTEM_ANALYSIS.md) | VH-xx | `.nct` car data, appearance records |
| [SAVE_SYSTEM_ANALYSIS.md](SAVE_SYSTEM_ANALYSIS.md) | SV-xx | Save files, container, body, player name |
| [NETWORKING_ANALYSIS.md](NETWORKING_ANALYSIS.md) | NW-xx | Stacks, endpoints, CloudCell protocol, every sub-sync |
| [ASSET_DOWNLOAD_PROTOCOL.md](ASSET_DOWNLOAD_PROTOCOL.md) | AD-xx | Asset lists, packs, range rules |
| [ASSET_FORMAT_INVENTORY.md](ASSET_FORMAT_INVENTORY.md) | AF-xx | Every game-data file format |
| [STORE_PRESERVATION_GRANTS.md](STORE_PRESERVATION_GRANTS.md) | SP-xx | Store, gifts, the non-purchase award, the patch |
| [RETR0_SERVER_OVERVIEW.md](RETR0_SERVER_OVERVIEW.md) | | The server as operated by the project |
| [RUNTIME_TEST_PLAN.md](RUNTIME_TEST_PLAN.md) | runs 1–29 | Every emulator test run |
| [TOOLCHAIN_AND_REPRODUCIBILITY.md](TOOLCHAIN_AND_REPRODUCIBILITY.md) | | Exact commands and tool versions |
| [FINDINGS_LOG.md](FINDINGS_LOG.md) | | Chronological findings |
| [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md), [UNRESOLVED_FUNCTIONS.md](UNRESOLVED_FUNCTIONS.md) | Q-xx | Open items |
| [RECONSTRUCTION_ROADMAP.md](RECONSTRUCTION_ROADMAP.md) | | Task tracker |
| [DECOMPILATION_PROGRESS_AUDIT.md](DECOMPILATION_PROGRESS_AUDIT.md), [COMPLETE_CPP_RECONSTRUCTION_PROGRESS.md](COMPLETE_CPP_RECONSTRUCTION_PROGRESS.md) | | Coverage and reconstruction progress |
| [BUILD_SYSTEM_AND_GRAPHICS_DEPENDENCIES.md](BUILD_SYSTEM_AND_GRAPHICS_DEPENDENCIES.md) | | Build-system audit |
