# Failure handling evidence

A single request exercised the actual FastAPI endpoint and all five production adapters. RESPX mocked every provider call. Mastodon returned HTTP 401, and each of the other four adapters completed successfully. No live publishing took place.

## Request and response

```json
{
  "message": "Offline evidence https://example.com"
}
```

HTTP 200

```json
{
  "success": true,
  "results": [
    {
      "platform": "Bluesky",
      "status": "success",
      "posted_url": "https://bsky.app/profile/evidence.bsky.social/post/mock-post",
      "public_access": true,
      "date": "2026-11-16",
      "time": "21:57:25",
      "error": null
    },
    {
      "platform": "Mastodon",
      "status": "failed",
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "Authentication failed"
    },
    {
      "platform": "Dev.to",
      "status": "success",
      "posted_url": "https://dev.to/evidence-mock/demo",
      "public_access": true,
      "date": "2026-11-16",
      "time": "21:57:25",
      "error": null
    },
    {
      "platform": "GitHub Gist",
      "status": "success",
      "posted_url": "https://gist.github.com/evidence-mock/example",
      "public_access": true,
      "date": "2026-11-16",
      "time": "21:57:25",
      "error": null
    },
    {
      "platform": "Telegram",
      "status": "success",
      "posted_url": "https://t.me/evidence_mock/123",
      "public_access": true,
      "date": "2026-11-16",
      "time": "21:57:25",
      "error": null
    }
  ]
}
```

## Outbound publishing attempts

| Platform | Attempts | Result |
| --- | ---: | --- |
| Bluesky | 1 | success |
| Mastodon | 1 | failed |
| Dev.to | 1 | success |
| GitHub Gist | 1 | success |
| Telegram | 1 | success |

The Bluesky login call was also intercepted once. Every result included all seven response fields.
