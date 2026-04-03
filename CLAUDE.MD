# CLAUDE.md — FrameForge Source of Truth

> This file is the authoritative reference for Claude Code.
> Read it at the start of every session. Do not contradict it.
> When in doubt, ask — don't assume.

---

## What This Project Is

FrameForge is a **desktop application** that transforms sparse hand-drawn keyframe sketches into fully rendered, production-quality animation sequences.

**One-line pitch:** Draw 20 keyframes → get 1000 animation-ready frames.

**Core philosophy:** The animator draws the acting, the motion, and the creative decisions. FrameForge handles the coloring, detailing, and in-betweening. The artist stays in the driver's seat.

**What it is NOT:**
- Not an AI art generator (does not create original compositions)
- Not a replacement for animators (requires skilled keyframe input)
- Not a text-to-video tool (the artist's sketches are the source of truth)
- Not a startup — this is a passion project and engineering portfolio piece

---

## Current Status

**Phase: 0 — Foundation**
**Date:** April 2026

- [x] Repo created, directory structure established
- [x] Python venv set up, PySide6 installed
- [x] PySide6 skeleton app (first window)
- [x] Cloud API account (Replicate or RunPod)
- [x] First successful API call

Phase 1 (MVP single-frame render) has not started.

---

## Repository Structure

```
FrameForge/                  ← git root
├── .venv/                   ← local only, never committed
├── assets/                  ← test sketches, reference images
├── docs/                    ← links to Docusaurus blog
├── src/
│   └── frameforge/          ← main Python package
│       ├── __init__.py
│       ├── ui/              ← PySide6 windows and widgets
│       ├── pipeline/        ← AI orchestration logic
│       └── utils/           ← shared helpers
├── tests/
├── .gitignore
├── CLAUDE.md                ← this file
├── LICENSE
├── pyproject.toml
└── requirements.txt
```

---

## Tech Stack

| Layer | Technology | Status |
|---|---|---|
| Desktop UI | PySide6 (Qt for Python) | Installed |
| Backend Logic | Python | ✓ |
| Cloud Compute | Replicate API or RunPod Serverless | Not set up yet |
| Base Model | SDXL or Flux | TBD |
| Structure Control | ControlNet (Lineart / Canny) | TBD |
| Style/Color Transfer | IP-Adapter | TBD |

**Open decisions (not yet resolved):**
- Replicate vs. RunPod — test both in Phase 0
- SDXL vs. Flux — Flux is newer but less battle-tested with ControlNet

---

## AI Pipeline (How It Works)

```
User's line-art sketch  ──► ControlNet ──┐
Reference sheet images  ──► IP-Adapter ──┼──► SDXL/Flux diffusion ──► Rendered frame
Optional text prompt    ──► CLIP       ──┘
```

1. Sketch is preprocessed and fed into ControlNet as structural constraint
2. Reference images are encoded by IP-Adapter (extracts identity, palette, style)
3. Text prompt is encoded by CLIP for scene context
4. SDXL/Flux runs diffusion with all three conditioning signals
5. Output is decoded, upscaled if needed, returned to desktop app

**Key principle:** FrameForge does not train any models. It orchestrates existing open-source models via cloud APIs. Engineering challenge = integration, UX, and temporal consistency — not ML research.

---

## Development Phases

### Phase 0 — Foundation (CURRENT)
- Python project structure, venv, CI basics
- PySide6 skeleton app
- Cloud API access (Replicate or RunPod)
- First successful API call: send image → get result

### Phase 1 — MVP Core (Single-Frame Render)
- File upload UI (sketch + references + prompt)
- ControlNet + IP-Adapter orchestration pipeline
- Render request/response cycle with loading states
- Before/after result display
- Export rendered frame as PNG
- Basic settings (render quality, style strength, sketch adherence)

### Phase 2 — Batch & Consistency
- Multi-frame import (sequence of sketches)
- Batch rendering with shared reference/prompt
- Temporal consistency exploration (seed locking, latent anchoring)

### Phase 3 — Timeline & Preview
- Timeline UI with thumbnails and scrubber
- Playback preview
- Frame reordering, deletion, re-rendering

### Phase 4 — In-Betweening
- Frame interpolation (optical flow / diffusion-based / hybrid)
- Handle squash/stretch/smear frame physics
- Export as image sequence or video

### Phase 5+ — Open-Ended
- Background generation from text prompts
- Multi-character scene handling
- Plugin architecture for different AI backends
- Local GPU support

---

## Coding Conventions

- **Language:** Python 3.x
- **UI framework:** PySide6 only — no PyQt5, no tkinter
- **Imports:** absolute imports from `frameforge.*`
- **UI code:** lives in `src/frameforge/ui/`
- **Pipeline/AI code:** lives in `src/frameforge/pipeline/`
- **Shared helpers:** lives in `src/frameforge/utils/`
- **No black boxes:** if you add a library or pattern, be ready to explain the underlying mechanism
- **Tests:** go in `tests/`, mirror the `src/frameforge/` structure

---

## Hard Rules

- **Never commit `.venv/`** — it's in `.gitignore`
- **Never commit API keys** — use environment variables or a `.env` file (also in `.gitignore`)
- **Never mix UI logic and pipeline logic** — keep them strictly separated
- **Do not add dependencies without updating `requirements.txt`**
- **Do not introduce a new phase's code before the current phase is complete**

---

## Project Philosophy

- **Passion project, not a startup.** No deadlines, no funding pressure.
- **Portfolio piece.** Every milestone is independently demonstrable.
- **No black boxes.** Understand the diffusion math, ControlNet conditioning, IP-Adapter cross-attention. Don't just pipe APIs.
- **Documented journey.** Progress is logged on a Docusaurus engineering blog.
- **Infinite timeline.** Each phase is self-contained. Progress survives long gaps.

---

## Known Risks

- **In-betweening quality:** diffusion models struggle with hand-drawn animation physics (squash, stretch, smear). May hit a wall. Documenting why it's hard is almost as valuable as solving it.
- **Temporal consistency:** active research problem. Seed locking and latent anchoring help but aren't perfect.
- **Cloud latency:** round-trip inference may feel slow for iterative workflows. Local GPU is Phase 5+.
- **Model evolution:** SD/Flux ecosystem moves fast. Design the pipeline to be model-agnostic where possible.

---

*Last updated: April 2026 — Phase 0*