# Repository metadata for discoverability

These were applied on 2026-09-12 (repository renamed from `shimo` to `cloudcost-analyzer`, description, homepage and topics set). Re-run if anything drifts:

```bash
# Rename the repository to the product slug (old URLs redirect automatically)
gh repo rename cloudcost-analyzer -R Faizullah9181/shimo

# Description shown in search results and on the repo header
gh repo edit --description "AI-powered multi-cloud cost analyzer & FinOps agent for AWS, Azure, GCP and DigitalOcean. Natural-language cost analysis, trends, forecasts and savings recommendations via CLI or web chat (Shimo agent)."

# Topics (GitHub indexes these for search and Explore)
gh repo edit \
  --add-topic cloud-cost --add-topic finops --add-topic cost-optimization \
  --add-topic aws-cost-explorer --add-topic azure-cost-management --add-topic gcp-billing \
  --add-topic digitalocean --add-topic multi-cloud --add-topic ai-agent --add-topic llm \
  --add-topic strands-agents --add-topic fastapi --add-topic react --add-topic bedrock \
  --add-topic cloud-cost-analysis --add-topic cloud-billing --add-topic cost-analyzer

# Homepage: point at the web UI or docs when deployed
gh repo edit --homepage "https://github.com/Faizullah9181/cloudcost-analyzer"
```

Social preview: upload a 1280x640 image under *Settings -> General -> Social preview*
(`frontend/public/social-preview.svg` is a starting point; export it to PNG).

Screenshots in `docs/screenshots/` are generated from a seeded demo database with headless Chrome; the architecture diagram lives in `docs/architecture.excalidraw` (edit at excalidraw.com) with rendered `docs/architecture.svg`/`.png`.

