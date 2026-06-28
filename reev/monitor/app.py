#!/usr/bin/env python3
"""REEV Database Monitor — FastAPI backend."""

import asyncio
import json
import os
import re
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="REEV DB Monitor", version="1.0.0")

# ── Configuration (env-var overridable for Docker) ────────────────────────────
DATA_DIR   = Path(os.environ.get("DATA_DIR",   "/nas/data"))
LOG_FILE   = Path(os.environ.get("LOG_FILE",   "/nas/download-smart.log"))
DL_SCRIPT  = os.environ.get("DL_SCRIPT",  "/nas/download-smart.sh")

# ── Database groups to monitor ─────────────────────────────────────────────────
DB_GROUPS = [
    {
        "id": "annonars-grch38", "label": "Annonars GRCh38", "icon": "🧬",
        "acronym": "ANNOtation of NucleotidE vaRiantS",
        "path": DATA_DIR / "annonars/grch38",
        "description": "Bases de datos de anotación de variantes para GRCh38 (hg38). Incluye frecuencias poblacionales (gnomAD v4), predicciones funcionales (CADD, dbNSFP, AlphaMissense), variantes clínicas (ClinVar), conservación evolutiva y variantes estructurales. Ensamblaje principal para NGS modernos.",
        "pending_downloads": [
            DATA_DIR / "download/annonars/gnomad-genomes-chrX-grch38-4.1+0.39.0",
            DATA_DIR / "download/annonars/gnomad-genomes-chrY-grch38-4.1+0.39.0",
        ],
    },
    {
        "id": "annonars-grch37", "label": "Annonars GRCh37", "icon": "🧬",
        "acronym": "ANNOtation of NucleotidE vaRiantS",
        "path": DATA_DIR / "annonars/grch37",
        "description": "Bases de datos de anotación de variantes para GRCh37 (hg19). Versión heredada ampliamente usada en estudios publicados y pipelines clínicas. Mismas categorías que GRCh38 con datos adaptados al ensamblaje antiguo.",
        "pending_downloads": [
            DATA_DIR / "download/annonars/dbnsfp-grch37-4.5a+0.39.0",
            DATA_DIR / "download/annonars/dbscsnv-grch37-1.1+0.39.0",
            DATA_DIR / "download/annonars/alphamissense-grch37-1+0.39.0",
            DATA_DIR / "download/annonars/functional-grch37-105.20201022+0.39.0",
            DATA_DIR / "download/annonars/gnomad-sv-exomes-grch37-0.3.1+0.39.0",
            DATA_DIR / "download/annonars/gnomad-sv-genomes-grch37-2.1.1+0.39.0",
            DATA_DIR / "download/annonars/regions-grch37-20240711+0.39.0",
            DATA_DIR / "download/annonars/gnomad-exomes-chrX-grch37-2.1.1",
            DATA_DIR / "download/annonars/gnomad-genomes-chrX-grch37-2.1.1",
        ],
    },
    {
        "id": "annonars-genes", "label": "Annonars Genes", "icon": "🔗",
        "acronym": "ANNOtation of NucleotidE vaRiantS",
        "path": DATA_DIR / "annonars",
        "description": "Bases de datos génicas independientes del ensamblaje: anotaciones HGNC, scores de haploinsuficiencia, constraint gnomAD (pLI, LOEUF, Z-score missense) y resumen ClinVar por gen. Compartidas entre GRCh37 y GRCh38.",
        "entries_filter": ["genes", "clinvar-genes"],
    },
    {
        "id": "mehari-grch38", "label": "Mehari GRCh38", "icon": "🔬",
        "acronym": "Molecular Effect and HGVS Annotation Resource Infrastructure",
        "path": DATA_DIR / "mehari/grch38",
        "description": "Transcriptos RefSeq y Ensembl con coordenadas GRCh38 para el motor Mehari. Necesarios para calcular el efecto HGVS de cada variante (missense, frameshift, splicing, UTR, etc.).",
    },
    {
        "id": "mehari-grch37", "label": "Mehari GRCh37", "icon": "🔬",
        "acronym": "Molecular Effect and HGVS Annotation Resource Infrastructure",
        "path": DATA_DIR / "mehari/grch37",
        "description": "Transcriptos RefSeq y Ensembl con coordenadas GRCh37 para el motor Mehari. Equivalente al anterior pero para el ensamblaje hg19.",
    },
    {
        "id": "dotty", "label": "Dotty / SeqRepo", "icon": "📍",
        "acronym": "DNA/RNA cOordinate Translation and Transcript bYpass",
        "path": DATA_DIR / "dotty",
        "description": "Repositorio de secuencias SeqRepo utilizado por Dotty para conversión y validación de descripciones HGVS. Permite resolver transcriptos por ID RefSeq/Ensembl y verificar la corrección de variantes HGVS.",
    },
    {
        "id": "viguno", "label": "Viguno / HPO", "icon": "🏥",
        "acronym": "Variant Interpretation with Gene and UNified Ontology",
        "path": DATA_DIR / "viguno",
        "description": "Human Phenotype Ontology (HPO) y sus asociaciones gen-fenotipo. Utilizada por CADA-Prio para priorizar variantes candidatas según el fenotipo clínico del paciente.",
    },
    {
        "id": "cada-prio", "label": "CADA-Prio Model", "icon": "🤖",
        "acronym": "Case Annotation and Deep learning-based Automated Prioritization",
        "path": DATA_DIR / "cada-prio",
        "description": "Modelo de machine learning para priorización de variantes candidatas en enfermedades raras. Integra el fenotipo HPO del paciente con datos de variantes para generar una puntuación de relevancia clínica.",
    },
]

