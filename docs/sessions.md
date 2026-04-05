## 2026-04-03 — Phase 0 Complete
**Done:** skeleton app, venv, API smoke test passing
**Decisions:** Python 3.11, Replicate over RunPod, file upload over URL
**Blockers solved:** Python 3.14 incompatibility, NSFW filter, Wikipedia 403
**Next:** Phase 1 Step 1 — drag and drop sketch upload



Session Summary
We started from a completed Phase 0 and built Phase 1 in full — from scratch to a working application. Along the way we solved the classic pip install -e . issue with src/ layout Python projects, understood why QThread exists and how Signals enable thread-safe communication between the background render and the UI, and designed a clean architecture with strict separation of concerns — replicate_client.py has no knowledge of Qt, render_worker.py has no knowledge of the UI, and MainWindow owns all application state.



Session summary
Phase 2 migration session: Built the complete ComfyUI workflow in the local ComfyUI GUI — Animagine XL base model + ControlNet Sketch + IP-Adapter Plus with CLIP Vision. Exported the workflow as API-format JSON (worflow_api_v1.json). Claude Code then created comfyui_client.py (same render_frame() interface as replicate_client.py), a smoke test file, and swapped the import in render_worker.py. Local GPU (GTX 1060) can't run SDXL, so no test run yet. Next step: RunPod account setup + cloud testing.
