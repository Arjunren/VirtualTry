# Architecture and implementation plan

## A. Architecture

VirtualTry uses a strict layered design:

- `ui`: PySide6 widgets, drag/drop, previews, status, settings, comparison and save flow.
- `application`: one-worker inference queue, asynchronous image loading, cancellation flags and request IDs.
- `vton`: the stable engine interface plus mock and CatVTON adapters.
- `imaging`: untrusted-image validation, MIME parsing, secure remote fetching and output naming.
- `infrastructure`: hardware discovery, application paths and rotating logs.

The GUI imports the `VTONEngine` abstraction, never upstream CatVTON internals. One service owns one engine instance and a thread pool capped at one inference job.

## B. Recommended VTON model

CatVTON is the selected local model. The official implementation reports under 8 GB of VRAM at 768×1024 with bf16, uses an 899.06M-parameter inference network, and supports upper, lower and overall garment masks. It is simpler than IDM-VTON because the diffusion stage does not require text, pose or parsing inputs; its application still uses DensePose and SCHP to build the automatic person mask.

CatVTON is **non-commercial**: source, checkpoints and demo are CC BY-NC-SA 4.0. They are external dependencies and are not redistributed by this MIT application. StableVITON has the same non-commercial license and substantially more dataset-oriented preprocessing. IDM-VTON uses SDXL, OpenPose, DensePose and human parsing, with a larger runtime footprint.

## C. Verified runtime and dependencies

The official CatVTON installation pins Python 3.9.0. Its current requirements at the pinned commit are recorded exactly in `requirements-catvton.txt`: PyTorch 2.1.2, torchvision 0.16.2, diffusers 0.29.2, accelerate 0.31.0, transformers 4.27.3, xformers 0.0.23.post1 and related packages. CUDA must match the installed PyTorch build. bf16 requires an Ampere-or-newer GPU; otherwise use fp16. CPU is exposed only as a very slow fallback.

The desktop shell uses PySide6 6.8.3 and Pillow 10.3.0. The supported production environment is Windows 10/11, 64-bit, Python 3.9. CatVTON's upstream Windows support has caveats around Detectron2 compilation; Visual Studio C++ Build Tools and a matching CUDA toolkit may be required.

## D. Directory structure

The repository follows a `src/virtual_tryon` package layout. Model source and weights live under ignored `models/` paths. User config and rotating logs live under `%LOCALAPPDATA%/VirtualTry`; generated images remain in memory until Save is chosen.

## E. Drag-and-drop design

Each drop zone inspects Qt MIME formats. Direct image bytes are preferred, followed by local/file URLs, then HTTPS URLs. Clipboard data follows the same parser. All decoding happens in background tasks and passes through Pillow verification, decoded dimension/pixel limits and RGB normalization. Browser URL fetching is optional and uses HTTPS only, DNS validation, pinned validated IP connections, redirect revalidation, MIME/size limits and timeouts.

## F. AI inference flow

Person + garment + explicit category → safe normalization → CatVTON AutoMasker (DensePose + SCHP) → blurred agnostic mask → CatVTON diffusion pipeline → RGB result. The engine loads once and is reused. A UUID identifies every request; stale completions are discarded. Cancellation is cooperative around uninterruptible model forward passes.

## G. Security and privacy

No image leaves the computer unless the user drops an HTTPS browser URL and remote fetching is enabled. There is no telemetry. File extensions are ignored, decoded pixel limits are enforced, image metadata is stripped by RGB conversion, model code is pinned, remote code execution is disabled, and model downloads require explicit license acknowledgement. Logs contain event names, types, durations and request IDs—not image bytes or full input paths.

## H. Implementation plan/status

- Phase 1: complete—native GUI, drag/drop, clipboard, previews, mock engine, background work and tests.
- Phase 2: complete adapter—official CatVTON pipeline integration with explicit external setup and no silent downloads.
- Phase 3: complete baseline—CUDA detection/OOM recovery, cancellation, stale-result protection, comparison, settings, saving and rotating logs.
- Phase 4: complete baseline—PyInstaller recipe, explicit model bootstrap, automated tests and hardened image/URL boundaries. A signed installer and validation on each target GPU remain release-engineering tasks.