# ── State ──────────────────────────────────────────────────────────────────────

# ── Helpers ────────────────────────────────────────────────────────────────────
def _human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


# Stable denominator cache: bytes_total for each rocksdb path is only ever increased,
# never decreased. This prevents the progress bar from jumping backwards when s5cmd
# starts a new parallel file chunk and transiently increases the apparent total.
_bytes_total_cache: dict[str, int] = {}

# S3 authoritative size cache: maps dir name → (bytes_total, query_time)
# TTL of 24 h — we only need to query once per database per session.
_s3_size_cache: dict[str, tuple[int, float]] = {}
_S3_ENDPOINT = "https://ceph-s3-public.cubi.bihealth.org"
_S3_BUCKET   = "s3://varfish-public"
_S5CMD       = "/home/arkantu/.local/bin/s5cmd"

# Map from dir-name prefix → S3 sub-prefix (mirrors download-smart.sh logic)
# Keys are substrings that appear in the directory name.
_S3_PREFIX_MAP = [
    # reduced-exomes (smaller files)
    ("gnomad-exomes-grch38",   "reduced-exomes/annonars"),
    ("gnomad-genomes-grch38",  "reduced-exomes/annonars"),
    ("gnomad-exomes-grch37",   "reduced-exomes/annonars"),
    ("gnomad-genomes-grch37",  "reduced-exomes/annonars"),
    # mehari freqs
    ("freqs-grch38",           "full/mehari"),
    ("freqs-grch37",           "full/mehari"),
    # full annonars (catch-all)
    ("annonars",               "full/annonars"),
    ("",                       "full/annonars"),   # fallback
]

def _s3_prefix_for(dir_name: str) -> str:
    """Determine the correct S3 sub-prefix for a given download directory name."""
    for key, prefix in _S3_PREFIX_MAP:
        if key in dir_name:
            return prefix
    return "full/annonars"

# Track in-flight S3 queries so we only fire once per dir_name
_s3_querying: set[str] = set()

def _query_s3_total_bytes(dir_name: str) -> int:
    """Return cached S3 total bytes for dir_name, or 0 while the background
    query is running (first call triggers a background thread)."""
    cached = _s3_size_cache.get(dir_name)
    if cached:
        total_bytes, ts = cached
        if time.time() - ts < 86400:
            return total_bytes

    # Don't block the API handler — fire a background thread on first miss.
    if dir_name not in _s3_querying:
        _s3_querying.add(dir_name)
        threading.Thread(target=_fetch_s3_size_bg, args=(dir_name,), daemon=True).start()
    return 0

