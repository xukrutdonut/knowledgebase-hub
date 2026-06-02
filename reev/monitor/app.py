#!/usr/bin/env python3
"""REEV Database Monitor — FastAPI backend."""

import asyncio
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="REEV DB Monitor", version="1.0.0")

# ── Configuration (env-var overridable for Docker) ────────────────────────────
DATA_DIR   = Path(os.environ.get("DATA_DIR",   "/mnt/pi-nas/raid-hdd/swarm-storage/reev-data/reev-static/data"))
LOG_FILE   = Path(os.environ.get("LOG_FILE",   "/mnt/pi-nas/raid-hdd/swarm-storage/reev-data/download-smart.log"))
NAS_HOST   = os.environ.get("NAS_HOST",   "192.168.0.193")
NAS_USER   = os.environ.get("NAS_USER",   "arkantu")
NAS_SCRIPT = os.environ.get("NAS_SCRIPT", "/mnt/swarm-storage/reev-data/download-smart.sh")
NAS_LOG    = os.environ.get("NAS_LOG",    "/mnt/swarm-storage/reev-data/download-smart.log")
SSH_KEY    = os.environ.get("SSH_KEY",    "/root/.ssh/id_ed25519")

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


def _rocksdb_progress(path: Path) -> dict:
    """Return download progress for a directory expected to contain RocksDB files.
    Handles two layouts:
      - path/rocksdb/*.sst  (nested layout, rocksdb/ has content)
      - path/*.sst          (flat layout, sst files at root)
    """
    rocksdb_dir = path / "rocksdb"
    if rocksdb_dir.exists():
        sst_files = list(rocksdb_dir.glob("*.sst"))
        if sst_files:
            # Nested layout with content
            pass
        else:
            # rocksdb/ dir exists but is empty → fall back to root (flat layout)
            rocksdb_dir = path
            sst_files = list(rocksdb_dir.glob("*.sst"))
    else:
        rocksdb_dir = path
        sst_files = list(rocksdb_dir.glob("*.sst"))

    if not sst_files and not (rocksdb_dir / "CURRENT").exists():
        return {"sst_done": 0, "sst_total": 0, "has_current": False, "pct": 0}

    has_current = (rocksdb_dir / "CURRENT").exists()

    done = sum(
        1 for f in sst_files
        if not (rocksdb_dir / (f.name + ".aria2")).exists() and f.stat().st_size > 0
    )
    total = len(sst_files)

    # If CURRENT exists, the rocksdb was cleanly closed → all files are complete
    if has_current:
        done = total

    pct = int(done / total * 100) if total else (100 if has_current else 0)
    return {"sst_done": done, "sst_total": total, "has_current": has_current, "pct": pct}


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
        existing_names = {e["name"] for e in out["entries"]}
        import re as _re
        for dl_path in grp.get("pending_downloads", []):
            dl_path = Path(dl_path)
            # Derive short name: "dbnsfp-grch37-4.5a+0.39.0" → "dbnsfp"
            short_name = _re.sub(r"-grch\d+.*", "", dl_path.name)
            if short_name in existing_names or not dl_path.exists():
                continue
            prog = _rocksdb_progress(dl_path)
            if prog["has_current"] and prog["sst_done"] == prog["sst_total"] and prog["sst_total"] > 0:
                dl_status = "done"
            elif prog["sst_done"] > 0:
                dl_status = "partial"
            else:
                dl_status = "incomplete"
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
                "dl_progress": prog,
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


def _nas_script_running() -> Optional[int]:
    """Return remote PID of download-smart.sh if running on NAS, else None."""
    try:
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=5", "-i", SSH_KEY, f"{NAS_USER}@{NAS_HOST}",
             f"pgrep -f {NAS_SCRIPT} | head -1"],
            capture_output=True, text=True, timeout=8,
        )
        pid_str = r.stdout.strip()
        return int(pid_str) if pid_str.isdigit() else None
    except Exception:
        return None


