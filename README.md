<p align="center">
  <img src="https://v3b.fal.media/files/b/0a91669c/SRSupr_XeUEEjj-ygMUWU_image.png" width="720" />
</p>

<h1 align="center">falgen</h1>

<p align="center">
  <img src="https://img.shields.io/badge/status-beta-orange" alt="beta" />
  <a href="https://fal.ai"><img src="https://img.shields.io/badge/powered%20by-fal.ai-blue" alt="powered by fal.ai" /></a>
  <a href="https://artificialanalysis.ai"><img src="https://img.shields.io/badge/rankings-Artificial%20Analysis-purple" alt="Artificial Analysis" /></a>
  <img src="https://img.shields.io/github/license/fal-ai/falgen" alt="license" />
</p>

<p align="center">
  Open source AI media generation from the terminal.
</p>

<p align="center">
  <a href="#install">Install</a> · <a href="#usage">Usage</a> · <a href="#features">Features</a> · <a href="#commands">Commands</a> · <a href="#contributing">Contributing</a>
</p>

---

Generate images, videos, audio, and more — just describe what you want. falgen picks the best model using [Artificial Analysis](https://artificialanalysis.ai) quality rankings, handles the queue, and renders results inline in your terminal.

## Install

```bash
# Homebrew
brew install fal-ai/tap/falgen

# pip
pip install falgen

# npx (downloads a prebuilt binary)
npx falgen
```

## Auth

```bash
# Option 1: falgen prompts for your key on first launch
falgen

# Option 2: environment variable
export FAL_KEY="your-key-here"
falgen
```

Get your API key at [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys).

## Usage

```
falgen                  # start a new session
falgen -s last          # resume last session
falgen -m openai/gpt-5.4  # use a specific LLM
```

Then just type what you want:

```
> a cyberpunk city at sunset, neon reflections on wet streets
> generate a 10s video of ocean waves crashing
> create lofi hip-hop background music, chill vibes
> upscale my photo to 4K
```

## Features

**Smart model selection** — Ranks models by quality using [Artificial Analysis](https://artificialanalysis.ai) arena ELO ratings. Supports style-specific rankings (portraits, anime, photorealistic, etc.) so you always get the best model for your task.

<p align="center">
  <img src="https://v3b.fal.media/files/b/0a9166b9/asZora6lqpsXpGUr_nmDv_image.png" width="720" />
  <br />
  <em>The agent asks which model to use, ranked by Artificial Analysis ELO ratings, and proceeds based on your choice.</em>
</p>

**AI tools** — The LLM agent has access to:

| Tool | Description |
|------|-------------|
| `best_models` | Quality rankings from Artificial Analysis arena |
| `search_models` | Search fal.ai's 600+ model catalog |
| `model_info` | Input schema, parameters, valid values |
| `generate` | Submit jobs, poll status, stream results |
| `ask_user` | Interactive choice picker for decisions |
| `get_skill` | Domain knowledge (cinematography, prompting, etc.) |
| `get_pricing` | Cost per image/minute/character |

<p align="center">
  <img src="https://v3b.fal.media/files/b/0a9166a4/BX6kG6seiaKGaMdgL_bFb_image.png" width="720" />
  <br />
  <em>Tool calls in action — the agent searches models, checks schemas, and submits a generation job with a live loading skeleton.</em>
</p>

<p align="center">
  <img src="https://v3b.fal.media/files/b/0a9166a8/XtffpVMkVdgRhu-j9lUeH_image.png" width="720" />
  <br />
  <em>Generated image rendered inline via <a href="https://hpjansson.org/chafa/">chafa</a>. Click to open in your system viewer.</em>
</p>

**Terminal UI** — Built with [Textual](https://textual.textualize.io/). Inline media preview via [chafa](https://hpjansson.org/chafa/). Five themes: Tokyo Night, Catppuccin, Nord, Gruvbox, Everforest.

<p align="center">
  <img src="https://v3b.fal.media/files/b/0a9166b2/M7ZWfSjopBB0E-PXgezZV_image.png" width="720" />
  <br />
  <em>Slash commands with autocomplete for quick access to all features.</em>
</p>

**Input** — Multi-line input (Shift+Enter), image paste from clipboard (Ctrl+V), local file path detection and upload, fuzzy-filtered choice menus.

**Session management** — SQLite persistence, resume previous sessions (`/resume`), media URLs tracked per session.

**Context management** — Automatic conversation summarization when approaching context limits.

## Commands

| Command | Description |
|---------|-------------|
| `/model` | Switch LLM |
| `/theme` | Switch color theme |
| `/search` | Search fal.ai models |
| `/info` | Model schema and details |
| `/price` | Check pricing |
| `/default` | Set default models per category |
| `/resume` | Resume a previous session |
| `/compact` | Toggle compact mode (hide tool calls) |
| `/usage` | Usage and cost |
| `/login` | Set API key |
| `/clear` | Clear conversation |

**Keyboard:** `Shift+Enter` new line · `Esc` cancel generation · `Ctrl+L` clear · `Ctrl+V` paste image · `Ctrl+C` quit

## Preview Dependencies

- [chafa](https://hpjansson.org/chafa/) — inline image/video/audio previews
- [ffmpeg](https://ffmpeg.org/) — video thumbnails and audio waveforms
- Optional: [pngpaste](https://github.com/jcsalterego/pngpaste) — clipboard image paste on macOS

The app runs without these, but previews will be unavailable.

## Contributing

Open source side project. Contributions, issues, and ideas are welcome.

```bash
git clone https://github.com/fal-ai/falgen
cd falgen
pip install -e .
falgen
```

## Acknowledgements

Model quality rankings powered by [Artificial Analysis](https://artificialanalysis.ai) — independent benchmarks through crowd-sourced blind comparisons.

## License

MIT