def _fetch_s3_size_bg(dir_name: str) -> None:
    """Background thread: run 's5cmd du' and populate _s3_size_cache."""
    try:
        s3_sub = _s3_prefix_for(dir_name)
        s3_url = f"{_S3_BUCKET}/{s3_sub}/{dir_name}/*"
        env = {**os.environ, "GODEBUG": "http2client=0"}
        r = subprocess.run(
            ["nsenter", f"--mount={HOST_PROC_MNT_NS}", "--net=/host-proc/1/ns/net", "--",
             _S5CMD, "--endpoint-url", _S3_ENDPOINT, "--no-sign-request",
             "du", s3_url],
            capture_output=True, text=True, timeout=30, env=env,
        )
        m = re.match(r"(\d+) bytes", r.stdout.strip())
        if m:
            _s3_size_cache[dir_name] = (int(m.group(1)), time.time())
    except Exception:
        pass
    finally:
        _s3_querying.discard(dir_name)

def _rocksdb_progress(path: Path) -> dict:
    """Return download progress for a directory expected to contain RocksDB files.
    Handles two layouts:
      - path/rocksdb/*.sst  (nested layout, rocksdb/ has content)
      - path/*.sst          (flat layout, sst files at root)
    """
    rocksdb_dir = path / "rocksdb"
    if rocksdb_dir.exists():
        sst_files = list(rocksdb_dir.glob("*.sst*"))
        if not sst_files:
            rocksdb_dir = path
            sst_files = list(rocksdb_dir.glob("*.sst*"))
    else:
        rocksdb_dir = path
        sst_files = list(rocksdb_dir.glob("*.sst*"))

    has_current = (rocksdb_dir / "CURRENT").exists()

    if not sst_files and not has_current:
        return {
            "sst_done": 0, "sst_total": 0, "has_current": False, "pct": 0,
            "bytes_done": 0, "bytes_total": 0
        }

    bytes_total = 0
    bytes_done = 0
    sst_done_count = 0
    sst_total_count = 0

    for f in sst_files:
        name = f.name
        if name.endswith(".aria2"):
            continue

        sst_total_count += 1
        stat = f.stat()
        sz = stat.st_size
        alloc = stat.st_blocks * 512

        bytes_total += sz
        bytes_done += min(alloc, sz)

        # Temp files from s5cmd (ends with numbers) or parts
        is_temp = any(name.endswith(ext) for ext in [".tmp", ".part"]) or (name[-1].isdigit() and not name.endswith(".sst"))
        if not is_temp and sz > 0:
            sst_done_count += 1

    if has_current:
        sst_done_count = sst_total_count
        bytes_done = bytes_total

    # Try to get the authoritative S3 total for this database directory.
    # This gives us the true denominator even before all files have been
    # allocated locally by s5cmd (which pre-allocates sparse files).
    s3_total = _query_s3_total_bytes(path.name)
    if s3_total > 0:
        # Use S3 total as the ground truth; fall back to local apparent size.
        stable_total = s3_total
    else:
        # Pin to max seen locally so the bar never goes backwards.
        cache_key = str(path)
        cached_max = _bytes_total_cache.get(cache_key, 0)
        if bytes_total > cached_max:
            _bytes_total_cache[cache_key] = bytes_total
        stable_total = max(bytes_total, cached_max)

    if has_current:
        # Once download is complete, clear the local cache.
        _bytes_total_cache.pop(str(path), None)

    pct = int(bytes_done / stable_total * 100) if stable_total else (100 if has_current else 0)
    if not has_current and pct >= 100:
        pct = 99

    return {
        "sst_done": sst_done_count,
        "sst_total": sst_total_count,
        "has_current": has_current,
        "pct": pct,
        "bytes_done": bytes_done,
        "bytes_total": stable_total
    }


