#!/usr/bin/env bash
# One-time setup. Installs Playwright + Chromium into ~/.cache/yt-video (shared by all projects),
# and numpy + scipy for the audio scripts. Run: bash scripts/setup.sh
set -e
TOOLS="${SHORTS_TOOLS_DIR:-$HOME/.cache/yt-video}"
missing=()
command -v node >/dev/null   || missing+=("node 18+ (https://nodejs.org)")
command -v ffmpeg >/dev/null || missing+=("ffmpeg with libx264 (macOS: brew install ffmpeg, Ubuntu: sudo apt install ffmpeg, Windows: winget install ffmpeg)")
command -v python3 >/dev/null || missing+=("python3 3.9+")
if [ ${#missing[@]} -gt 0 ]; then printf 'Missing:\n  %s\n' "${missing[@]}"; exit 1; fi

python3 -c "import numpy, scipy" 2>/dev/null || python3 -m pip install --user numpy scipy || python3 -m pip install --break-system-packages numpy scipy

if [ ! -d "$TOOLS/node_modules/playwright" ]; then
  mkdir -p "$TOOLS"
  [ -f "$TOOLS/package.json" ] || echo '{"private":true}' > "$TOOLS/package.json"
  (cd "$TOOLS" && npm install --silent playwright)
fi
(cd "$TOOLS" && npx playwright install chromium)
echo "Installed. Check everything with: python3 $(dirname "$0")/short.py doctor"
