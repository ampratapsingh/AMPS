# Automated Multi-Platform Posting System

A FastAPI service that publishes a message of up to 200 characters with one CTA link. It publishes to Bluesky, Mastodon, Dev.to, GitHub Gist, Telegram, and Telegraph by default. Discord is opt-in. A valid request returns a result for each enabled platform, including any provider failures.

The original brief's “supported LLM platforms” wording is out of scope. The publishing integrations use APIs for creating public posts, while LLM APIs generate text.

```text
POST /posting
    |
    v
Pydantic validation --> HTTP 422 on invalid input
    |
    v
PostingService.publish(PostPayload)
    |
    +--> Bluesky       +--> GitHub Gist
    +--> Mastodon      +--> Telegram
    +--> Dev.to        +--> Telegraph
                       +--> Discord (opt-in)
    |
    v
HTTP 200 with results in registry order
```

## Setup

Use Python 3.10 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Replace the placeholders in `.env` for the platforms you plan to use. The file is git-ignored. The process environment takes precedence over the file.

| Platform | Environment variables | How to obtain them |
| --- | --- | --- |
| Bluesky | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | Use your profile handle. Open Settings → Privacy and Security → App Passwords and generate an app password. [AT Protocol post guide](https://atproto.com/guides/post-richtext) |
| Mastodon | `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN` | Use the origin of your instance, which defaults to `https://mastodon.social`. Under Preferences → Development, create an application with `write:statuses` and copy the access token. [Status API](https://docs.joinmastodon.org/methods/statuses/#create) |
| Dev.to | `DEVTO_API_KEY` | Generate a DEV API key under Settings → Extensions. [Forem article API](https://developers.forem.com/api/v1#tag/articles/operation/createArticle) |
| GitHub Gist | `GITHUB_TOKEN` | In GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens, generate a token with user permission **Gists: write**. [Create a gist](https://docs.github.com/en/rest/gists/gists?apiVersion=2022-11-28#create-a-gist) |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL` | Create a bot with `@BotFather`, add it as a channel admin with permission to post, and use the public channel username, with or without `@`. [Bot API](https://core.telegram.org/bots/api#sendmessage) |
| Telegraph | `TELEGRAPH_ACCESS_TOKEN` | Optional. Use the `access_token` returned by `createAccount` to reuse an account across restarts. With the value blank, the service lazily creates one account per process and caches it in memory. [Telegraph API](https://telegra.ph/api#createAccount) |
| Discord | `DISCORD_WEBHOOK_URL`, `DISCORD_GUILD_ID` | Create a webhook under the target channel's Settings → Integrations → Webhooks and copy its URL. Enable Developer Mode, right-click the server and select **Copy Server ID**. Add `discord` to `ENABLED_PLATFORMS`. [Execute webhook](https://docs.discord.com/developers/resources/webhook#execute-webhook) |

| Setting | Default | Behavior |
| --- | --- | --- |
| `ENABLED_PLATFORMS` | `bluesky,mastodon,devto,gist,telegram,telegraph` | Comma-separated adapter keys. An unknown key prevents startup. An empty list publishes nowhere. |
| `PLATFORM_TIMEOUT_SECONDS` | `15` | Time budget in seconds for each platform, including any time left for the public probe after publishing. |

## Run

```sh
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Open [Swagger UI](http://localhost:4000/docs) to try the endpoint and view its examples. The endpoint uses the credentials of the running process, so keep access to the server restricted to the people who may publish with those credentials.

## API examples

### Request

```sh
curl http://localhost:4000/posting \
  -H 'Content-Type: application/json' \
  -d '{"message":"Check out our latest business platform. https://example.com"}'
```

### Success (HTTP 200)

With only `gist` enabled and its page accessible:

```json
{
  "success": true,
  "results": [
    {
      "platform": "GitHub Gist",
      "status": "success",
      "posted_url": "https://gist.github.com/author/abc123",
      "public_access": true,
      "date": "2026-11-16",
      "time": "10:30:00",
      "error": null
    }
  ]
}
```

### Partial failure (HTTP 200)

With `gist,telegram` enabled and Telegram authentication failing:

```json
{
  "success": true,
  "results": [
    {
      "platform": "GitHub Gist",
      "status": "success",
      "posted_url": "https://gist.github.com/author/abc123",
      "public_access": true,
      "date": "2026-11-16",
      "time": "10:30:00",
      "error": null
    },
    {
      "platform": "Telegram",
      "status": "failed",
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "Authentication failed"
    }
  ]
}
```

Every valid request returns HTTP 200. If every adapter fails, the response has `"success": false` and retains the individual results.

### Validation error (HTTP 422)

For `{"message":"Compare https://example.com and https://example.org"}`:

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

## Tests

```sh
pytest
```

The suite uses HTTPX's ASGI transport for API tests and RESPX for outbound calls. Unmocked outbound HTTP requests fail the test. The tests use fake credentials.

## Design decisions

- **One adapter per platform.** Each adapter owns its authentication, outbound request, and URL extraction. One async HTTPX client is shared for the app's lifespan.
- **Concurrent publication and failure isolation.** Each enabled adapter runs with its own timeout. Results always follow registry order: Bluesky, Mastodon, Dev.to, GitHub Gist, Telegram, Telegraph, Discord.
- **One attempt per POST.** A provider can publish successfully even when the client times out. Retrying that request could create a duplicate.
- **UTC timestamps.** Each success records the time when its adapter returns the posted URL, using `YYYY-MM-DD` and `HH:MM:SS`. Failed results have null timestamps.
- **Public access probes.** The service performs an unauthenticated GET with redirects and no session cookies. After a non-2xx response, it retries once after one second if time remains. A 2xx response is a reachability signal. A failed probe leaves the publication successful with `public_access: false`. Discord always reports `false` because message links require login and server membership.
- **Secret redaction.** Credentials use Pydantic `SecretStr`. Provider errors are shortened and redacted before being returned. Logging records each adapter's name, status, and latency. HTTPX and HTTPCore request logs are suppressed below warning to protect tokens in Telegram and Discord URLs.
- **Internal platform selection.** Only `ENABLED_PLATFORMS` controls where posts go. Enabled adapters with missing credentials report a per-platform configuration error.

## Assumptions

- CTA hosts use dotted ASCII DNS labels, including ASCII punycode where applicable. The validator checks URL syntax without making a DNS or HTTP request. Common closing punctuation is removed from the extracted CTA and kept in the post text.
- Missing or nonnumeric rate-limit retry hints produce a generic rate-limit message. The same message may be rejected by a platform's duplicate or spam checks.
- The Bluesky account uses the specified `bsky.social` login and publishing endpoints.
- Dev.to and Telegraph derive titles from up to eight complete words and 80 characters outside the URL. They use “Shared link” if no whole word fits or the message consists only of the URL.
- Missing provider credentials and provider responses are exercised with mocks. Live outcomes depend on account permissions, provider policies, and instance settings.

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

## Demo

- **TODO (author)** Add screenshots of a real Swagger request and the resulting posts.
- **TODO (author)** Add logs from real posting attempts with credentials blurred or removed.
