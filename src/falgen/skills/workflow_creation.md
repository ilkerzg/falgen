# Workflow Creation - Production Pipeline Design Patterns

Design and build multi-step AI media generation pipelines on fal.ai.
These patterns are proven in production workflows. Use `search_models` and `best_models` to find the right model for each step - never hardcode model choices.

## Quick Reference

> **Golden Rule:** Always use `best_models` with appropriate category and style to pick generation models. Use `search_models` to find utility endpoints. Never assume a model name - look it up.

**Core Architecture**
```
User Input → [LLM Planner] → [N × LLM Extractors] → [N × Generation] → [Post-processing] → Output
```

**Model Selection by Role**
| Role | How to Find | Key Parameters |
|------|------------|----------------|
| Image generation | `best_models(category="text-to-image", style=...)` | aspect_ratio, resolution |
| Image editing | `best_models(category="image-editing")` | reference image + edit prompt |
| Text-to-video | `best_models(category="text-to-video")` | duration, aspect_ratio |
| Image-to-video | `best_models(category="image-to-video")` | start_image, duration |
| Upscaling | `search_models(query="upscale")` | scale_factor |
| TTS/Voice | `best_models(category="text-to-speech")` | voice, stability, speed |
| LLM routing | `search_models(query="openrouter")` | model, temperature, reasoning |
| Video merge | `search_models(query="merge videos")` | video_urls array |
| Crop/Resize | `search_models(query="crop image")` | percentage-based coordinates |
| Subtitles | `search_models(query="subtitle")` | text array, timing, position |

**Temperature Gradient Rule**
- Creative planning: 0.7-0.85
- Image/video prompts: 0.5-0.6
- Text extraction/parsing: 0.1-0.3
- Duration/parameter estimation: 0.3-0.5

---

## Architecture Patterns

### Pattern 1: Fan-Out Parallel Pipeline
The most common pattern. One planner generates a structured plan, then N independent lanes execute in parallel.

```
[Planner LLM] → structured plan (JSON or delimited text)
       ↓
[Extract-1] [Extract-2] ... [Extract-N]    ← parallel LLM extraction
       ↓         ↓              ↓
[Image-1]  [Image-2]  ... [Image-N]        ← parallel generation
       ↓         ↓              ↓
[Video-1]  [Video-2]  ... [Video-N]        ← parallel video gen
       ↓         ↓              ↓
              [Merge All]                   ← sequential assembly
                  ↓
               [Output]
```

**When to use:** Multi-scene videos, batch generation, dataset creation.
**Key rules:**
- Planner outputs a structured format with clear delimiters (e.g., `===SCENE N===` or JSON)
- Extractors use low temperature (0.1) for deterministic parsing
- All independent lanes run in parallel for speed
- Assembly is always the final sequential step

### Pattern 2: Sequential Compositing Chain
Each step builds on the previous, adding layers progressively.

```
[Generate Base Scene]
       ↓
[Edit: Add Product/Subject]
       ↓
[Edit: Add People/Characters]
       ↓
[Edit: Add VFX/Effects]
       ↓
[Generate Video from Final Image]
```

**When to use:** Product campaigns, branded content, complex scene composition.
**Key rules:**
- Each edit pass should change ONE thing only
- Preserve everything from previous steps explicitly in the prompt
- Use vision LLM between steps to verify the result before proceeding
- Final image → video as the last step

### Pattern 3: Contact Sheet (Grid-Then-Slice)
Generate multiple views/variants as a single composite image, then crop into individual frames.

```
[Generate N×M Grid Image]
       ↓
[Crop-1] [Crop-2] ... [Crop-N×M]    ← parallel
       ↓       ↓            ↓
[Upscale-1] [Upscale-2] ... [Upscale-N×M]  ← parallel (compensate crop quality loss)
```

**When to use:** Multi-angle views, character variants, culture/style variations, product turntables.
**Key rules:**
- Single image ensures visual consistency across all variants
- Crop coordinates must be precise (percentage-based: x_offset, y_offset, width, height)
- ALWAYS upscale after cropping - cropped tiles lose resolution
- Common layouts: 2×3, 3×4, 4×2, 2×2
- Prompt must explicitly describe the grid layout (e.g., "4×2 grid, each panel shows...")
- Specify "no borders, no grid lines, no gaps between panels" in the prompt

### Pattern 4: Frame-Bridging (Continuous Video Chain)
Create seamless long videos by chaining clips via last-frame extraction.

