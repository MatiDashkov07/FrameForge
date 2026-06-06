# FrameForge — Project Snapshot

> **Purpose:** A point-in-time, 100%-accurate record of what the project actually *is* right now — not what was planned, what exists. This is a measuring stick for future progress and raw material for later blog documentation.
>
> **Date of snapshot:** June 6, 2026
> **Last code commit:** `0979bab` — "rmbg complete" — Fri Apr 10, 2026
> **Time since last development:** ~2 months (military service)
> **Author:** Mati
>
> **Methodology note:** This snapshot is built from (a) a Claude Code source inventory run on June 6, 2026, (b) the documented session logs, and (c) the three planning documents. Where something was not verified in this session, it is explicitly marked `[NOT VERIFIED THIS SESSION]` rather than assumed.

---

## 1. One-Line Status

The **old pipeline works end-to-end** (sketch → cloud render → colored anime frame → optional transparent PNG). The **MangaNinja migration is fully planned but zero code written**. The project is paused at the threshold of Saga 0.

This session (June 6) confirmed the app launches and the RunPod render pipeline still works after the 2-month gap. No new technical progress was made by design — the goal was reorientation + this snapshot.

---

## 2. What Actually Works Today (Verified)

| Capability | Status | Notes |
|---|---|---|
| App launches (`python main.py`) | ✅ Verified June 6 | Clean launch |
| RunPod Pod + ComfyUI backend | ✅ Verified June 6 | New Pod spun up, URL updated in `.env`, render confirmed working |
| Sketch upload (drag-and-drop, PNG/JPEG) | ✅ Working | `sketch_drop_zone.py` |
| Reference upload (UI accepts up to 3) | ⚠️ Partial — see §4 | UI accepts 3, **pipeline uses only the first** |
| Auto-tagger (Gemini 2.5 Flash, 2-stage) | ✅ Working | Paid billing active, not free tier |
| Render via Animagine XL 3.1 + ControlNet + IP-Adapter | ✅ Working | The "old pipeline" |
| Before/After result display | ✅ Working | |
| Background removal (RMBG-2.0, local CPU) | ✅ Working | On-demand "Generate Clear PNG", ~35s |
| Export rendered frame / clear PNG as PNG | ✅ Working | |

---

## 3. Actual Source Inventory (June 6, 2026)

From Claude Code's read of `src/frameforge/`:

### UI Layer (`src/frameforge/ui/`)

| File | ~Lines | Role |
|---|---|---|
| `main_window.py` | ~708 | Main Qt window. Owns all UI state, coordinates workers, handles sketch/reference/result display, bg removal, export. Mediator pattern hub. |
| `render_worker.py` | ~128 | Background QThread: auto-tag → ComfyUI render → image download. Emits signals to main thread. |
| `sketch_drop_zone.py` | ~202 | Single-sketch drag-and-drop widget with thumbnail. |
| `reference_drop_zone.py` | ~309 | Drop zone for up to 3 reference images, thumbnails + remove buttons. |
| `bg_removal_worker.py` | ~42 | QThread for RMBG-2.0, mirrors RenderWorker structure. |

### Pipeline Layer (`src/frameforge/pipeline/`)

| File | ~Lines | Role |
|---|---|---|
| `comfyui_client.py` | ~319 | ComfyUI HTTP client: uploads images, injects values into workflow JSON, queues prompt, polls history, returns output URL. |
| `auto_tagger.py` | ~348 | Two-stage Gemini: sketch → description (Stage 1) → Danbooru tags (Stage 2) → assembled prompt. |
| `replicate_client.py` | ~138 | Phase 1 Replicate client. **Superseded** by `comfyui_client.py`, kept in repo. |
| `worflow_api_v1.json` | ~209 | ComfyUI workflow template. **Filename typo ("worflow") is the real filename on disk** — referenced as-is in code. |

### Utils (`src/frameforge/utils/`)

| File | ~Lines | Role |
|---|---|---|
| `background_removal.py` | ~110 | Local BRIA RMBG-2.0 (BiRefNet). Model cached at module level. Must run off main thread. |

### Dependencies (`requirements.txt`)

