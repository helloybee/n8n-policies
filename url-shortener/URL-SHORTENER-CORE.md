# URL Shortening Service - Core Reference

> **Status**: v1.0.0 - Initial Implementation Complete
> **Target**: DGX Spark Server (Local Deployment)
> **Repository**: `helloybee/n8n-policies`
> **Branch**: `claude/url-shortening-service-0CffM`
> **Last Updated**: 2026-03-21

---

## 1. Project Overview

DGX Spark 서버에서 로컬로 운영 가능한 self-hosted URL 단축 서비스.
외부 의존성 없이 Python Flask + SQLite만으로 동작하며, Docker 배포를 지원한다.

### Design Decisions

| 결정 사항 | 선택 | 이유 |
|---|---|---|
| Language | Python 3.11 | DGX Spark 환경에 기본 탑재, 빠른 개발 |
| Framework | Flask | 경량, 단일 파일 구성 가능 |
| Database | SQLite (WAL mode) | 별도 DB 서버 불필요, 파일 기반 영구 저장 |
| WSGI Server | Gunicorn | Production-ready, multi-worker 지원 |
| Short Code | SHA256 hash → base62 (6자리) | 충돌 확률 극히 낮음, URL-safe |
| Container | Docker + Compose | 재현 가능한 배포, 볼륨으로 데이터 영구화 |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────┐
│                  DGX Spark Server                │
│                                                  │
│   ┌──────────────────────────────────────────┐   │
│   │          Docker Container (optional)      │   │
│   │                                           │   │
│   │   ┌───────────┐     ┌────────────────┐   │   │
│   │   │   Flask    │────▶│   SQLite DB    │   │   │
│   │   │  (app.py)  │     │  (urls.db)     │   │   │
│   │   └─────┬─────┘     └────────────────┘   │   │
│   │         │                                 │   │
│   │   ┌─────┴─────┐                          │   │
│   │   │ Gunicorn   │                          │   │
│   │   │ (2 workers)│                          │   │
│   │   └─────┬─────┘                          │   │
│   └─────────┼────────────────────────────────┘   │
│             │                                     │
│        Port 5000                                  │
└─────────────┼─────────────────────────────────────┘
              │
         Client (curl / browser / n8n)
```

---

## 3. File Structure

```
url-shortener/
├── app.py                 # Main application (Flask + SQLite)
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container image build
├── docker-compose.yml     # Docker Compose orchestration
├── .gitignore             # Excludes __pycache__, *.db, .env
└── README.md              # User-facing documentation
```

---

## 4. Database Schema

```sql
CREATE TABLE urls (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code   TEXT UNIQUE NOT NULL,      -- 6자리 base62 코드 or 커스텀 코드
    original_url TEXT NOT NULL,              -- 원본 URL
    created_at   REAL NOT NULL,             -- Unix timestamp
    click_count  INTEGER DEFAULT 0          -- 리다이렉트 횟수
);

CREATE INDEX idx_short_code ON urls(short_code);
```

- **WAL mode** 활성화: 읽기/쓰기 동시 접근 성능 향상
- DB 파일 기본 위치: `./urls.db` (Docker에서는 `/data/urls.db`)

---

## 5. API Reference

### 5.1 `GET /` - Service Info

```bash
curl http://localhost:5000/
```

**Response** `200`:
```json
{
  "service": "URL Shortener",
  "version": "1.0.0",
  "endpoints": {
    "POST /shorten": "Create a short URL",
    "GET /<code>": "Redirect to original URL",
    "GET /stats/<code>": "Get URL statistics",
    "GET /api/urls": "List all URLs"
  }
}
```

### 5.2 `POST /shorten` - Create Short URL

```bash
curl -X POST http://localhost:5000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.nvidia.com/dgx/spark-user-guide/index.html"}'
```

**Request Body**:
```json
{
  "url": "https://example.com/long/path",      // required
  "custom_code": "mylink"                       // optional (2-20 chars, alphanumeric + -_)
}
```

**Response** `201` (new) / `200` (existing):
```json
{
  "short_url": "http://localhost:5000/abc123",
  "short_code": "abc123",
  "original_url": "https://example.com/long/path",
  "existing": false
}
```

**Errors**: `400` (missing/invalid URL), `409` (custom code conflict)

### 5.3 `GET /<code>` - Redirect

```bash
curl -L http://localhost:5000/abc123
```

**Response**: `302` redirect to original URL. `click_count` incremented.

### 5.4 `GET /stats/<code>` - URL Statistics

```bash
curl http://localhost:5000/stats/abc123
```

**Response** `200`:
```json
{
  "short_code": "abc123",
  "short_url": "http://localhost:5000/abc123",
  "original_url": "https://example.com/long/path",
  "created_at": 1742572800.123,
  "click_count": 42
}
```

### 5.5 `GET /api/urls` - List All URLs

```bash
curl http://localhost:5000/api/urls
```

**Response** `200`: Array of URL objects (최근 100개, 생성일 역순)

### 5.6 `DELETE /api/urls/<code>` - Delete URL

```bash
curl -X DELETE http://localhost:5000/api/urls/abc123
```

**Response** `200`: `{"message": "Deleted successfully"}`

---

## 6. Configuration (Environment Variables)

| Variable | Default | Description |
|---|---|---|
| `URL_SHORTENER_DB` | `urls.db` | SQLite 데이터베이스 파일 경로 |
| `URL_SHORTENER_BASE_URL` | `http://localhost:5000` | 생성되는 단축 URL의 base URL |
| `URL_SHORTENER_CODE_LENGTH` | `6` | 자동 생성 코드 길이 |
| `PORT` | `5000` | 서버 포트 |
| `HOST` | `0.0.0.0` | 바인드 주소 |
| `DEBUG` | `false` | Flask 디버그 모드 |