def _entry_info(path: Path, is_download: bool = False) -> dict:
    """Collect metadata for a single entry (file / dir / symlink)."""
    info: dict = {
        "name":       path.name,
        "is_symlink": path.is_symlink(),
        "target":     None,
        "version":    None,
        "mtime":      None,
        "mtime_iso":  None,
        "has_done":   False,
        "status":     "missing",
        "size_bytes": None,
        "size_human": "…",
        "dl_progress": None,
    }

    if path.is_symlink():
        try:
            target = os.readlink(path)
            info["target"] = target
            # Resolve for actual path
            actual = path.resolve()
            info["version"] = actual.name
        except OSError:
            return info
    else:
        actual = path

    if not actual.exists():
        return info

    try:
        st = actual.stat()
        info["mtime"] = st.st_mtime
        info["mtime_iso"] = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        pass

    if actual.is_file():
        # Files are "done" when they exist with non-zero size
        info["has_done"] = st.st_size > 0 if st else False
        info["status"] = "done" if info["has_done"] else "incomplete"
        return info

    # For download-group entries: detect RocksDB completion
    if is_download:
        prog = _rocksdb_progress(actual)
        info["dl_progress"] = prog
        if prog["has_current"] and prog["sst_done"] == prog["sst_total"] and prog["sst_total"] > 0:
            info["has_done"] = True
            info["status"] = "done"
        elif prog["sst_done"] > 0:
            info["status"] = "partial"
        else:
            info["status"] = "incomplete"
        return info

    # Directory: prefer .done mtime as "last updated"
    done = actual / ".done"
    if done.exists():
        info["has_done"] = True
        info["status"] = "done"
        try:
            dst = done.stat()
            info["mtime"] = dst.st_mtime
            info["mtime_iso"] = datetime.fromtimestamp(dst.st_mtime).strftime("%Y-%m-%d %H:%M")
        except OSError:
            pass
    else:
        # Also check for RocksDB-style completion in any sub-path
        # Supports both nested layout (rocksdb/CURRENT) and flat layout (CURRENT at root)
        rocksdb_current = actual / "rocksdb" / "CURRENT"
        flat_current = actual / "CURRENT"
        if rocksdb_current.exists() or flat_current.exists():
            info["has_done"] = True
            info["status"] = "done"
        else:
            info["status"] = "incomplete"

    return info


def _group_status(statuses: list[str]) -> str:
    if not statuses:
        return "empty"
    if all(s == "done" for s in statuses):
        return "done"
    if any(s == "done" for s in statuses):
        return "partial"
    return "incomplete"


# ── API Endpoints ──────────────────────────────────────────────────────────────

@app.get("/api/disk")
def get_disk():
    """Return disk usage, projected download size, and overflow warning."""
    try:
        sv = os.statvfs(DATA_DIR)
        disk_total  = sv.f_blocks * sv.f_frsize
        disk_free   = sv.f_bavail * sv.f_frsize
        disk_used   = disk_total - disk_free
    except Exception:
        disk_total = disk_free = disk_used = 0

    # Sum of S3 total sizes for every DB that is still in partial/incomplete state
    pending_s3_bytes  = 0   # total S3 size of unfinished databases
    pending_remaining = 0   # bytes still to download (s3_total - bytes_done)
    pending_entries   = []  # list of {name, s3_total, bytes_done, pct}

    dl_dir = DATA_DIR / "download"
    if dl_dir.exists():
        for p in dl_dir.rglob("rocksdb"):
            db_dir = p.parent
            prog   = _rocksdb_progress(db_dir)
            if prog["has_current"] and prog["sst_done"] == prog["sst_total"] and prog["sst_total"] > 0:
                continue   # fully complete
            s3_total = prog["bytes_total"]
            done     = prog["bytes_done"]
            if s3_total > 0:
                remaining = max(0, s3_total - done)
                pending_s3_bytes  += s3_total
                pending_remaining += remaining
                pending_entries.append({
                    "name":      db_dir.name,
                    "s3_total":  s3_total,
                    "bytes_done": done,
                    "pct":       prog["pct"],
                })

    will_overflow   = pending_remaining > disk_free
    overflow_margin = pending_remaining - disk_free  # positive = overflow

    return {
        "disk_total":        disk_total,
        "disk_used":         disk_used,
        "disk_free":         disk_free,
        "disk_used_pct":     round(disk_used / disk_total * 100, 1) if disk_total else 0,
        "pending_s3_bytes":  pending_s3_bytes,
        "pending_remaining": pending_remaining,
        "will_overflow":     will_overflow,
        "overflow_margin":   overflow_margin,
        "pending_entries":   pending_entries,
        "disk_total_human":  _human_size(disk_total),
        "disk_free_human":   _human_size(disk_free),
        "pending_remaining_human": _human_size(pending_remaining) if pending_remaining > 0 else "0 B",
        "overflow_margin_human":   _human_size(abs(overflow_margin)),
    }