PySide6 6.11.0 · python-dotenv · replicate *(superseded)* · google-genai · torch + torchvision · transformers · Pillow · timm + kornia · rembg *(test/fallback only)* · httpx + httpcore · pydantic

---

## 4. Render Pipeline — Actual Call Chain

Traced through the real code (not the planned architecture):

```
main_window._on_render_clicked()
  → collects sketch path + params, creates RenderWorker, switches canvas to loading page
  → render_worker.run()  [background thread]
      → auto_tagger.analyze_image()   — Gemini vision: sketch → description
      → auto_tagger.generate_tags()   — Gemini text: description → Danbooru tags
      → auto_tagger.assemble_prompt() — tags + scene direction + quality suffix
      → comfyui_client.render_frame()
          → _ensure_url()        — reads COMFYUI_URL env (default 127.0.0.1:8188)
          → _upload_image() × 2  — POST sketch + reference   ◄── ONLY 1 REFERENCE
          → _build_workflow()    — load JSON, inject filenames/prompt/CN+IP strengths
          → _queue_prompt()      — POST /prompt → prompt_id
          → _poll_until_done()   — GET /history/{id} every 1s (300s timeout)
          → extract output URL from node 151 (SaveImage)
          → download bytes, decode to QImage
          → result_ready.emit(image)
  → main_window._on_result_ready()  [main thread]
  → _show_render() → _display_pixmap()  — scale, setPixmap, switch to result page
```

### The Multi-Reference Gap (Confirmed)

> **Known gap, confirmed by Mati June 6:** The UI lets the user upload **3** reference images, but the pipeline **only uses the first one**. `comfyui_client._upload_image()` is called ×2 (sketch + single reference), and `replicate_client.py` carries the TODO: *"support multiple references via embedding averaging. Currently only the first reference is passed."*
>
> This matters because MangaNinja's whole point is multi-reference. The UI is one step ahead of the pipeline here — which is fine, but it must not be mistaken for working multi-reference support.

---

## 5. Workflow JSON Node Structure (`worflow_api_v1.json`)

| Node | Type | Role |
|---|---|---|
| 144 | CheckpointLoaderSimple | `animagine-xl-3.1.safetensors` |
| 145 | CLIPTextEncode | Positive prompt → conditioning |
| 146 | CLIPTextEncode | Negative prompt → conditioning |
| 147 | EmptyLatentImage | 1024×1024 latent |
| 148 | KSampler | Euler, **cfg=7, 20 steps** |
| 150 | VAEDecode | Latent → image |
| 151 | SaveImage | Output node (this is what gets polled) |
| 152 | LoadImage | Sketch input (filename injected at runtime) |
| 153 | ControlNetLoader | `control-lora-sketch-rank256.safetensors` |
| 154 | ControlNetApplyAdvanced | CN applied, strength injected at runtime |
| 155 | LoadImage | Reference input (filename injected at runtime) |
| 157 | IPAdapterModelLoader | `ip-adapter-plus_sdxl_vit-h.safetensors` |
| 158 | CLIPVisionLoader | `open_clip_model.safetensors` |
| 159 | IPAdapterAdvanced | IP-Adapter applied, weight injected at runtime |

> **⚠️ Doc discrepancy to resolve:** `CLAUDE.md` (Step C) records the sampler as **"Euler a, 28 steps, CFG 7"**, but the actual workflow JSON node 148 reads **"Euler, 20 steps, CFG 7"**. The code is the source of truth here — the JSON says 20 steps / Euler, not 28 / Euler a. Worth reconciling when CLAUDE.md is next updated. `[Flagged — not corrected this session]`

---

## 6. Known Code-Level Issues / Debt

| Where | Issue |
|---|---|
| `worflow_api_v1.json` | Filename typo ("worflow") baked in — code references it literally. Cosmetic, but a portfolio reviewer will notice. |
| `comfyui_client.py`, `auto_tagger.py` | Leftover `print()` debug statements, not cleaned up. |
| `replicate_client.py` | Dead Phase-1 code kept in repo. Decision pending: keep as historical fallback or remove. |
| `main_window.py` ~209, ~238 | Phase 3 placeholders (canvas → timeline; status → QProgressBar). |
| RunPod | **Intermittent silent failure:** occasional renders finish in ~0.05s with no image + 403 on download. Likely silent ComfyUI node error or workflow mismatch. **Unresolved.** |