```
[Image-1] → [Video-1 (8s)] → [Extract Last Frame] → [Video-2 (8s)] → [Extract Last Frame] → ...
                                                                              ↓
                                                                    [Merge All Videos]
```

**When to use:** Long-form content (60s+), documentaries, narratives requiring visual continuity.
**Key rules:**
- Extract the LAST frame from each video clip
- Use the extracted frame as the START image for the next clip
- Use a SHARED motion prompt across all clips for consistency
- This doubles your video length: N images → 2N clips
- Total duration = N × 2 × clip_duration

### Pattern 5: Start/End Frame Interpolation
Generate both first and last frames, then let video model interpolate between them.

```
[Generate Start Frame]
       ↓
[Vision LLM analyzes start frame]
       ↓
[Edit Start Frame → End Frame]
       ↓
[Video Model: start_image + end_image + motion_prompt]
```

**When to use:** Precise motion control, subtle movements, character acting, product reveals.
**Key rules:**
- End frame is created by EDITING the start frame (not generating independently)
- This ensures visual consistency between start and end
- Vision LLM should SEE the actual generated start frame before writing the edit prompt
- Motion prompt should describe ONLY the transition, not the static composition
- Physically specific motion: use degrees, distances, directions (not vague descriptions)
- Best for 4-5 second clips with controlled, deliberate motion

### Pattern 6: Frame-as-Bridge (Style Transfer via V2V)
Transform visual style in image space, then propagate to video via video-to-video.

```
[Input Video] → [Extract First Frame]
                        ↓
                [Edit Frame (transform style/look)]
                        ↓
                [Video-to-Video: original_video + transformed_frame]
```

**When to use:** Style transfer, character transformation, artistic effects on existing video.
**Key rules:**
- Transform the LOOK in image space (cheaper, more controllable)
- Use v2v to propagate the transformation while preserving MOTION from original
- The original video provides motion reference
- The transformed frame provides style/aesthetic reference

### Pattern 7: Multi-Modal Assembly (Video + Audio + Subtitles)
Combine separately generated visual, audio, and text tracks.

```
                    [Scene Planner]
                    ↓          ↓          ↓
            [Narration Text] [Image Prompt] [Motion Prompt]
                    ↓          ↓               ↓
                [TTS Audio]  [Image Gen]       ↓
                    ↓          ↓               ↓
                    ↓      [I2V Video] ←───────┘
                    ↓          ↓
            [Merge Audio + Video]
                    ↓
            [Add Subtitles]
                    ↓
                [Output]
```

**When to use:** Documentaries, narrated content, educational videos, marketing.
**Key rules:**
- Audio and visual streams run in PARALLEL (big time savings)
- Merge audio+video per scene FIRST, then concatenate all scenes
- Consistent voice settings across all TTS calls (same voice, stability, speed)
- Subtitle timing: match to scene duration (e.g., 5s per scene → subtitle at 0-5s)
- Disable audio generation on video model when using external TTS

### Pattern 8: Multi-Expert Agent Panel
Chain specialized LLM "experts" that each contribute a different dimension, then synthesize.

```
[Vision LLM: Analyze Input]
       ↓
[Expert A: Strategy] ──┐
[Expert B: Visual]  ───┤── parallel
[Expert C: Motion]  ───┘
       ↓
[Merge All Expert Outputs]
       ↓
[Master Synthesizer LLM → final prompts]
       ↓
[N × Generation]
```

**When to use:** Brand campaigns, complex creative briefs, multi-format output (story + square + landscape + video).
**Key rules:**
- Each expert has a narrow, well-defined role (strategist, art director, motion director)
- Expert outputs are structured JSON for composability
- A final "master" LLM synthesizes all expert inputs into generation-ready prompts
- Enforce diversity: master must avoid reusing angles, backgrounds, or lighting across outputs

### Pattern 9: Shotgun Variation (Brute-Force Diversity)
Run the same prompt through many parallel instances, relying on sampling randomness for diversity.

```
[Single LLM Prompt] → [Instance-1] [Instance-2] ... [Instance-N]  ← all parallel, same prompt
                            ↓           ↓               ↓
                      [Image-1]   [Image-2]   ...  [Image-N]
```

**When to use:** Style exploration, generating many variants for user selection, A/B testing.
**Key rules:**
- All LLM nodes share the IDENTICAL prompt
- Diversity comes from LLM sampling randomness (temperature 0.6-0.9)
- Generate many (15-50), let user pick the best
- Works best with style transfer / image editing where a reference image constrains the output

### Pattern 10: Systematic Variation Matrix
Each node varies exactly ONE controlled axis while keeping everything else constant.