@app.get("/api/status")
def get_status():
    """Return metadata for all database groups (fast — no du)."""
    result = []
    for grp in DB_GROUPS:
        path: Path = grp["path"]
        filt: list = grp.get("entries_filter", [])

        out = {
            "id":           grp["id"],
            "label":        grp["label"],
            "icon":         grp["icon"],
            "acronym":      grp.get("acronym", ""),
            "description":  grp.get("description", ""),
            "path":         str(path),
            "exists":       path.exists(),
            "entries":      [],
            "last_update":  None,
            "last_update_iso": None,
            "status":       "missing",
            "error":        None,
        }

        if not path.exists():
            result.append(out)
            continue

        try:
            items = sorted(path.iterdir(), key=lambda p: p.name)
            for item in items:
                if item.name.startswith("."):
                    continue
                if filt and item.name not in filt:
                    continue
                info = _entry_info(item)
                out["entries"].append(info)
                if info["mtime"] and (
                    out["last_update"] is None or info["mtime"] > out["last_update"]
                ):
                    out["last_update"] = info["mtime"]
                    out["last_update_iso"] = info["mtime_iso"]
        except Exception as exc:
            out["error"] = str(exc)

        # ── Inject pending-download entries that aren't symlinked yet ──────────
        dynamic_pending = []
        try:
            if "annonars" in grp["id"]:
                assembly = "grch38" if "grch38" in grp["id"] else "grch37"
                dl_dir = DATA_DIR / "download" / "annonars"
                if dl_dir.exists():
                    for p in dl_dir.iterdir():
                        if p.is_dir() and assembly in p.name:
                            dynamic_pending.append(p)
            elif "mehari" in grp["id"]:
                assembly = "grch38" if "grch38" in grp["id"] else "grch37"
                dl_dir = DATA_DIR / "download" / "mehari"
                if dl_dir.exists():
                    for p in dl_dir.iterdir():
                        if p.is_dir() and assembly in p.name:
                            dynamic_pending.append(p)
        except Exception:
            pass

        all_pending = list(grp.get("pending_downloads", [])) + dynamic_pending
        existing_names = {e["name"] for e in out["entries"]}
        import re as _re
        for dl_path in all_pending:
            dl_path = Path(dl_path)
            # Derive short name: "dbnsfp-grch38-4.5a+0.39.0" → "dbnsfp"
            short_name = _re.sub(r"-grch\d+.*", "", dl_path.name)
            if not dl_path.exists():
                continue
            prog = _rocksdb_progress(dl_path)
            if prog["has_current"] and prog["sst_done"] == prog["sst_total"] and prog["sst_total"] > 0:
                dl_status = "done"
            elif prog["sst_done"] > 0:
                dl_status = "partial"
            else:
                dl_status = "incomplete"

            if short_name in existing_names:
                for entry in out["entries"]:
                    if entry["name"] == short_name:
                        if dl_status == "done":
                            entry["dl_progress"] = None
                            entry["status"] = "done"
                        else:
                            entry["dl_progress"] = prog
                            entry["status"] = dl_status
                continue

            out["entries"].append({
                "name":        short_name,
                "is_symlink":  False,
                "target":      None,
                "version":     dl_path.name,
                "mtime":       None,
                "mtime_iso":   None,
                "has_done":    dl_status == "done",
                "status":      dl_status,
                "size_bytes":  None,
                "size_human":  "…",
                "dl_progress": None if dl_status == "done" else prog,
            })

        out["status"] = _group_status([e["status"] for e in out["entries"]])
        result.append(out)

    return result


