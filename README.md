# Automated Multi-Platform Posting System

A FastAPI service that takes a short message with one call-to-action (CTA) URL and publishes it through the official APIs for Bluesky, Mastodon, Dev.to, GitHub Gist, and Telegram. One request returns a separate result for each enabled platform.

## Features

- One publishing endpoint with interactive Swagger documentation.
- Message validation with a 200-character limit and exactly one HTTP(S) CTA.
- Concurrent publication with independent timeouts and error handling.
- Public URL checks, UTC timestamps, and readable per-platform error details.
- Offline tests and evidence from a verified five-platform live run.

## Technology stack

Python 3.10+, FastAPI, Uvicorn, Pydantic v2, Pydantic Settings, and async HTTPX. The tests use pytest, pytest-asyncio, and RESPX.

```text
POST /posting --> Validate message --> PostingService
                                          |
                                          +--> Bluesky
                                          +--> Mastodon
                                          +--> Dev.to
                                          +--> GitHub Gist
                                          +--> Telegram
                                          |
                                  HTTP 200 with results
```

## Project structure

```text
automated-posting/
├── app/
│   ├── main.py, schemas.py, validation.py
│   ├── config.py, exceptions.py
│   ├── platforms/
│   │   ├── base.py, registry.py
│   │   ├── bluesky.py, mastodon.py, devto.py, gist.py, telegram.py
│   │   └── telegraph.py, discord.py
│   └── services/posting_service.py
├── tests/
│   ├── conftest.py, test_validation.py, test_posting.py
│   └── test_posting_service.py, test_platforms.py
├── evidence/
│   ├── publishing-verification.md, api-validation.md
│   ├── failure-handling.md, test-results.txt
│   └── screenshots/
├── .env.example, .gitignore, pytest.ini, requirements.txt
└── README.md
```

## Installation

From the root of a fresh clone, create a virtual environment and install the pinned dependencies.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

### Configure the five submission platforms

Edit the copied `.env` and set `ENABLED_PLATFORMS` to the following value. The template also enables Telegraph, so this step sets the submission's five destinations.

```dotenv
ENABLED_PLATFORMS=bluesky,mastodon,devto,gist,telegram
PLATFORM_TIMEOUT_SECONDS=15
```

Replace the placeholders for the platforms you enable. `.env` is git-ignored, and system environment variables take precedence over values in the file. A missing credential produces a failure for that platform. An unknown adapter key prevents startup.

