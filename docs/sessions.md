## 2026-04-03 — Phase 0 Complete
**Done:** skeleton app, venv, API smoke test passing
**Decisions:** Python 3.11, Replicate over RunPod, file upload over URL
**Blockers solved:** Python 3.14 incompatibility, NSFW filter, Wikipedia 403
**Next:** Phase 1 Step 1 — drag and drop sketch upload



Session Summary
We started from a completed Phase 0 and built Phase 1 in full — from scratch to a working application. Along the way we solved the classic pip install -e . issue with src/ layout Python projects, understood why QThread exists and how Signals enable thread-safe communication between the background render and the UI, and designed a clean architecture with strict separation of concerns — replicate_client.py has no knowledge of Qt, render_worker.py has no knowledge of the UI, and MainWindow owns all application state.



Session summary
Phase 2 migration session: Built the complete ComfyUI workflow in the local ComfyUI GUI — Animagine XL base model + ControlNet Sketch + IP-Adapter Plus with CLIP Vision. Exported the workflow as API-format JSON (worflow_api_v1.json). Claude Code then created comfyui_client.py (same render_frame() interface as replicate_client.py), a smoke test file, and swapped the import in render_worker.py. Local GPU (GTX 1060) can't run SDXL, so no test run yet. Next step: RunPod account setup + cloud testing.


Session summary
Today we set up the entire RunPod infrastructure — account, Network Volume, SSH keys, GPU Pod with ComfyUI template. Downloaded all 4 models (Animagine, ControlNet Sketch, IP-Adapter Plus, CLIP Vision) and installed the IPAdapter custom node. Ran 3 successful renders directly from ComfyUI in the cloud, and discovered that a face-only reference image + removing color-descriptive words from the prompt significantly improves color accuracy. Pod terminated, models persist on the Network Volume. Next up: Spin up a new Pod, grab the ComfyUI proxy URL, and wire it into the FrameForge desktop app through comfyui_client.py.



Session Summary
Step 4 of Phase 2 migration completed: FrameForge desktop app now connects to ComfyUI on RunPod for cloud-based rendering. Two bugs were fixed along the way — Cloudflare's proxy blocks requests without a User-Agent header (affected all HTTP calls), and one urlopen call in _poll_until_done() was missed during the initial header fix. The full pipeline works end-to-end: sketch upload → ComfyUI inference on RunPod → rendered image displayed in app. Next focus shifts from infrastructure to output quality — the model produces decent results but struggles with color accuracy and character identity, pointing toward prompt engineering and workflow improvements as the next priority.

Session Summary
We solved the CLIP Vision issue — the file existed, but the Unified Loader FaceID's regex pattern was looking for a filename in SD 1.5 format instead of SDXL. We fixed it by copying the file with a compatible name. After that, we installed insightface, connected an InsightFace Loader node, and made the discovery that FaceID doesn't work with anime faces at all — InsightFace is trained exclusively on real human faces. The conclusion: FaceID is a dead end for our use case, the standard IP-Adapter Plus is the right tool, and the focus shifts to automated Danbooru tag generation as the next AI layer.

Session summary
Built and validated a two-stage auto-tagging system that converts sketch images into Danbooru tag strings for Animagine XL 3.1. Stage 1 sends the sketch to Gemini 2.5 Flash (vision) to produce a detailed English description. Stage 2 sends the description plus optional user context to the same model (text-only) to synthesize a structured Danbooru tag set. The POC runs on Gemini's free tier at zero cost. Testing confirmed that Gemini correctly identifies anime characters (including Monkey D. Luffy by name), extracts fine-grained visual details (scar placement, hat damage, clothing layers), and successfully incorporates user scene direction ("sunset, forest background") into the final tags even when those elements are absent from the sketch itself.