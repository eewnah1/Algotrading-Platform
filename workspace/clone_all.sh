#!/usr/bin/env bash
# Clone all eewnah1 dashboard repos into the repos/ folder for VS Code workspace use.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOS_DIR="$SCRIPT_DIR/repos"
mkdir -p "$REPOS_DIR"
cd "$REPOS_DIR"

REPOS=(
  Algotrading-Platform
  Options-Market-Maker-Simulator
  ichimoku-signals-app
  Modernise-TradeMaster
  aussuper-switch-predictor
  RL_QuantTrading
  srt-next-day-predictor
  SGX-G3B-Predictor
  sgx-cfa-next-day-predictor
  hst-next-day-predictor
  clr-next-day-predictor
  Schroder-Multi-Asset-Revolution-Fund-Next-Day-and-Multi-Horizon-Predictor
  SLV-Silver-ETF-Multi-Horizon-Predictor
  PineBridge-Acorns-of-Asia-Balanced-Predictor
  Neuberger-Berman-Next-Gen-Connectivity-Predictor
  MG-Lux-Japan-Fund-Multi-Horizon-Predictor
  LionGlobal-Korea-Fund-Multi-Horizon-Direction-Predictor
  KOSPI-Next-Day-Predictor
  International-Fund-Switch-In-Next-Day-Predictor
  First-Sentier-Bridge-Fund-Next-Day-and-Multi-Horizon-Predictor
  BlackRock-World-Gold-Fund-Next-Day-Predictor
  ASX200-Next-Day-Magnitude-Predictor
  portfolio-optimizatio
  earth2studio
  ausuper-switch
  battleship
)

for repo in "${REPOS[@]}"; do
  if [ -d "$repo/.git" ]; then
    echo "Pulling $repo ..."
    (cd "$repo" && git pull)
  else
    echo "Cloning $repo ..."
    git clone "https://github.com/eewnah1/$repo.git" "$repo"
  fi
done

echo "Done. Open dashboards.code-workspace in VS Code."