@app.get("/api/update/running")
def update_running():
    """Check whether the update script is currently running on the NAS."""
    pid = _nas_script_running()
    return {"running": pid is not None, "pid": pid}


@app.get("/api/update/progress")
def update_progress():
    """Return done/total count from the manifest and current rsync % from the log."""
    # Count done entries on the NAS via SSH (manifest paths use NAS paths)
    done, total, rsync_pct, rsync_eta, current_file = 0, 0, None, None, None
    try:
        manifest_path = NAS_LOG.replace("download-smart.log", "reev-static/data/download/.manifest-expected-dones")
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=5", "-i", SSH_KEY, f"{NAS_USER}@{NAS_HOST}",
             f"total=$(wc -l < {manifest_path} 2>/dev/null || echo 0); "
             f"done=$(while IFS= read -r f; do [ -f \"$f\" ] && echo ok; done < {manifest_path} 2>/dev/null | wc -l); "
             f"echo \"$done $total\""],
            capture_output=True, text=True, timeout=12,
        )
        parts = r.stdout.strip().split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            done, total = int(parts[0]), int(parts[1])
    except Exception:
        pass

    # Parse rsync progress and current file from log tail
    try:
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=5", "-i", SSH_KEY, f"{NAS_USER}@{NAS_HOST}",
             f"tail -200 {NAS_LOG}"],
            capture_output=True, text=True, timeout=10,
        )
        lines = r.stdout.splitlines()
        # Find last rsync progress line: "    12,345,678  42%  1.23MB/s    0:01:23"
        pct_re = re.compile(r'[\d,]+\s+(\d+)%\s+[\d.]+\w+/s\s+([\d:]+)')
        for line in reversed(lines):
            m = pct_re.search(line)
            if m:
                rsync_pct = int(m.group(1))
                rsync_eta = m.group(2)
                break
        # Find last meaningful status line from the script (bracketed timestamp lines)
        skip_re = re.compile(r'NOTE:|rsync://|sending|receiving|bytes/sec|total size|^\s*[\d,]+\s+\d+%|^building|^delta|^created|^sent|^recv')
        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Only consider lines from our script (have [YYYY-MM-DD HH:MM:SS] prefix)
            ts_match = re.match(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] (.+)$', stripped)
            if ts_match:
                content = ts_match.group(1).strip()
                if content and not skip_re.search(content):
                    current_file = content
                    break
    except Exception:
        pass

    pct = int(done / total * 100) if total > 0 else 0
    return {
        "done": done,
        "total": total,
        "pct": pct,
        "rsync_pct": rsync_pct,
        "rsync_eta": rsync_eta,
        "current_file": current_file,
    }


@app.post("/api/update/start")
def start_update():
    """Launch download-smart.sh on the NAS via SSH (background nohup)."""
    if _nas_script_running() is not None:
        raise HTTPException(409, "Update already running")

    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-i", SSH_KEY,
        f"{NAS_USER}@{NAS_HOST}",
        f"nohup {NAS_SCRIPT} >> {NAS_LOG} 2>&1 &",
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.wait(timeout=10)  # SSH exits quickly after launching nohup background job
        return {"started": True, "cmd": " ".join(cmd)}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/api/log")
def get_log(lines: int = 200):
    """Return the last N lines of the download log (via SSH to NAS for freshness)."""
    try:
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
             "-i", SSH_KEY, f"{NAS_USER}@{NAS_HOST}", f"tail -{lines} {NAS_LOG}"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and r.stdout:
            return {"content": r.stdout, "file": NAS_LOG}
    except Exception:
        pass
    # Fallback: local sshfs mount
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
    """SSE stream via SSH tail -f (bypasses sshfs cache for real-time updates)."""
    async def _gen():
        cmd = [
            "ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
            "-o", "ServerAliveInterval=10",
            "-i", SSH_KEY, f"{NAS_USER}@{NAS_HOST}",
            f"tail -n 80 -f {NAS_LOG}",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
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