---

## 7. Deployment Guide

### 7.1 Direct Run (개발/테스트)

```bash
cd url-shortener
pip install -r requirements.txt
python app.py
```

### 7.2 Production (Gunicorn)

```bash
cd url-shortener
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:5000 --workers 2 app:app --preload
```

### 7.3 Docker

```bash
cd url-shortener
docker compose up -d
```

### 7.4 DGX Spark Specific Notes

- GPU 불필요 (CPU-only 서비스)
- 내부 네트워크 전용: `HOST=127.0.0.1` 설정
- 외부 접근 시: `URL_SHORTENER_BASE_URL=http://<DGX_SPARK_IP>:5000`
- systemd service 등록 시 자동 시작 가능

---

## 8. Core Algorithm: Short Code Generation

```python
def generate_short_code(url: str) -> str:
    hash_input = f"{url}{time.time()}".encode()    # URL + timestamp로 유니크성 확보
    hash_hex = hashlib.sha256(hash_input).hexdigest()
    num = int(hash_hex[:12], 16)                   # 48-bit slice
    code = ""
    for _ in range(SHORT_CODE_LENGTH):             # base62 인코딩
        code += ALPHABET[num % len(ALPHABET)]
        num //= len(ALPHABET)
    return code
```

- **62^6 = ~56.8 billion** 조합 가능
- timestamp를 포함하여 같은 URL도 다른 코드 생성 가능 (collision 방지)
- DB에서 collision 체크 후 재생성 루프

---

## 9. Key Implementation Details

### Validation
- URL은 반드시 `http://` 또는 `https://`로 시작해야 함
- Custom code: 2~20자, `[a-zA-Z0-9-_]`만 허용
- 이미 단축된 URL은 기존 코드 반환 (중복 방지)

### Concurrency
- SQLite WAL mode로 읽기/쓰기 동시 접근 지원
- Gunicorn 2 worker 기본 설정 (DGX Spark CPU 코어에 맞게 조절 가능)

### Data Persistence
- Docker: named volume `url_data` → `/data/urls.db`
- Direct run: `./urls.db` (working directory)

---

## 10. Git History

| Commit | Description |
|---|---|
| `7eb8186` | Initial implementation - Flask + SQLite URL shortener with Docker support |

**Branch**: `claude/url-shortening-service-0CffM` (from `main` @ `eab1ae2`)

---

## 11. Roadmap / Future Enhancements

아래는 아직 구현되지 않은 향후 개선 사항:

- [ ] **Web UI**: 브라우저에서 URL 입력/관리할 수 있는 프론트엔드
- [ ] **n8n 연동**: n8n workflow에서 HTTP Request 노드로 단축 URL 생성
- [ ] **만료 기능**: TTL 설정으로 일정 시간 후 자동 삭제
- [ ] **QR 코드 생성**: 단축 URL에 대한 QR 코드 자동 생성
- [ ] **인증/API Key**: 무단 사용 방지를 위한 API 키 인증
- [ ] **클릭 분석**: User-Agent, IP, timestamp 기반 상세 통계
- [ ] **Bulk import/export**: CSV/JSON으로 대량 URL 관리
- [ ] **Rate limiting**: 요청 빈도 제한
- [ ] **Custom domain**: 자체 도메인 연결 지원

---

## 12. Source Code Reference

전체 소스는 `url-shortener/app.py` 단일 파일에 포함:

| Line | Function | Description |
|---|---|---|
| 22-27 | `get_db()` | SQLite 연결 생성 (WAL mode) |
| 30-44 | `init_db()` | 테이블/인덱스 생성 |
| 47-56 | `generate_short_code()` | SHA256 → base62 코드 생성 |
| 59-65 | `is_valid_url()` | URL 유효성 검증 |
| 68-80 | `index()` | `GET /` 서비스 정보 |
| 83-136 | `shorten()` | `POST /shorten` URL 단축 |
| 139-155 | `stats()` | `GET /stats/<code>` 통계 |
| 158-174 | `list_urls()` | `GET /api/urls` 전체 목록 |
| 177-184 | `delete_url()` | `DELETE /api/urls/<code>` 삭제 |
| 187-200 | `redirect_url()` | `GET /<code>` 리다이렉트 |
| 203-207 | `__main__` | 서버 시작 진입점 |
