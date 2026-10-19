# Kontrak integrasi implementasi

Status: kontrak kerja implementasi 19 Oktober 2026; hasil aktual dan batas bukti mengikuti laporan tes.

## Struktur

- Python package `src/arker`: API/core/database/config/auth dikerjakan bersama worker/adapters pada satu package, tetapi proses API dan worker terpisah.
- Web React + TypeScript + Vite di `apps/web`; build ke `apps/web/dist`, dilayani API untuk instalasi lokal.
- CLI `python -m arker` menyediakan init, serve, worker, doctor, preview, backup/restore, dan service operations.
- Data privat selalu berasal dari `--data-dir` atau default per OS. Tidak mengakses instalasi lain.
- Semua dependency terkunci; CI menguji backend dan build frontend pada Windows/macOS/Linux.

## REST untuk frontend

Prefix `/api`. JSON error memakai `{"detail": "pesan aman", "code": "machine_code"}`; semua endpoint data memerlukan sesi admin. Mutasi memerlukan header `X-CSRF-Token` dari session dan same-origin. Cookie session HttpOnly; HTTPS secure pada deployment non-loopback.

| Method/path | Respons atau input utama |
| --- | --- |
| GET /auth/session | authenticated, user, csrf_token, setup_required |
| POST /auth/login | email, password; respons session |
| POST /auth/logout | akhir sesi |
| GET /overview | health, summary, charts, active_assets, attention, generated_at |
| GET /health | connected, state, heartbeat_at, age_seconds, components, applied_version |
| GET /service | running, worker_running, worker_state, worker_pid; supervisor lokal |
| POST /service/{start,stop,restart} | accepted, id, action; tunggu status proses untuk konfirmasi |
| GET /assets?q=&state=&page=&limit= | items, total, page, limit |
| GET /assets/{id} | asset, deliveries, events, artifacts |
| POST /intake | urls array; accepted, duplicates, rejected |
| GET /batches | items, total |
| GET /accounts | items, total, snapshot_at |
| GET /deliveries?state=&platform= | items, total |
| GET /comments | items, total |
| GET /reports | items, metrics, quality |
| GET /personas | items |
| PUT /personas/{id} | name, style, account_id opsional; versi/binding immutable |
| GET /events?before=&after=&limit= | items, cursor; default terbaru dahulu |
| GET /configuration | config, desired_version, applied_version, credentials flags |
| POST /configuration/validate | config; valid, errors, impact |
| PUT /configuration | config, base_version; version, status |
| POST /credentials/{provider} | credential fields; configured/version saja |
| POST /connections/{provider}/test | hasil tes hanya-baca |
| GET /storage | profiles, capacity, verification |
| POST /storage/check | bank_directory, folder_url; validation findings |
| GET /backups | items |
| POST /commands | kind, payload, idempotency_key; cleanup_plan hanya baca, cleanup aksi terpisah |
| GET /commands/{id} | command dengan status/alasan |
| GET /media/{asset_id}/{artifact} | file tervalidasi, admin only |

Server memberi available_actions pada entitas. Frontend tidak mengarang kemampuan retry, publish atau cancel. Tabel kosong mempunyai state nyata, bukan data demo otomatis.

## Kontrak Python antara modul

Backend menyediakan `arker.db.Store(data_dir: Path)`, `.connect()` context manager transaksi SQLite dengan Row, `.event(kind, entity_id=None, payload=None)`, `.configuration()` (config, desired_version, applied_version), serta `.set_meta(key,value)`/`.get_meta(key,default=None)`.

`arker.config.default_config(data_dir)` dan `validate_config(config, data_dir)` menangani config; `arker.secrets.SecretStore(data_dir)` menyediakan set/get/status tanpa exposing nilai di API.

Worker menyediakan `arker.worker.Worker(store, ...)` dengan async `tick()` dan `run()`. Adapter ditempatkan di `arker.adapters`. Worker hanya menerapkan desired config melalui command, menulis heartbeat, memproses queue, dan tidak memanggil API web untuk mengakses DB.

Schema disepakati langsung antar implementer sebelum integrasi; backend adalah pemilik file db.py. Root memiliki CLI, service manager, backup/cleanup, packaging, CI dan dokumentasi. Setiap implementer menambahkan tes miliknya tanpa mengubah file yang dimiliki implementer lain.
