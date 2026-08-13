# eewnah1 Dashboards Workspace

One workspace to clone, run, and monitor all `eewnah1` dashboard repos in VS Code and Google Colab.

## VS Code

```bash
git clone https://github.com/eewnah1/Algotrading-Platform.git
cd Algotrading-Platform/workspace
./clone_all.sh
code dashboards.code-workspace
```

The workspace file loads the `Algotrading-Platform` repo and every cloned dashboard repo as folders.

## Google Colab

Open the dashboard health/check notebook directly in Colab:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/eewnah1/Algotrading-Platform/blob/main/workspace/notebooks/dashboards_colab.ipynb)

The notebook clones every repo under `/content/Algotrading-Platform/workspace/repos` and checks each live dashboard `/health` endpoint.

## Live dashboard URLs

See `workspace/data/live_urls.json` for the current public no-auth URLs.

## Repos included

All `eewnah1` dashboard and predictor repos are referenced in `clone_all.sh` and `dashboards.code-workspace`.

## License

Same as the individual repos (Apache-2.0 where specified).