```
[Base Prompt + Variation 1: angle=front, lighting=studio]     → [Image-1]
[Base Prompt + Variation 2: angle=3/4, lighting=golden-hour]  → [Image-2]
[Base Prompt + Variation 3: angle=close-up, lighting=blue]    → [Image-3]
...
```

**When to use:** Product photography, character turntables, comprehensive style sheets.
**Key rules:**
- Define a variation matrix: angle × lighting × material × mood
- Each node gets a unique combination from the matrix
- Temperature scales with creativity needs: standard shots 0.6, artistic 0.9
- Share a common base prompt, only the variation section changes

### Pattern 11: Zero-Shot Multi-Image Reasoning
Use a vision LLM to analyze multiple input images, assign roles, and generate structured instructions.

```
[Multiple Input Images] → [Vision LLM with reasoning]
                                    ↓
                          [Structured JSON: role assignments + instructions]
                                    ↓
                          [Image Edit with all inputs + instructions]
```

**When to use:** Identity swap, style transfer from reference, multi-image composition.
**Key rules:**
- Use the most capable vision model with reasoning enabled
- LLM must analyze ALL images and determine which serves what role
- Output structured JSON with explicit preservation rules and negative constraints
- Priority hierarchy: what to keep > what to change

---

## Creative Techniques

### Character Consistency
- **Single reference → edit method:** Generate one anchor image, then EDIT it for each scene variation. All scenes share the same visual DNA.
- **Contact sheet method:** Generate all character poses/angles in one grid image. Ensures consistent face, body, clothing across all variants.
- **Identity description lock:** In every prompt, repeat the full character description (face, hair, body type, clothing). Never abbreviate after the first mention.

### Dramatic Arc via Prompt Escalation
Structure emotional intensity across scenes through vocabulary:

| Act | Intensity | Motion Words | Lighting Words |
|-----|-----------|-------------|----------------|
| Introduction | Low | slowly, gently, softly | warm, natural, ambient |
| Development | Medium | steadily, deliberately | focused, directional |
| Rising Action | High | quickly, anxiously | dramatic, high contrast |
| Climax | Peak | explosively, desperately, overwhelmingly | intense, backlit, chiaroscuro |
| Resolution | Calm | peacefully, softly, slowly | golden hour, warm, peaceful |

### Vision-Grounded Feedback Loop
Use vision LLM to examine GENERATED images before writing the next prompt:
```
[Generate Image] → [Vision LLM sees it] → [Write context-aware prompt] → [Next step]
```
This compensates for generation drift (what was prompted vs what was actually produced).

### Cinematic Transition Devices
- **Shoulder tap:** Character A taps Character B's shoulder, camera pans to reveal B
- **360° tour reveal:** Camera orbits scene, returns to starting point with new overlay
- **Frame extract → continue:** Last frame of clip N becomes first frame of clip N+1
- **Start/end frame morph:** Controlled interpolation between two defined keyframes

### Material-Layered Prompting
Stack multiple synonymous descriptors to reinforce a specific look:
- Surface: "glossy, shiny, reflective, polished, gleaming"
- Texture: "rough, grainy, weathered, textured, pitted"
- Material: "vinyl, plastic, ceramic, metallic, organic"
- Lighting interaction: "catches light, subsurface scattering, specular highlights, diffuse glow"

---

## Node Design Rules

### LLM Planner Node
- Use the most capable model available (check `best_models`)
- Enable reasoning for complex creative decisions
- Temperature: 0.7-0.85
- Output must be structured and parseable (JSON, delimited sections, numbered lists)
- Include explicit output format examples in the system prompt
- One planner per workflow (avoid multiple planning stages)

### LLM Extractor Node
- Use the fastest/cheapest model available
- Temperature: 0.1 (near-deterministic)
- Prompt: "Extract ONLY [specific item] from the text. Output NOTHING else."
- Fan out N extractors in parallel from one planner output
- Alternative: use split-text utility with a delimiter (cheaper than LLM)

### Image Generation Node
- Use `best_models` to find the top-ranked model for the desired style
- Always specify: aspect_ratio, resolution/image_size
- For reference-based: use image editing models with the reference as input
- For grids/sheets: explicitly describe layout, "no borders, no gaps"

### Image Editing Node
- Input: reference image + text prompt describing the edit
- Keep edits focused: change ONE thing per pass
- Explicitly state what to PRESERVE: "keep background, lighting, clothing exactly the same"
- For subtle changes: be physically specific (angles, distances, colors)

