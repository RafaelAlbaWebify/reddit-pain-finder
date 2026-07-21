# HTTP AI review runner

The runner executes exactly three isolated OpenAI-compatible HTTP reviewer profiles and writes the JSONL files consumed by `benchmark build-provisional-review`.

## Safety and provenance

- Endpoints must use HTTPS.
- API keys are read only from named environment variables.
- Configuration files contain no secret values.
- Each returned decision is validated against the existing `ReviewerDecision` schema.
- The returned `external_id` must match the evidence item exactly.
- Reviewer files are replaced only after all three profiles complete successfully.
- AI outputs remain provisional and are not human-approved ground truth.

## Configuration

Create a local JSON file that is not committed with three reviewer profiles:

```json
{
  "reviewers": [
    {
      "name": "reviewer-a",
      "endpoint": "https://provider.example/v1/chat/completions",
      "model": "model-a",
      "api_key_env": "PAINFINDER_REVIEWER_A_KEY",
      "system_prompt": "Assess only the supplied evidence. Return the required JSON object.",
      "temperature": 0,
      "timeout_seconds": 60,
      "retries": 2
    },
    {
      "name": "reviewer-b",
      "endpoint": "https://provider.example/v1/chat/completions",
      "model": "model-b",
      "api_key_env": "PAINFINDER_REVIEWER_B_KEY",
      "system_prompt": "Review independently and conservatively. Return only the required JSON object.",
      "temperature": 0,
      "timeout_seconds": 60,
      "retries": 2
    },
    {
      "name": "reviewer-c",
      "endpoint": "https://provider.example/v1/chat/completions",
      "model": "model-c",
      "api_key_env": "PAINFINDER_REVIEWER_C_KEY",
      "system_prompt": "Challenge ambiguous pain claims. Return only the required JSON object.",
      "temperature": 0,
      "timeout_seconds": 60,
      "retries": 2
    }
  ]
}
```

The three profiles may use different providers or models as long as each endpoint accepts an OpenAI-compatible chat-completions request and returns `choices[0].message.content` containing one JSON decision.

## Run

Set the environment variables in the current PowerShell session:

```powershell
$env:PAINFINDER_REVIEWER_A_KEY = "..."
$env:PAINFINDER_REVIEWER_B_KEY = "..."
$env:PAINFINDER_REVIEWER_C_KEY = "..."
```

Execute the three passes:

```powershell
.\.venv\Scripts\python.exe -m painfinder.ai_review_http `
  --blind-packet output\reviewer-a.csv `
  --config .\local\reviewers.json `
  --output-directory output\ai-reviews
```

This writes:

- `output/ai-reviews/reviewer-1.jsonl`
- `output/ai-reviews/reviewer-2.jsonl`
- `output/ai-reviews/reviewer-3.jsonl`

Then build consensus and the human approval queue:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark build-provisional-review `
  --blind-packet output\reviewer-a.csv `
  --reviewer-output output\ai-reviews\reviewer-1.jsonl `
  --reviewer-output output\ai-reviews\reviewer-2.jsonl `
  --reviewer-output output\ai-reviews\reviewer-3.jsonl
```

Never commit the local configuration when it contains operational endpoint details, and never place API keys inside it.