@app.get("/api/disk")
def get_disk():
    """Return disk usage of the data mount."""
    try:
        env = {**os.environ, "LC_ALL": "C", "LANG": "C"}
        r = subprocess.run(
            ["df", "-h", str(DATA_DIR)],
            capture_output=True, text=True, timeout=10, env=env,
        )
        lines = r.stdout.strip().splitlines()
        if len(lines) >= 2:
            parts = lines[1].split()
            return {
                "filesystem": parts[0],
                "size":       parts[1],
                "used":       parts[2],
                "avail":      parts[3],
                "use_pct":    parts[4],
                "mount":      parts[5],
            }
    except Exception as exc:
        return {"error": str(exc)}
    return {}


@app.get("/api/size/{group_id}")
async def get_group_size(group_id: str):
    """Run du -sh on a group's resolved paths (can be slow on NAS)."""
    grp = next((g for g in DB_GROUPS if g["id"] == group_id), None)
    if not grp:
        raise HTTPException(404, "Unknown group")

    path: Path = grp["path"]
    filt: list = grp.get("entries_filter", [])
    sizes: dict[str, str] = {}
    total_bytes = 0

    if path.exists():
        try:
            items = [p for p in sorted(path.iterdir()) if not p.name.startswith(".")]
            if filt:
                items = [p for p in items if p.name in filt]
            for item in items:
                actual = item.resolve() if item.is_symlink() else item
                if actual.exists():
                    proc = await asyncio.create_subprocess_exec(
                        "du", "-sb", str(actual),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    stdout, _ = await proc.communicate()
                    if stdout:
                        nb = int(stdout.split()[0])
                        total_bytes += nb
                        sizes[item.name] = _human_size(nb)
        except Exception as exc:
            return {"group_id": group_id, "error": str(exc), "sizes": sizes}

    return {
        "group_id":    group_id,
        "sizes":       sizes,
        "total_human": _human_size(total_bytes),
        "total_bytes": total_bytes,
    }


HOST_PROC_MNT_NS = "/host-proc/1/ns/mnt"
HOST_SCRIPT = os.environ.get("HOST_SCRIPT", "/media/arkantu/Storage1TB/reev/download-smart.sh")


def _nsenter_cmd(cmd: list) -> list:
    """Wrap a command with nsenter to run in the host mount and network namespaces."""
    return ["nsenter", f"--mount={HOST_PROC_MNT_NS}", "--net=/host-proc/1/ns/net", "--"] + cmd


def _nas_script_running() -> Optional[int]:
    """Return host PID of download-smart.sh if running, else None."""
    try:
        # Leer archivo de PID en el namespace del host
        r_pid = subprocess.run(
            _nsenter_cmd(["cat", "/tmp/reev-download-smart.pid"]),
            capture_output=True, text=True, timeout=5,
        )
        if r_pid.returncode != 0:
            return None
        pid_str = r_pid.stdout.strip()
        if not pid_str.isdigit():
            return None
        pid = int(pid_str)
        # Verificar si el proceso sigue vivo en el host
        r_kill = subprocess.run(
            _nsenter_cmd(["kill", "-0", str(pid)]),
            capture_output=True, timeout=5,
        )
        if r_kill.returncode == 0:
            return pid
        return None
    except Exception:
        return None


@app.get("/api/update/running")
def update_running():
    """Check whether the update script is currently running on the NAS."""
    pid = _nas_script_running()
    return {"running": pid is not None, "pid": pid}


# Global state for download speed calculation
_last_check_time = 0.0
_last_check_size = 0
_current_speed = "0.0 MB/s"
_progress_history = []
_max_history_len = 200

def _format_speed(bps: float) -> str:
    if bps >= 1024 * 1024 * 1024:
        return f"{bps / (1024 * 1024 * 1024):.2f} GB/s"
    elif bps >= 1024 * 1024:
        return f"{bps / (1024 * 1024):.2f} MB/s"
    elif bps >= 1024:
        return f"{bps / 1024:.2f} KB/s"
    else:
        return f"{bps:.2f} B/s"


@app.get("/api/update/progress")
def update_progress():
    """Return done/total count from the manifest and current aria2/rsync % from the log."""
    global _last_check_time, _last_check_size, _current_speed, _progress_history
    done, total, rsync_pct, rsync_eta, current_file = 0, 0, None, None, None

    # Calculate real-time speed from directory size growth
    try:
        current_time = time.time()
        du_res = subprocess.run(
            ["du", "-sb", str(DATA_DIR / "download")],
            capture_output=True, text=True, timeout=3
        )
        if du_res.returncode == 0:
            current_size = int(du_res.stdout.split()[0])
            if _last_check_time > 0:
                dt = current_time - _last_check_time
                if dt >= 1.0:
                    db = current_size - _last_check_size
                    speed_bps = max(0.0, float(db) / dt)
                    _current_speed = _format_speed(speed_bps)
                    _last_check_time = current_time
                    _last_check_size = current_size
            else:
                _last_check_time = current_time
                _last_check_size = current_size
    except Exception:
        pass

    # Count done entries from local manifest
    try:
        manifest_path = DATA_DIR / "download" / ".manifest-expected-dones"
        if manifest_path.exists():
            lines_m = manifest_path.read_text().splitlines()
            total = len(lines_m)
            for line in lines_m:
                line = line.strip()
                if not line:
                    continue
                # Map host path (e.g. /media/arkantu/.../download/...) to container path (/nas/data/download/...)
                idx = line.find("download/")
                if idx != -1:
                    container_path = DATA_DIR / line[idx:]
                    if container_path.exists():
                        done += 1
                else:
                    if Path(line).exists():
                        done += 1
    except Exception:
        pass

    # Parse progress from local log tail
    rsync_speed = None
    try:
        r = subprocess.run(
            ["tail", "-200", str(LOG_FILE)],
            capture_output=True, text=True, timeout=5,
        )
        lines = r.stdout.splitlines()
        pct_re = re.compile(r'[\d,]+\s+(\d+)%\s+[\d.]+\w+/s\s+([\d:]+)')
        for line in reversed(lines):
            m = pct_re.search(line)
            if m:
                rsync_pct = int(m.group(1))
                rsync_speed = m.group(2)
                rsync_eta = m.group(3)
                break
        skip_re = re.compile(r'NOTE:|rsync://|sending|receiving|bytes/sec|total size|^\s*[\d,]+\s+\d+%|^building|^delta|^created|^sent|^recv')
        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                continue
            ts_match = re.match(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] (.+)$', stripped)
            if ts_match:
                content = ts_match.group(1).strip()
                if content and not skip_re.search(content):
                    current_file = content
                    break
    except Exception:
        pass

    pct = int(done / total * 100) if total > 0 else 0
    final_speed = rsync_speed if rsync_speed else _current_speed

    # Append to history cache (maximum once per 5 seconds to avoid duplicates)
    try:
        current_time = time.time()
        time_str = datetime.fromtimestamp(current_time).strftime("%H:%M:%S")
        should_append = True
        if _progress_history:
            if _progress_history[-1]["time"] == time_str:
                should_append = False
        if should_append:
            _progress_history.append({
                "time": time_str,
                "speed": final_speed,
                "pct": pct
            })
            if len(_progress_history) > _max_history_len:
                _progress_history.pop(0)
    except Exception:
        pass

    return {
        "done": done,
        "total": total,
        "pct": pct,
        "rsync_pct": rsync_pct,
        "rsync_speed": final_speed,
        "rsync_eta": rsync_eta,
        "current_file": current_file,
    }


# Estado global para la verificación diaria de actualizaciones
_update_check_result = {
    "updates_available": False,
    "pending_count": 0,
    "last_checked": None,
    "pending_list": []
}

async def periodic_update_checker():
    """Verificación periódica diaria de actualizaciones utilizando el script status."""
    global _update_check_result
    # Espera inicial de 10 segundos tras encender para que el contenedor esté listo
    await asyncio.sleep(10)
    while True:
        try:
            if _nas_script_running() is None:
                r = subprocess.run(
                    _nsenter_cmd(["bash", HOST_SCRIPT, "--status"]),
                    capture_output=True, text=True, timeout=15
                )
                if r.returncode == 0:
                    lines = r.stdout.splitlines()
                    pending = []
                    for line in lines:
                        if ("incompleto" in line or "no descargado" in line or "⏳" in line or "✗" in line) and "DISCO" not in line:
                            clean_line = line.replace("⏳", "").replace("✗", "").strip()
                            pending.append(clean_line)
                    
                    _update_check_result = {
                        "updates_available": len(pending) > 0,
                        "pending_count": len(pending),
                        "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "pending_list": pending
                    }
        except Exception:
            pass
        # Espera de 24 horas (86400 segundos) para la próxima comprobación
        await asyncio.sleep(86400)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_update_checker())