---

## 7. UI/UX Backlog (`ui-bugs.md`)

Deliberately batched for a dedicated polish phase — not fixed mid-feature:

1. Placeholder text in empty references tab is vertically misplaced (lower-middle, not centered).
2. Redesign reference canvas to a Pinterest-style grid (2 large images/row, hover reveals name + delete).
3. First render doesn't fill canvas; after toggling sketch↔result it shrinks to sketch size — inconsistent sizing.
4. App isn't size-modular — rendered images don't scale with window, so the window can't be shrunk when an image fills the canvas.
5. General UI/UX redesign — identity, colors, style, improved layout, benchmarked against market animation tools.

---

## 8. Cloud Infrastructure (Reference)

- **Provider:** RunPod, On-Demand Pods (not Serverless)
- **Region:** EU-RO-1 · **GPU:** RTX A4000 (16GB) · ~$0.27/hr
- **Network Volume:** `external_turquoise_python` (cosmetic name) — models persist when Pod is terminated
- **Models on Volume:** Animagine XL 3.1 · control-lora-sketch-rank256 · ip-adapter-plus_sdxl_vit-h · open_clip_model
- **Proxy URL:** Dynamic per Pod (`https://{pod-id}-8188.proxy.runpod.net`) — **must manually paste into `.env` as `COMFYUI_URL` each new Pod**
- **Cost discipline:** Terminate the Pod when not actively rendering.

---

## 9. The Big Picture — Where This Sits in the Roadmap

### Established architecture (decided, validated)
- **Compositing pipeline** over single-pass: render character → remove background → composite as separate locked layers.
- **Reference images are the source of truth**, not stored prompts.
- **Validate empirically before building.**

### The pending pivot: MangaNinja migration
A full migration plan exists (`MangaNinja_Migration_Saga.md`), structured as 5 sagas. **None started.** It supersedes Steps B/D/F/G of the old Pipeline Reevaluation roadmap.

| Saga | Goal | Status |
|---|---|---|
| 0 — Spike | Validate MangaNinja on RunPod (test matrix A–F) | **NOT STARTED** ← next action |
| 1 — Backend Migration | Replace IP-Adapter with MangaNinja in pipeline | Not started |
| 2 — Multi-Reference UI | UI manages N references (the gap in §4 gets closed) | Not started |
| 3 — Point Guidance UI | Click-to-link sketch regions ↔ reference regions | Not started |
| 4 — Character Library | SQLite + relative paths, persistent character defs | Not started |
| 5 — Enhancement & Polish | Upscaling, perf, layer export | Not started |

### Key constraints carried into the migration
- **MangaNinja is SD1.5 only** — native 512×512, needs an enhancement step (SD1.5 tiled upscale preferred over Animagine img2img, which risks overriding semantic colors).
- **Old pipeline is kept as a fallback** — not deleted. Validates the modularity principle.
- **Dev machine (GTX 1060)** runs lightweight ops only (rembg, preprocessing, workflow JSON construction). All diffusion stays on RunPod.

---

## 10. The Exact Next Action

Per the migration plan, the immediate next step is the **cheapest possible** one (no RunPod cost):

> **Build the ComfyUI MangaNinja workflow JSON locally (CPU, no rendering)** by importing the example workflow images from the `smthemex/ComfyUI_MangaNinjia` GitHub repo into the local ComfyUI, understanding the nodes, then exporting in API format — ready for a later RunPod spike.

Only *after* the workflow is built does Saga 0's RunPod testing (cost-incurring) begin.

---

## 11. Honest Self-Assessment

Nothing in the current pipeline is at 100%. Every component — base model, ControlNet, IP-Adapter, auto-tagger, background removal — works but has clear, documented limitations. That is expected and fine at this stage. The MVP intentionally resembles existing market tools; the North Star (50 keyframes → 1,000 frames) remains the long-term differentiator, and the architecture is being built so every piece feeds into it.

The single most important thing this snapshot captures: **the project survived a 2-month gap intact, still runs, and has a clear, costed, low-risk next step waiting.**

---

*Snapshot generated June 6, 2026. Next snapshot recommended after Saga 0 completes (go/no-go on MangaNinja).*
