# HTTP AI review runner

The runner executes exactly three isolated OpenAI-compatible reviewer profiles and writes the JSONL files consumed by `benchmark build-provisional-review`.

## Safety and provenance

- Remote endpoints must use HTTPS.
- Plain HTTP is accepted only for loopback hosts such as `localhost`, `127.0.0.1`, and `::1`.
- Remote API keys are read only from named environment variables.
- Loopback reviewers may omit `api_key_env` because the local Ollama API does not require authentication.
- Each request asks for a strict JSON schema derived from `ReviewerDecision`.
- Each returned decision is validated against that schema and must preserve the exact evidence `external_id`.
- Reviewer files are replaced only after all three profiles complete successfully.
- AI outputs remain provisional and are not human-approved ground truth.

## Local Ollama configuration

Create a local file such as `local/reviewers-ollama.json`. Do not commit operational configuration files.

```json
{
  "reviewers": [
    {
      "name": "local-conservative",
      "endpoint": "http://127.0.0.1:11434/v1/chat/completions",
      "model": "qwen3:1.7b",
      "system_prompt": "Assess only explicit evidence of a real user problem. Be conservative. Return only the required JSON object.",
      "temperature": 0,
      "timeout_seconds": 180,
      "retries": 1,
      "reasoning_effort": "none"
    },
    {
      "name": "local-opportunity",
      "endpoint": "http://127.0.0.1:11434/v1/chat/completions",
      "model": "qwen3:1.7b",
      "system_prompt": "Assess independently whether the evidence describes a recurring customer pain or workaround. Return only the required JSON object.",
      "temperature": 0.1,
      "timeout_seconds": 180,
      "retries": 1,
      "reasoning_effort": "none"
    },
    {
      "name": "local-skeptical",
      "endpoint": "http://127.0.0.1:11434/v1/chat/completions",
      "model": "qwen3:1.7b",
      "system_prompt": "Challenge weak or ambiguous pain claims and avoid inferring facts not present in the evidence. Return only the required JSON object.",
      "temperature": 0.2,
      "timeout_seconds": 180,
      "retries": 1,
      "reasoning_effort": "none"
    }
  ]
}
```

Using one model with different prompts is useful for a zero-cost pilot, but it is not equivalent to three genuinely independent models. Consensus from these profiles remains provisional.

Run the local passes:

```powershell
.\.venv\Scripts\python.exe -m painfinder.ai_review_http `
  --blind-packet output\pilot-review-packet.csv `
  --config .\local\reviewers-ollama.json `
  --output-directory output\ai-reviews
```

This writes:

- `output/ai-reviews/reviewer-1.jsonl`
- `output/ai-reviews/reviewer-2.jsonl`
- `output/ai-reviews/reviewer-3.jsonl`

## Remote provider configuration

Remote profiles must use HTTPS and name an environment variable containing the API key:

```json
{
  "name": "remote-reviewer",
  "endpoint": "https://provider.example/v1/chat/completions",
  "model": "model-name",
  "api_key_env": "PAINFINDER_REVIEWER_KEY",
  "system_prompt": "Review independently and return only the required JSON object.",
  "temperature": 0,
  "timeout_seconds": 60,
  "retries": 2
}
```

Never put a secret value inside the configuration file.

## Build consensus

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark build-provisional-review `
  --blind-packet output\pilot-review-packet.csv `
  --reviewer-output output\ai-reviews\reviewer-1.jsonl `
  --reviewer-output output\ai-reviews\reviewer-2.jsonl `
  --reviewer-output output\ai-reviews\reviewer-3.jsonl
```
