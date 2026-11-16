# Automated Multi-Platform Posting System

A FastAPI service that publishes a message with one CTA link to multiple platforms.

## Setup

Create a virtual environment, install `requirements.txt`, and copy `.env.example` to `.env`.

## Run

```sh
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Open [Swagger UI](http://localhost:4000/docs).
