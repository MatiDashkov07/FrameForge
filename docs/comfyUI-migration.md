# FrameForge: Architecture Migration Source of Truth (SoT)
## Phase 2.5: Replicate API to Custom ComfyUI (RunPod)

**Document Purpose:** This is the definitive roadmap for migrating FrameForge's backend rendering engine. It outlines the transition from a managed Replicate API to a fully controlled, self-hosted ComfyUI pipeline on RunPod. This document supersedes previous plans and incorporates critical fixes for API flow, state management, and infrastructure persistence.

---

### Step 1: Local ComfyUI Foundation (PoC Translation)
Before touching cloud infrastructure, the exact Replicate PoC must be recreated and isolated in a local environment.

* **Setup:** Install ComfyUI locally. GPU performance is irrelevant here; the goal is structural correctness.
* **Pipeline Construction:** Build the visual node tree combining:
    * Base Model (Animagine XL or SDXL).
    * ControlNet (Lineart) for the sketch constraint.
    * IP-Adapter Plus for the single-image reference constraint.
* **Bug Fix / State Isolation:** Ensure the workflow explicitly routes the sketch image *only* to ControlNet and the reference image *only* to the IP-Adapter. This corrects the semantic bleeding observed in the previous Replicate implementation.
* **API Export:** Enable `Dev mode Options` in ComfyUI settings and export the pipeline using `Save (API Format)` to generate the base `workflow_api.json`.

---

### Step 2: The API Contract & Python Client
ComfyUI's API is asynchronous and requires specific file-handling protocols. This step abstracts that complexity behind a clean Python class.

* **Node ID Mapping:** Open `workflow_api.json`. ComfyUI assigns arbitrary numeric strings (e.g., `"4"`, `"13"`) to nodes. Identify the IDs for the sketch upload, reference upload, text prompt, and strength sliders. Hardcode these as documented constants at the top of your Python file to prevent mystery bugs later.
* **The Adapter Pattern:** Create a new file named `comfyui_client.py`. It must expose the exact same `render_frame()` method signature as your existing `replicate_client.py`.
* **Execution Flow Implementation:** Inside `render_frame()`, implement the strict ComfyUI lifecycle:
    1.  **Upload:** `POST /upload/image` using `multipart/form-data` for both the sketch and the reference image. Store the filenames returned by the server.
    2.  **Template:** Inject those returned filenames and the user's text prompt into the mapped Node IDs within your loaded JSON payload.
    3.  **Queue:** `POST /prompt` with the populated JSON. The server will immediately return a `prompt_id`.
    4.  **Poll:** Implement a `while` loop that calls `GET /history/{prompt_id}` every ~1 second until the job status shows as completed.
    5.  **Fetch:** Construct the final image URL and call `GET /view?filename=...` to download the rendered frame.
* **Testing:** Write `tests/test_comfyui_local.py` to run a headless smoke test against your local ComfyUI instance.

---

### Step 3: Cloud Infrastructure Setup (RunPod Pods)
Transitioning to the cloud requires handling RunPod's ephemeral storage model to prevent massive data loss on shutdown.

* **Persistent Storage (Critical):** Do not immediately spin up a Pod. First, provision a **Network Volume** (~50 GB) in your chosen RunPod datacenter. 
* **Pod Provisioning:** Spin up a standard GPU Pod (e.g., RTX 3090 or 4090) using the official ComfyUI template. **Attach the Network Volume** during setup.
* **Model Hydration:** Point ComfyUI's model paths to the Network Volume. Download the hefty model weights (Base checkpoints, ControlNet, IP-Adapter, CLIPVision) to this volume once. They will now survive Pod restarts.
* **Manual Validation:** Access the Pod's web interface via the RunPod proxy link and run a manual generation to verify that the GPU is utilizing the models correctly.

---

### Step 4: App Integration & Engine Swap
Because the codebase uses a clean adapter pattern, swapping the engines requires minimal changes to the core application logic.

* **The Swap:** Open `render_worker.py`. Change the import statement from `replicate_client` to `comfyui_client`.
* **Network Configuration:** Update `comfyui_client.py` to point to your RunPod proxy URL instead of `127.0.0.1`. Inject your RunPod API key into the headers for authentication.
* **End-to-End Test:** Launch the PySide6 UI, upload the Luffy sketch and reference sheet, and trigger a render. The desktop app will now orchestrate the cloud GPU pipeline.
* **Verification:** Write `tests/test_comfyui_cloud.py` to finalize the migration testing suite.