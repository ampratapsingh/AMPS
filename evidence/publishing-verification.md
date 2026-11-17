# Publishing verification

Checked on 17 November 2026 (Asia/Kolkata). Publication timestamps below are UTC and come from the published records.

All five test items exist, match the approved content, and are accessible without signing in. Each public post URL returned HTTP 200, and the API or public preview independently returned the matching content.

## Published items

| Platform | Account or channel | Public post | Published at (UTC) | Content evidence |
| --- | --- | --- | --- | --- |
| Bluesky | `@batxdev.bsky.social` | [Post](https://bsky.app/profile/batxdev.bsky.social/post/3n2hf4gtezn2g) | `2026-11-16 20:39:04.609` | Matching author and post text. Timestamp from the record's `createdAt`. [Public API response](https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts?uris=at%3A%2F%2Fdid%3Aplc%3Aavyf5pzqbbus64jabpg62iex%2Fapp.bsky.feed.post%2F3n2hf4gtezn2g) |
| Mastodon | `@batxdev@mastodon.social` | [Status](https://mastodon.social/@batxdev/117628046130441119) | `2026-11-16 20:39:03.741` | Matching author and rendered text. API visibility was `public`. Timestamp from `created_at`. [Public API response](https://mastodon.social/api/v1/statuses/117628046130441119) |
| Dev.to | `batxdev` | [Article](https://dev.to/batxdev/integration-test-for-the-multi-platform-posting-system-demo-1hb3) | `2026-11-16 20:39:03` | Matching author, title, and Markdown body. Timestamp from `published_at`. [Public API response](https://dev.to/api/articles/batxdev/integration-test-for-the-multi-platform-posting-system-demo-1hb3) |
| GitHub Gist | `batxdev` | [Gist](https://gist.github.com/batxdev/34b97b2833c549bd88021cea62d22f7d) | `2026-11-16 20:39:04` | Matching owner, description, and `message.md` content. API returned `public: true`. Timestamp from `created_at`. [Public API response](https://api.github.com/gists/34b97b2833c549bd88021cea62d22f7d) |
| Telegram | AMPS (`@amps_publisher`) | [Channel message](https://t.me/amps_publisher/2) | `2026-11-16 20:39:04` | Matching channel, message ID, and rendered text in the public widget. Timestamp from the widget's `time[datetime]`. [Public widget](https://t.me/amps_publisher/2?embed=1) |

The retrieved posts matched this body:

```text
Integration test for the multi-platform posting system demo. Visit https://example.com
```

The Dev.to title and GitHub Gist description also matched the approved text: `Integration test for the multi-platform posting system demo.`

## FastAPI endpoint evidence

The approved live run submitted one `POST /posting` with the message above to the actual `app.main:app` through HTTPX `ASGITransport`. The application's lifespan built the real adapters for the five approved platforms. The request went through FastAPI routing, validation, and the posting service, which called the live provider APIs. The endpoint returned HTTP 200 with `success: true` and five successful results. The outbound request log recorded one publishing attempt per platform. The links above were returned by that endpoint response and verified separately.

The live request used in-process ASGI, so it did not traverse a TCP listener. A separate loopback check ran `uvicorn app.main:app --host 0.0.0.0 --port 4000` with all adapters disabled. On port 4000, Swagger UI returned HTTP 200, OpenAPI listed `POST /posting` as the only business route, an invalid request returned HTTP 422, and a valid request returned HTTP 200.

## Screenshots

- [Swagger UI](screenshots/swagger-ui.png) shows the running local documentation with the posting operation expanded. Publishing adapters were disabled for this capture.
- [API success](screenshots/api-success.png) shows the JSON returned by the original approved live request, rendered in a read-only browser view for the capture.
- The five public pages were captured in a fresh, signed-out browser profile. [Bluesky](screenshots/bluesky.png), [Mastodon](screenshots/mastodon.png), [Dev.to](screenshots/devto.png), [GitHub Gist](screenshots/github-gist.png), [Telegram public widget](screenshots/telegram.png)
- [Test results](screenshots/test-results.png) shows the summary from the new offline run. [Complete pytest output](test-results.txt)

## Duplicate check

The checks read each listing through its final page and compared the content of distinct items against the approved body. Each listing contained the expected post and zero additional matches. The scope was the approved accounts' visible published history and Telegram's public channel history.

| Platform | Listing checked | Items checked | Matching items |
| --- | --- | ---: | ---: |
| Bluesky | Public author feed, filtered to posts authored by the account | 1 | 1 |
| Mastodon | Public account statuses, excluding boosts | 1 | 1 |
| Dev.to | Authenticated published-article listing | 1 | 1 |
| GitHub Gist | Public account gists, including file contents | 1 | 1 |
| Telegram | Public channel history | 2 | 1 |

## Failures or inaccessible posts

None. Dev.to's public article listing initially returned HTTP 429. Its authenticated published-article listing completed the duplicate check, and the article itself remained accessible anonymously.

Verification used read-only requests. No posts were published, deleted, or edited, and no integration code was changed.