| Platform | Environment variables | Setup |
| --- | --- | --- |
| Bluesky | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | Use your profile handle. Open Settings → Privacy and Security → App Passwords and generate an app password. [AT Protocol post guide](https://atproto.com/guides/post-richtext) |
| Mastodon | `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN` | Use the origin of your instance, which defaults to `https://mastodon.social`. Under Preferences → Development, create an application with `write:statuses` and copy the access token. [Status API](https://docs.joinmastodon.org/methods/statuses/#create) |
| Dev.to | `DEVTO_API_KEY` | Generate a DEV API key under Settings → Extensions. [Forem article API](https://developers.forem.com/api/v1#tag/articles/operation/createArticle) |
| GitHub Gist | `GITHUB_TOKEN` | In GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens, generate a token with user permission **Gists: write**. [Create a gist](https://docs.github.com/en/rest/gists/gists?apiVersion=2022-11-28#create-a-gist) |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL` | Create a bot with `@BotFather`, add it as a channel admin with permission to post, and use the public channel username, with or without `@`. [Bot API](https://core.telegram.org/bots/api#sendmessage) |

The repository also contains optional Telegraph and Discord adapters. For Telegraph, `TELEGRAPH_ACCESS_TOKEN` reuses an account across restarts, while an empty token triggers account creation when Telegraph is enabled. Discord uses `DISCORD_WEBHOOK_URL` and `DISCORD_GUILD_ID`. These adapters are outside the five-platform submission configuration.

## Run the API

Run the server from the repository root with the virtual environment active.

```sh
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Open [Swagger UI](http://localhost:4000/docs) or the [OpenAPI schema](http://localhost:4000/openapi.json). For a local walkthrough with publishing disabled, run `ENABLED_PLATFORMS="" uvicorn app.main:app --host 0.0.0.0 --port 4000`. With publishing enabled, requests use the configured accounts, so restrict access to the running server.

## POST /posting

Send JSON with one required field, `message`, whose value is a string. The server selects destinations through `ENABLED_PLATFORMS`.

### Request example

This is the request body used in the recorded live test. Sending it with real credentials and adapters enabled creates public posts.

```sh
curl -X POST http://localhost:4000/posting \
  -H 'Content-Type: application/json' \
  -d '{"message":"Integration test for the multi-platform posting system demo. Visit https://example.com"}'
```

### Successful response (HTTP 200)

The five-platform live test returned this response.

```json
{
  "success": true,
  "results": [
    {
      "platform": "Bluesky",
      "status": "success",
      "posted_url": "https://bsky.app/profile/batxdev.bsky.social/post/3n2hf4gtezn2g",
      "public_access": true,
      "date": "2026-11-16",
      "time": "20:39:04",
      "error": null
    },
    {
      "platform": "Mastodon",
      "status": "success",
      "posted_url": "https://mastodon.social/@batxdev/117628046130441119",
      "public_access": true,
      "date": "2026-11-16",
      "time": "20:39:04",
      "error": null
    },
    {
      "platform": "Dev.to",
      "status": "success",
      "posted_url": "https://dev.to/batxdev/integration-test-for-the-multi-platform-posting-system-demo-1hb3",
      "public_access": true,
      "date": "2026-11-16",
      "time": "20:39:03",
      "error": null
    },
    {
      "platform": "GitHub Gist",
      "status": "success",
      "posted_url": "https://gist.github.com/batxdev/34b97b2833c549bd88021cea62d22f7d",
      "public_access": true,
      "date": "2026-11-16",
      "time": "20:39:05",
      "error": null
    },
    {
      "platform": "Telegram",
      "status": "success",
      "posted_url": "https://t.me/amps_publisher/2",
      "public_access": true,
      "date": "2026-11-16",
      "time": "20:39:05",
      "error": null
    }
  ]
}
```

Every valid request returns HTTP 200, including when all platforms fail. The top-level `success` is true if any platform publishes. Each result includes the platform name, `status` (`success` or `failed`), posted URL, public-access flag, UTC date and time, and error detail. On failure, `posted_url`, `date`, and `time` are null, `public_access` is false, and `error` explains the failure. Successful results have a null `error`.

### Input validation

- The message is trimmed first. It must be nonempty and at most 200 characters after trimming.
- Exactly one CTA is required. Plain URLs and inline Markdown links count, including when separated by commas or other punctuation. Repeated URLs count separately.
- The URL must use HTTP or HTTPS. Valid domain names, internationalized domains, `localhost`, IPv4 addresses, and bracketed IPv6 addresses are accepted. Paths, queries, fragments, and valid ports are supported. The syntax check makes no DNS or HTTP requests.
- Invalid input, malformed JSON, and invalid UTF-8 return the custom HTTP 422 response. For example, a message containing two CTA URLs returns the following.

```json
{
  "success": false,
  "error": "validation_error",
  "details": [
    {
      "field": "message",
      "message": "message must contain exactly one link (found 2)"
    }
  ]
}
```

### Independent failure handling

The service runs enabled adapters concurrently and returns results in registry order. Each adapter has its own timeout, and a failure on one platform leaves the others running. Authentication failures, rate limits, timeouts, network errors, and provider errors become individual failed results. The mocked failure test returned HTTP 200 with four successes and the failed Mastodon result below.

```json
{
  "platform": "Mastodon",
  "status": "failed",
  "posted_url": null,
  "public_access": false,
  "date": null,
  "time": null,
  "error": "Authentication failed"
}
```

Publishing requests are attempted once to avoid duplicates after an ambiguous timeout. After publishing, the service checks the URL without credentials or session cookies and follows redirects. It retries a non-2xx probe once if time remains. A failed probe leaves the publication successful with `public_access: false`. Provider error details are shortened and redacted. HTTP client request logs are suppressed below warning to protect credentials that appear in provider URLs.

## Testing

Run the suite from the repository root with the virtual environment active.

```sh
python -m pytest
```

**92 passed, 0 failed.** The suite uses HTTPX ASGI transport and fake credentials. RESPX intercepts outbound HTTP requests and fails tests on unexpected calls. Coverage includes request validation, provider payloads and error mapping, timeouts, partial and total failure, and public-access probes. No live credentials are needed.

## Actual publishing verification

The approved live run exercised FastAPI's `POST /posting` route and created one item per platform. Each item was retrieved independently, matched the approved text, and was accessible without signing in. A follow-up history check found one matching item per account or channel.

| Platform | Published at (UTC, from published record) | Public result | Evidence |
| --- | --- | --- | --- |
| Bluesky | 2026-11-16 20:39:04.609 | [Post](https://bsky.app/profile/batxdev.bsky.social/post/3n2hf4gtezn2g) | [Screenshot](evidence/screenshots/bluesky.png) |
| Mastodon | 2026-11-16 20:39:03.741 | [Status](https://mastodon.social/@batxdev/117628046130441119) | [Screenshot](evidence/screenshots/mastodon.png) |
| Dev.to | 2026-11-16 20:39:03 | [Article](https://dev.to/batxdev/integration-test-for-the-multi-platform-posting-system-demo-1hb3) | [Screenshot](evidence/screenshots/devto.png) |
| GitHub Gist | 2026-11-16 20:39:04 | [Gist](https://gist.github.com/batxdev/34b97b2833c549bd88021cea62d22f7d) | [Screenshot](evidence/screenshots/github-gist.png) |
| Telegram | 2026-11-16 20:39:04 | [Channel message](https://t.me/amps_publisher/2) | [Screenshot](evidence/screenshots/telegram.png) |

The timestamps in the live API response mark when each successful result was recorded by the service. The table uses the timestamps in the published records.

## Evidence

| File | Contents |
| --- | --- |
| [Publishing verification](evidence/publishing-verification.md) | Provider read-back links, publication timestamps, anonymous access checks, duplicate checks, and evidence that the live run used the actual endpoint. |
| [API validation](evidence/api-validation.md) | Actual FastAPI responses for the accepted 200-character message and six rejection cases, with provider calls mocked. |
| [Failure handling](evidence/failure-handling.md) | A mocked Mastodon authentication failure alongside four successful results in the same request. |
| [Offline test output](evidence/test-results.txt) | Complete pytest output, including pass and failure counts. |
| [Screenshots](evidence/screenshots/) | [Swagger UI](evidence/screenshots/swagger-ui.png), the [recorded live API response](evidence/screenshots/api-success.png), five public posts, and the [pytest summary](evidence/screenshots/test-results.png). |

## Scope and assumptions

- The submission uses provider APIs that publish public content. LLM APIs are outside the publishing scope.
- The Bluesky adapter uses the `bsky.social` login and publishing endpoints.
- Dev.to and Telegraph derive a short title from the text outside the CTA, with `Shared link` as the fallback.
- Bare hostnames other than `localhost` are rejected because they depend on local DNS search configuration. Provider moderation, duplicate detection, and rate limits can independently affect live requests.

## Platforms considered and rejected

November 2026 review.

| Platform | Reason rejected |
| --- | --- |
| X / Twitter | The pay-per-use API has no free publishing tier, and creating posts with links costs more. [X API pricing](https://docs.x.com/x-api/getting-started/pricing) |
| Reddit | New Data API access requires explicit approval. [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) |
| Medium | The OAuth API docs are archived, and Medium does not accept new integrations. [Medium API docs](https://github.com/Medium/medium-api-docs) |
| Hashnode | API publishing has required a paid Pro plan since May 2026. [Hashnode changelog](https://hashnode.com/changelog/2026-05-13-graphql-api-paid-access) |
| LinkedIn | OAuth and 60-day access tokens add lifecycle work. Programmatic refresh is limited to approved partners. [LinkedIn refresh tokens](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens) |
| Threads | Requires a Meta app and OAuth, with 60-day long-lived tokens and App Review for use beyond tester accounts. [Threads API](https://developers.facebook.com/docs/threads/) |
