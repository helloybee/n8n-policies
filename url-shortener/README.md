# URL Shortening Service (DGX Spark Local)

Self-hosted URL shortening service for DGX Spark server local deployment.

## Tech Stack
- **Python 3.11** + **Flask**
- **SQLite** (file-based, no external DB needed)
- **Gunicorn** (production WSGI server)
- **Docker** support included

## Quick Start

### Option 1: Direct Run

```bash
cd url-shortener
pip install -r requirements.txt
python app.py
```

### Option 2: Docker

```bash
cd url-shortener
docker compose up -d
```

Service runs at `http://localhost:5000`.

## API Usage

### Create Short URL
```bash
curl -X POST http://localhost:5000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/very/long/path"}'
```

### Create with Custom Code
```bash
curl -X POST http://localhost:5000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "custom_code": "mylink"}'
```

### Redirect
```bash
curl -L http://localhost:5000/abc123
```

### View Stats
```bash
curl http://localhost:5000/stats/abc123
```

### List All URLs
```bash
curl http://localhost:5000/api/urls
```

### Delete URL
```bash
curl -X DELETE http://localhost:5000/api/urls/abc123
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `URL_SHORTENER_DB` | `urls.db` | SQLite database file path |
| `URL_SHORTENER_BASE_URL` | `http://localhost:5000` | Base URL for generated short links |
| `URL_SHORTENER_CODE_LENGTH` | `6` | Length of generated short codes |
| `PORT` | `5000` | Server port |
| `HOST` | `0.0.0.0` | Server bind address |
| `DEBUG` | `false` | Enable Flask debug mode |

## DGX Spark Deployment Notes

1. DGX Spark에서 Docker로 실행 시 GPU는 불필요 (CPU 서비스)
2. 로컬 네트워크에서만 접근하려면 `HOST=127.0.0.1`로 설정
3. 외부 접근이 필요하면 `URL_SHORTENER_BASE_URL`을 서버 IP로 설정:
   ```bash
   export URL_SHORTENER_BASE_URL=http://192.168.x.x:5000
   ```
4. SQLite DB 파일은 `/data` 볼륨에 영구 저장됨