@app.get("/api/update/check")
def get_update_check():
    """Return the result of the last daily update check."""
    return _update_check_result


@app.post("/api/update/check/run")
def run_update_check():
    """Manually trigger the update check."""
    global _update_check_result
    if _nas_script_running() is not None:
        raise HTTPException(409, "Cannot check updates while update is running")
    
    try:
        r = subprocess.run(
            _nsenter_cmd(["bash", HOST_SCRIPT, "--status"]),
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            lines = r.stdout.splitlines()
            pending = []
            for line in lines:
                if ("incompleto" in line or "no descargado" in line or "⏳" in line or "✗" in line) and "DISCO" not in line:
                    clean_line = line.replace("⏳", "").replace("✗", "").strip()
                    pending.append(clean_line)
            
            _update_check_result = {
                "updates_available": len(pending) > 0,
                "pending_count": len(pending),
                "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "pending_list": pending
            }
            return _update_check_result
        else:
            raise HTTPException(500, f"Check failed with exit code {r.returncode}")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/update/history")
def update_history():
    """Return progress and speed history points for charting."""
    return _progress_history


@app.post("/api/update/start")
def start_update():
    """Launch download-smart.sh in the host's mount namespace via nsenter."""
    if _nas_script_running() is not None:
        raise HTTPException(409, "Update already running")

    # Verify the script is accessible in the host namespace
    check = subprocess.run(
        _nsenter_cmd(["test", "-f", HOST_SCRIPT]),
        capture_output=True, timeout=5,
    )
    if check.returncode != 0:
        raise HTTPException(404, f"Script not found in host namespace: {HOST_SCRIPT}")

    try:
        log_file = open(str(LOG_FILE), "a")
        # nsenter enters the host's mount namespace so host tools
        # (wget, rsync, s5cmd, ...) are available — they are absent inside the container.
        proc = subprocess.Popen(
            _nsenter_cmd(["bash", HOST_SCRIPT]),
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
        return {"started": True, "pid": proc.pid, "script": HOST_SCRIPT}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/api/log")
def get_log(lines: int = 200):
    """Return the last N lines of the local download log."""
    try:
        r = subprocess.run(
            ["tail", f"-{lines}", str(LOG_FILE)],
            capture_output=True, text=True, timeout=15,
        )
        return {"content": r.stdout, "file": str(LOG_FILE)}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/api/log/stream")
async def stream_log():
    """SSE stream of local download log via tail -f."""
    async def _gen():
        proc = await asyncio.create_subprocess_exec(
            "tail", "-n", "80", "-f", str(LOG_FILE),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            async for raw in proc.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                yield f"data: {json.dumps(line)}\n\n"
        except asyncio.CancelledError:
            proc.kill()
            await proc.wait()

    return StreamingResponse(_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Static frontend ────────────────────────────────────────────────────────────
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
