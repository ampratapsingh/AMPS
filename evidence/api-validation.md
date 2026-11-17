# API validation evidence

Recorded responses from the actual FastAPI `POST /posting` route over HTTPX ASGI transport. RESPX intercepted all provider HTTP calls. The 200-character request used a mocked Gist adapter response. The rejected requests made zero outbound calls.

## 200-character acceptance

```json
{
  "message": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa https://example.com"
}
```

HTTP 200

```json
{
  "success": true,
  "results": [
    {
      "platform": "GitHub Gist",
      "status": "success",
      "posted_url": "https://gist.github.com/evidence-mock/example",
      "public_access": true,
      "date": "2026-11-16",
      "time": "21:57:25",
      "error": null
    }
  ]
}
```

## 201-character rejection

```json
{
  "message": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa https://example.com"
}
```

HTTP 422

```json
{
  "success": false,
  "error": "validation_error",
  "details": [
    {
      "field": "message",
      "message": "message must not exceed 200 characters (got 201)"
    }
  ]
}
```

## Missing CTA rejection

```json
{
  "message": "No CTA here."
}
```

HTTP 422

```json
{
  "success": false,
  "error": "validation_error",
  "details": [
    {
      "field": "message",
      "message": "message must contain exactly one link (found 0)"
    }
  ]
}
```

## Multiple CTA rejection

```json
{
  "message": "Compare https://example.com and https://example.org"
}
```

HTTP 422

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

## Adjacent Markdown CTA rejection

```json
{
  "message": "[First](https://example.com/a),[Second](https://example.org/b)"
}
```

HTTP 422

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

## Invalid URL rejection

```json
{
  "message": "Visit https://[v1.example]/path"
}
```

HTTP 422

```json
{
  "success": false,
  "error": "validation_error",
  "details": [
    {
      "field": "message",
      "message": "link is not a valid URL"
    }
  ]
}
```

## Invalid UTF-8 rejection

```text
b'{"message":"Visit https://example.com \xff"}'
```

HTTP 422

```json
{
  "success": false,
  "error": "validation_error",
  "details": [
    {
      "field": "body",
      "message": "body must be valid JSON"
    }
  ]
}
```
