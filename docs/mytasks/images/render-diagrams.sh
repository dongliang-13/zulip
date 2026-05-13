#!/usr/bin/env bash
# render-diagrams.sh
# Renders the PlantUML source files in this directory to PNG.
#
# Usage:
#   cd docs/mytasks/images
#   bash render-diagrams.sh
#
# Tries renderers in this order:
#   1. plantuml CLI (brew install plantuml  /  apt install plantuml)
#   2. Docker image plantuml/plantuml (docker.com)
#   3. plantuml.jar auto-downloaded from GitHub (requires java)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUML_FILES=(
    "deployment-overview.puml"
    "data-flow.puml"
    "db-schema.puml"
)

# ── colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[render]${NC} $*"; }
warn()  { echo -e "${YELLOW}[render]${NC} $*"; }
error() { echo -e "${RED}[render]${NC} $*" >&2; }

render_with_cli() {
    info "Renderer: plantuml CLI"
    for f in "${PUML_FILES[@]}"; do
        info "  → $f"
        plantuml -tpng -o "$SCRIPT_DIR" "$SCRIPT_DIR/$f"
    done
}

render_with_docker() {
    info "Renderer: Docker (plantuml/plantuml)"
    for f in "${PUML_FILES[@]}"; do
        info "  → $f"
        docker run --rm \
            -v "$SCRIPT_DIR":/work \
            plantuml/plantuml \
            -tpng "/work/$f"
    done
}

render_with_jar() {
    local JAR="$SCRIPT_DIR/plantuml.jar"
    if [[ ! -f "$JAR" ]]; then
        warn "plantuml.jar not found — downloading from GitHub releases..."
        local URL
        URL=$(curl -fsSL https://api.github.com/repos/plantuml/plantuml/releases/latest \
            | grep '"browser_download_url"' \
            | grep 'plantuml\.jar"' \
            | head -1 \
            | sed 's/.*"browser_download_url": "\(.*\)"/\1/')
        if [[ -z "$URL" ]]; then
            # Fallback to a known stable version
            URL="https://github.com/plantuml/plantuml/releases/download/v1.2024.6/plantuml-1.2024.6.jar"
        fi
        info "Downloading: $URL"
        curl -fsSL -o "$JAR" "$URL"
        info "Saved to: $JAR"
    fi

    info "Renderer: plantuml.jar (java)"
    for f in "${PUML_FILES[@]}"; do
        info "  → $f"
        java -jar "$JAR" -tpng -o "$SCRIPT_DIR" "$SCRIPT_DIR/$f"
    done
}

# ── main ──────────────────────────────────────────────────────────────────────
echo ""
info "Rendering ${#PUML_FILES[@]} PlantUML diagrams → PNG"
echo ""

if command -v plantuml &>/dev/null; then
    render_with_cli
elif command -v docker &>/dev/null; then
    render_with_docker
elif command -v java &>/dev/null; then
    render_with_jar
else
    error "No renderer found. Install one of:"
    error "  plantuml  →  brew install plantuml   (macOS)"
    error "             →  apt install plantuml    (Ubuntu/Debian)"
    error "  docker    →  https://www.docker.com"
    error "  java      →  https://adoptium.net    (script auto-downloads plantuml.jar)"
    exit 1
fi

echo ""
info "Done. Output files:"
for f in "${PUML_FILES[@]}"; do
    PNG="${f%.puml}.png"
    if [[ -f "$SCRIPT_DIR/$PNG" ]]; then
        info "  ✓ $PNG"
    else
        warn "  ? $PNG  (not found — check plantuml output above)"
    fi
done
echo ""