### Video Generation Node (Image-to-Video)
- Start image is required (never use text-to-video for pipeline steps)
- Specify: duration, aspect_ratio, negative_prompt
- Disable audio generation when using external TTS: `generate_audio: false`
- Motion prompt should be SHORT (15-35 words max)
- Focus on: subject motion + camera motion + ambient
- Common negative prompt: "blur, distort, low quality, text, watermark, morphing, flickering"

### Utility Nodes
- **Crop:** Use percentage coordinates (x_offset_percentage, y_offset_percentage, width_percentage, height_percentage)
- **Upscale:** Always upscale AFTER cropping to recover lost resolution
- **Merge videos:** Input is an array of video URLs in playback order
- **Merge audio+video:** Per-scene merge BEFORE concatenating all scenes
- **Subtitles:** Two passes for dual-layer (e.g., names on top, locations on bottom)
- **Compress:** Final step before delivery, specify target width/quality

---

## Pipeline Recipes

### Recipe: Multi-Scene Cinematic Video
```
Input: concept/story description
Steps:
1. LLM Planner → N scene descriptions (with start/end frame + motion for each)
2. N × Image Gen (start frames, parallel)
3. N × Image Edit (end frames from start frames, parallel)
4. N × I2V with start+end frames (parallel)
5. Merge all clips
Optional: + TTS narration + subtitle overlay
```

### Recipe: Cultural/Style Variation Grid
```
Input: reference image + N variation descriptions
Steps:
1. LLM Planner → composite grid prompt with N panels
2. Image Edit → single N-panel grid image
3. N × Crop (parallel)
4. N × Upscale (parallel)
Optional: N × I2V with transition prompts + merge
```

### Recipe: Product Campaign
```
Input: product reference photos + brand guidelines
Steps:
1. Vision LLM → scene composition prompt
2. Sequential edits: scene → product placement → human → VFX
3. Create clean version (remove text/logos)
4. I2V with clean→branded start/end frames
```

### Recipe: Training Dataset Generator
```
Input: task type (e.g., "background_remove")
Steps:
1. LLM Planner → N diverse (start_prompt, edit_prompt) pairs
2. N × Image Gen (original images, parallel)
3. N × Image Edit (transformed images, parallel)
4. N × Vision LLM (captions by examining generated images, parallel)
Output: N × (original, transformed, caption) triplets
```

### Recipe: Narrated Documentary
```
Input: topic/subject
Steps:
1. LLM Planner → N scenes with narration + visual + motion
2. Per scene (all parallel):
   a. Extract narration → TTS
   b. Extract visual → Image Gen → I2V (with motion prompt)
3. Per scene: merge audio + video
4. Merge all scenes
Optional: + subtitle overlay
```

### Recipe: Brand Campaign (Multi-Expert)
```
Input: brand image + brief text
Steps:
1. Vision LLM → brand identity analysis
2. 3 parallel experts: strategist, art director, motion director
3. Master synthesizer → 6 image prompts + 2 video prompts
4. 6 × Image Gen (parallel, mixed aspect ratios)
5. 2 × I2V from generated keyframe images
Output: 6 images + 2 videos across story/square/landscape formats
```

### Recipe: Style Exploration (Shotgun)
```
Input: reference image + target style description
Steps:
1. N × LLM (same prompt, parallel) → N diverse prompt variations
2. N × Image Edit (reference + each prompt, parallel)
Output: N style variants for user to browse/select
```

### Recipe: Identity-Preserving Edit
```
Input: multiple images (scene + identity references)
Steps:
1. Vision LLM (reasoning) → analyze images, assign roles, write JSON instructions
2. Image Edit with all images + JSON instructions
Output: edited image with preserved identity in target scene
```

---

## Common Mistakes to Avoid

1. **Generating images independently when consistency matters** → Use contact sheet or edit-from-reference instead
2. **Using text-to-video when you have a reference image** → Always prefer image-to-video for better control
3. **Long motion prompts in video generation** → Keep under 35 words, focus on motion only
4. **Hardcoding model names** → Always use best_models/search_models to find current best
5. **Sequential execution when parallel is possible** → Fan out all independent work
6. **Skipping upscale after crop** → Cropped tiles always lose resolution
7. **Using expensive LLM for text extraction** → Use cheapest/fastest model at temp 0.1
8. **Vague motion descriptions** → Be physically specific: degrees, distances, directions
9. **Multiple changes in one edit pass** → One edit = one change, chain multiple passes
10. **Generating audio in I2V when using TTS** → Set generate_audio: false to avoid conflicts
