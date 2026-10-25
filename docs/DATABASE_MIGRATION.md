# AgroNex AI — Database Architecture & PostgreSQL Migration Guide

## 1. Persistence Overview

AgroNex AI employs a dual-tier persistence architecture designed for zero-setup local deployment with seamless migration to managed cloud PostgreSQL (Supabase / AWS RDS / GCP Cloud SQL).

- **Default / Offline Mode**: Embedded SQLite (`backend/agronex.db`) requires zero external infrastructure or network connectivity. Auto-initialized on startup by `config/local_db.py`.
- **Production / Cloud Mode**: Managed PostgreSQL / Supabase with Row Level Security (RLS), ACID transaction guarantees, horizontal connection pooling, and binary blob storage via Supabase Storage (`crop-images` bucket).

---

## 2. SQLite Schema Specification (`agronex.db`)

### Tables

#### `users`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | UUID identifier |
| `name` | TEXT | NOT NULL | Farmer full name |
| `mobile` | TEXT | UNIQUE NOT NULL | 10-digit Indian mobile number |
| `email` | TEXT | UNIQUE | Optional email address |
| `hashed_password` | TEXT | NOT NULL | Salted bcrypt password hash |
| `location` | TEXT | NULLABLE | District / State (e.g., "Coimbatore, Tamil Nadu") |
| `preferred_language` | TEXT | DEFAULT 'en' | ISO 639-1 code (`'en'` or `'ta'`) |
| `created_at` | TEXT | NOT NULL | ISO 8601 UTC timestamp |

#### `farmer_profiles`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | UUID identifier |
| `user_id` | TEXT | REFERENCES users(id) ON DELETE CASCADE | Associated user |
| `name` | TEXT | NULLABLE | Display name |
| `mobile` | TEXT | NULLABLE | Contact number |
| `farm_size` | REAL | DEFAULT 0.0 | Operational land holding in acres |
| `primary_crop` | TEXT | DEFAULT 'Paddy' | Cultivated crop (e.g. Tomato, Paddy, Corn) |
| `location` | TEXT | NULLABLE | Farm geographical location |
| `preferred_language` | TEXT | DEFAULT 'en' | Preferred UI language (`'en'` or `'ta'`) |
| `notify_weather` | INTEGER | DEFAULT 1 | Boolean flag for daily weather alerts |
| `notify_spray` | INTEGER | DEFAULT 1 | Boolean flag for caution window warnings |
| `notify_schemes` | INTEGER | DEFAULT 1 | Boolean flag for subsidy updates |
| `updated_at` | TEXT | NOT NULL | ISO 8601 UTC timestamp |

#### `crop_analyses`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | UUID identifier |
| `user_id` | TEXT | NULLABLE | Associated user |
| `crop_type` | TEXT | NOT NULL | Identified crop species (e.g., "Tomato") |
| `image_path` | TEXT | NULLABLE | Storage reference URI or local thumbnail path |
| `detected_disease` | TEXT | NOT NULL | Diagnosed pathology or "healthy" |
| `confidence` | REAL | NOT NULL | Model softmax confidence score (0.0 to 1.0) |
| `severity` | TEXT | DEFAULT 'Not determined' | Clinical severity level |
| `risk_level` | TEXT | DEFAULT 'Not determined' | Epidemiological risk rating |
| `quality_status` | TEXT | DEFAULT 'Passed' | Optical quality gate result |
| `weather_context` | TEXT | NULLABLE | Micro-climate conditions snapshot |
| `is_inconclusive` | INTEGER | DEFAULT 0 | 1 if uncertainty threshold triggered |
| `created_at` | TEXT | NOT NULL | ISO 8601 UTC timestamp |

#### `chat_history`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | UUID identifier |
| `user_id` | TEXT | NULLABLE | Associated user |
| `role` | TEXT | NOT NULL | `'user'` or `'ai'` |
| `message` | TEXT | NOT NULL | Text query or response |
| `created_at` | TEXT | NOT NULL | ISO 8601 UTC timestamp |

### Indexes
- `idx_crop_analyses_created_at` on `crop_analyses(created_at DESC)`
- `idx_crop_analyses_user_id` on `crop_analyses(user_id)`
- `idx_chat_history_created_at` on `chat_history(created_at DESC)`
- `idx_chat_history_user_id` on `chat_history(user_id)`
- `idx_farmer_profiles_user_id` on `farmer_profiles(user_id)`

---

## 3. PostgreSQL Migration Procedure

### Step 1: Initialize PostgreSQL / Supabase Schema
Execute the synchronized DDL script provided in `supabase_schema.sql`:
```bash
psql -h your-db.supabase.co -U postgres -d postgres -f supabase_schema.sql
```
This provisions all tables, foreign keys, triggers, Row Level Security policies, storage buckets, and performance indexes.

### Step 2: Data Export from SQLite
Run the following Python script to dump SQLite records into PostgreSQL-compatible JSON format or directly insert them into PostgreSQL:

```python
import sqlite3
import json
from pathlib import Path

sqlite_conn = sqlite3.connect("backend/agronex.db")
sqlite_conn.row_factory = sqlite3.Row
cur = sqlite_conn.cursor()

tables = ["users", "farmer_profiles", "crop_analyses", "chat_history"]
dump = {}

for table in tables:
    cur.execute(f"SELECT * FROM {table}")
    rows = [dict(r) for r in cur.fetchall()]
    dump[table] = rows
    print(f"Exported {len(rows)} records from {table}")

with open("sqlite_export.json", "w", encoding="utf-8") as f:
    json.dump(dump, f, indent=2, ensure_ascii=False)

print("Export complete: sqlite_export.json")
```

### Step 3: Configure Environment Variables
In your backend environment (`backend/.env` or deployment settings):
```env
# Enable Supabase / PostgreSQL persistence
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=your_service_or_anon_key
```

When `SUPABASE_URL` is set and reachable, `backend/config/database.py` automatically routes requests to PostgreSQL, while maintaining `local_db.py` as an offline resilience layer.

---

## 4. Operational Best Practices

1. **Image Storage**: Never store raw image byte streams in SQL databases. Always store references (`image_path`), with binaries stored either on object storage (Supabase Storage bucket `crop-images` / AWS S3) or local filesystem (`uploads/`).
2. **Transaction Safety**: All write operations in `local_db.py` use Python context managers (`with conn:`) guaranteeing automatic commits on success and rollbacks on failure.
3. **Safe Deletion**: Deleting crop analyses automatically unlinks any associated temporary files in `uploads/` to prevent disk bloat.
4. **Connection Pooling**: When deploying to production with high concurrency, use PgBouncer or Supabase transaction pooler on port 6543.
