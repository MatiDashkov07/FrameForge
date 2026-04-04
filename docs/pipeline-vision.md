# FrameForge — Pipeline Vision

## Current State (Phase 2.2)
ComfyUI on RunPod Pod. Workflow: lineart_anime ControlNet + 
IP-Adapter + Animagine/AnythingXL. Single reference image.
FrameForge calls ComfyUI's REST API directly.

## Planned Enhancements

### Vision Analysis Layer (Phase 3)
Inject a vision model (Gemini or GPT-4o) before the diffusion step.
The model receives the sketch and outputs a structured description:
subject, pose, apparent character type, scene context.
This description is merged into the prompt automatically.
Goal: eliminate semantic confusion (cat → girl problem).

### Character Description System (Phase 3)
In the References panel, each reference image gets an optional 
text field: character name + short description.
Example: "Luffy — straw hat, red vest, black hair, scar under left eye"
The system uses this to construct a detailed, accurate prompt 
without requiring the user to know prompt engineering.

### Prompt Enhancer (Phase 3)
A local pre-processing step (Claude/Gemini API call) that takes 
the user's raw prompt and rewrites it into optimized diffusion 
prompt syntax — correct token ordering, quality tags, negative 
prompt suggestions.
Runs client-side before the ComfyUI call.

### Multi-Reference Embedding Averaging (Phase 4)
Instead of passing only reference_paths[0] to IP-Adapter,
encode all reference images (up to 10–20) and average their 
embeddings in latent space.
Use case: character reference sheets from multiple angles 
(front, side, back) → single coherent style embedding.
Requires custom ComfyUI node or direct diffusers integration.

### Model-Agnostic Pipeline (Phase 4+)
Abstract the ComfyUI workflow behind a config file.
Swapping models = editing one JSON, not touching Python code.
Enables easy experimentation with new checkpoints as the 
anime model ecosystem evolves.





FrameForge — Strategic Evolution Map
Phase 2.5: Performance & Fidelity Foundation
Goal: Solidify the base output before adding complex AI logic.
Step 1: Embedding Caching (Non-Blocking)
Action: Implement a caching layer for IP-Adapter latent embeddings of reference images.
Why: If a user generates 5 versions of the same character, the system shouldn't re-calculate the image encoding every time.
Step 2: Lineart-Specific LoRA Integration (Blocking)
Action: Inject a lightweight LoRA (e.g., Flat Anime or Lineart Enhancer) into the Animagine XL checkpoint.
Why: This "teaches" the model to respect the clean lines provided by ControlNet, reducing visual noise.
Phase 3: Intelligence & Semantic Layer (The "Brain")
Goal: Bridge the gap between "lines" and "meaning".
Step 3: Vision Analysis Layer (Blocking)
Action: VLM (Gemini/GPT-4o) analyzes the sketch.
Output: Structured JSON containing: subject, pose, lighting_source, and bounding_boxes.
Step 4: Automated Prompt Engineering (Blocking)
Action: Use a local LLM or API to convert the Vision Analysis + User Input into Danbooru Tags (e.g., 1girl, solo, looking at viewer, blue eyes).
Why: Animagine XL follows tags much better than natural language.
Phase 4: Advanced Consistency & Refinement
Goal: Achieving professional, production-ready quality.
Step 5: Multi-Reference Weighted Averaging (Blocking)
Action: Encode multiple angles of a character and apply a weighted average (Face > Clothing > Background).
Step 6: Regional Prompting (Blocking)
Action: Use the VLM's bounding_boxes to apply different prompts to different areas of the canvas using ComfyUI Conditioning nodes.
Why: Prevents "color bleeding" (e.g., if the character has red hair, the background doesn't accidentally turn red).
Step 7: Face/Hand Adetailer (Blocking - Post Process)
Action: A final pass that detects the face/hands and re-renders them at a higher resolution.
Phase 5: Scale & UX Optimization
Goal: Moving from a prototype to a snappy, cost-effective product.
Step 8: Real-Time WebSocket Streaming (Non-Blocking)
Action: Instead of waiting for the REST API to finish, stream the intermediate "Latent Previews" to the client.
Why: Dramatic improvement in perceived speed; the user sees the image "forming" in real-time.
Step 9: Serverless Migration (Infra)
Action: Move from RunPod Pods to RunPod Serverless.
Why: Scale to zero costs when no one is using the app, and scale to infinity during peak traffic.

Refined Approach to Regional Prompting (Phase 4, Step 6): Instead of relying on a Vision Language Model (VLM) to generate raw bounding box coordinates—which often leads to imprecise borders and color-bleeding artifacts—the VLM will be used strictly for semantic tagging (e.g., identifying "straw hat" or "red vest"). These tags will then be passed to a dedicated segmentation model like GroundingDINO within the ComfyUI pipeline to generate pixel-perfect, dynamic masks for accurate regional conditioning.

Simplified Multi-Reference Averaging (Phase 4, Step 5): To avoid the heavy R&D overhead of building custom Python logic for latent space math, the multi-reference system will leverage the existing IP-Adapter Plus architecture natively within ComfyUI. This allows the system to accept a batch input of multiple reference images and automatically handles the weighted embedding averaging required for cohesive 360-degree character styling.