"""
Celery app + tareas de tracking de ClinVar.

Flujo mensual:
  1. run_monthly_clinvar_sync  → descarga VCF nuevo, compara con el anterior
  2. _compute_clinvar_diff     → diff nativo (parse VCF.gz + comparar CLNSIG)
  3. process_clinvar_diff      → filtra variantes del lab, genera alertas
  4. send_pending_alerts       → envía emails/webhooks
"""

import re
import gzip
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from tracker.config import get_settings
from tracker.models import (
    Base, TrackedVariant, ClassificationHistory,
    VariantAlert, ClinVarSyncLog,
    ACMGClass, BreakingChange
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Celery app
# ---------------------------------------------------------------------------

celery_app = Celery(
    "variant_tracker",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Madrid",
    enable_utc=True,
    task_routes={
        "tracker.tasks.run_monthly_clinvar_sync": {"queue": "clinvar"},
        "tracker.tasks.send_pending_alerts": {"queue": "alerts"},
    },
    beat_schedule={
        "monthly-clinvar-sync": {
            "task": "tracker.tasks.run_monthly_clinvar_sync",
            "schedule": crontab(hour=3, minute=0, day_of_month=1),
        },
        "daily-pending-alerts": {
            "task": "tracker.tasks.send_pending_alerts",
            "schedule": crontab(hour=8, minute=0),
        },
    },
)


def get_db_engine():
    return create_engine(settings.database_url_sync)


# ---------------------------------------------------------------------------
# ClinVar VCF parser nativo
# ---------------------------------------------------------------------------

def _parse_clinvar_vcf(vcf_gz_path: Path) -> dict[str, str]:
    """
    Parsea un VCF.gz de ClinVar y devuelve dict:
      { "GRCh38_CHROM_POS_REF_ALT": "CLNSIG_value" }
    """
    variants = {}
    opener = gzip.open if str(vcf_gz_path).endswith(".gz") else open

    with opener(vcf_gz_path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split("\t", 8)
            if len(parts) < 8:
                continue
            chrom, pos, _, ref, alt = parts[0], parts[1], parts[2], parts[3], parts[4]
            info = parts[7]

            # Extraer CLNSIG
            m = re.search(r"CLNSIG=([^;]+)", info)
            if not m:
                continue
            clnsig = m.group(1).replace("|", "/")

            # Normalizar cromosoma
            chrom = chrom.replace("chr", "").upper()
            key = f"GRCh38_{chrom}_{pos}_{ref}_{alt}"
            variants[key] = clnsig

    return variants


def _classify_breaking_change(old_sig: str, new_sig: str) -> BreakingChange:
    """
    Determina la severidad del cambio según criterios VariantAlert-like.
    """
    pathogenic = {"Pathogenic", "Likely_pathogenic", "Pathogenic/Likely_pathogenic"}
    benign     = {"Benign", "Likely_benign", "Benign/Likely_benign"}
    vus        = {"Uncertain_significance"}

    def bucket(s):
        if s in pathogenic: return "P"
        if s in benign:     return "B"
        if s in vus:        return "VUS"
        return "O"

    ob, nb = bucket(old_sig), bucket(new_sig)
    if ob == nb:
        return BreakingChange.warning   # mismo bucket, cambio de texto menor
    if {ob, nb} & {"P"} and {ob, nb} & {"B"}:
        return BreakingChange.major     # P↔B: impacto diagnóstico máximo
    if "VUS" in {ob, nb}:
        return BreakingChange.minor     # VUS↔P o VUS↔B
    return BreakingChange.unknown


def _compute_clinvar_diff(old_vcf: Path, new_vcf: Path) -> list[dict]:
    """
    Compara dos releases de ClinVar y devuelve lista de cambios:
    [{ variant_key, old_sig, new_sig, breaking_change }, ...]
    """
    logger.info(f"Parseando VCF anterior: {old_vcf.name}")
    old_map = _parse_clinvar_vcf(old_vcf)
    logger.info(f"Parseando VCF nuevo: {new_vcf.name} ({len(old_map)} variantes base)")
    new_map = _parse_clinvar_vcf(new_vcf)

    diffs = []
    for key, new_sig in new_map.items():
        old_sig = old_map.get(key)
        if old_sig is None:
            continue  # variante nueva — no reclasificación
        if old_sig != new_sig:
            diffs.append({
                "variant_key": key,
                "old_sig": old_sig,
                "new_sig": new_sig,
                "breaking_change": _classify_breaking_change(old_sig, new_sig),
            })

    logger.info(f"Diff completado: {len(diffs)} cambios de clasificación encontrados")
    return diffs


# ---------------------------------------------------------------------------
# Helpers de descarga
# ---------------------------------------------------------------------------

def _get_latest_clinvar_vcf_url() -> tuple[str, str]:
    index_url = f"{settings.clinvar_ftp_base}/"
    r = requests.get(index_url, timeout=30)
    r.raise_for_status()
    matches = re.findall(r'clinvar_(\d{8})\.vcf\.gz', r.text)
    if not matches:
        raise RuntimeError("No se encontró VCF en el FTP de ClinVar")
    latest = sorted(matches)[-1]
    return f"{settings.clinvar_ftp_base}/clinvar_{latest}.vcf.gz", latest


def _download_file(url: str, dest: Path, chunk_size: int = 1024 * 1024) -> None:
    logger.info(f"Descargando {url} → {dest}")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)
    logger.info(f"Descarga completada: {dest.stat().st_size / 1e6:.1f} MB")


# ---------------------------------------------------------------------------
# Tareas Celery
# ---------------------------------------------------------------------------

@celery_app.task(name="tracker.tasks.run_monthly_clinvar_sync", bind=True, max_retries=3)
def run_monthly_clinvar_sync(self):
    engine = get_db_engine()
    clinvar_dir = Path(settings.clinvar_data_dir)
    clinvar_dir.mkdir(parents=True, exist_ok=True)

    try:
        url, release_str = _get_latest_clinvar_vcf_url()
        release_date = datetime.strptime(release_str, "%Y%m%d").date()

        with Session(engine) as session:
            existing = session.scalar(
                select(ClinVarSyncLog).where(ClinVarSyncLog.release_date == release_date)
            )
            if existing and existing.status == "done":
                logger.info(f"ClinVar {release_str} ya procesado.")
                return {"status": "already_done", "release": release_str}

            sync_log = existing or ClinVarSyncLog(release_date=release_date)
            sync_log.status = "running"
            sync_log.started_at = datetime.utcnow()
            session.add(sync_log)
            session.commit()
            sync_id = str(sync_log.id)

        # 1. Descargar VCF nuevo
        new_vcf = clinvar_dir / f"clinvar_{release_str}.vcf.gz"
        if not new_vcf.exists():
            _download_file(url, new_vcf)

        # 2. Buscar release anterior
        vcf_files = sorted(clinvar_dir.glob("clinvar_????????.vcf.gz"))
        prev_vcfs = [f for f in vcf_files if f != new_vcf]

        if not prev_vcfs:
            logger.info("Primer sync — no hay release previo.")
            with Session(engine) as session:
                log = session.get(ClinVarSyncLog, sync_log.id)
                log.vcf_file = str(new_vcf)
                log.status = "done"
                log.completed_at = datetime.utcnow()
                log.variants_checked = 0
                session.commit()
            return {"status": "first_sync", "release": release_str}

        prev_vcf = prev_vcfs[-1]

        # 3. Diff nativo
        diffs = _compute_clinvar_diff(prev_vcf, new_vcf)

        # 4. Procesar alertas
        _process_diffs(diffs, release_str, release_date, sync_id, engine)

        return {"status": "done", "release": release_str, "diffs": len(diffs)}

    except Exception as exc:
        logger.error(f"Error en sync ClinVar: {exc}", exc_info=True)
        with Session(engine) as session:
            for log in session.scalars(
                select(ClinVarSyncLog).where(ClinVarSyncLog.status == "running")
            ).all():
                log.status = "error"
                log.error_msg = str(exc)
            session.commit()
        raise self.retry(exc=exc, countdown=3600)


def _process_diffs(diffs: list[dict], release_str: str, release_date, sync_id: str, engine):
    """Filtra los diffs con variantes del lab y genera alertas."""
    import uuid as _uuid

    with Session(engine) as session:
        tracked = session.scalars(
            select(TrackedVariant).where(TrackedVariant.active == True)
        ).all()
        tracked_map = {v.variant_key: v for v in tracked}

    if not tracked_map:
        logger.info("No hay variantes activas en el lab.")
        return

    alerts_generated = 0

    for diff in diffs:
        key = diff["variant_key"]
        if key not in tracked_map:
            continue

        variant = tracked_map[key]
        old_sig = diff["old_sig"]
        new_sig = diff["new_sig"]
        breaking = diff["breaking_change"]

        with Session(engine) as session:
            v = session.get(TrackedVariant, variant.id)
            if not v:
                continue

            new_acmg = _map_clinvar_to_acmg(new_sig)

            history = ClassificationHistory(
                variant_id=v.id,
                acmg_class=new_acmg,
                clinvar_sig=new_sig,
                clinvar_release=release_date,
                source="clinvar",
                breaking_change=breaking,
                notes=f"ClinVar {release_str}: {old_sig} → {new_sig}",
            )
            session.add(history)

            v.current_acmg_class = new_acmg
            v.current_clinvar_sig = new_sig
            v.current_clinvar_release = release_date
            v.updated_at = datetime.utcnow()

            alert = VariantAlert(
                variant_id=v.id,
                alert_type="reclassification",
                old_classification=old_sig,
                new_classification=new_sig,
                breaking_change=breaking,
                clinvar_release_new=release_str,
                notified=False,
            )
            session.add(alert)
            session.commit()
            alerts_generated += 1

    with Session(engine) as session:
        log = session.get(ClinVarSyncLog, _uuid.UUID(sync_id))
        if log:
            log.variants_checked = len(diffs)
            log.variants_changed = alerts_generated
            log.alerts_generated = alerts_generated
            log.status = "done"
            log.completed_at = datetime.utcnow()
            session.commit()

    logger.info(f"Sync {release_str}: {len(diffs)} diffs, {alerts_generated} alertas.")
    if alerts_generated > 0:
        send_pending_alerts.delay()


@celery_app.task(name="tracker.tasks.send_pending_alerts")
def send_pending_alerts():
    engine = get_db_engine()

    with Session(engine) as session:
        pending = session.scalars(
            select(VariantAlert).where(VariantAlert.notified == False)
        ).all()

        if not pending:
            return {"sent": 0}

        major = [a for a in pending if a.breaking_change == BreakingChange.major]
        minor = [a for a in pending if a.breaking_change == BreakingChange.minor]
        other = [a for a in pending if a.breaking_change not in (BreakingChange.major, BreakingChange.minor)]

        body = _build_alert_email(major, minor, other, session)
        sent = False

        if settings.smtp_host:
            sent = _send_email(
                subject=f"[{settings.lab_name}] ClinVar: {len(major)} cambios MAYORES, {len(minor)} menores",
                body=body,
            )

        if settings.webhook_url:
            _send_webhook(major, minor, other, session)

        if sent or settings.webhook_url:
            now = datetime.utcnow()
            for alert in pending:
                alert.notified = True
                alert.notified_at = now
            session.commit()

        return {"sent": len(pending), "major": len(major), "minor": len(minor)}


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

_CLINVAR_TO_ACMG = {
    "Pathogenic": ACMGClass.pathogenic,
    "Likely_pathogenic": ACMGClass.likely_pathogenic,
    "Pathogenic/Likely_pathogenic": ACMGClass.likely_pathogenic,
    "Uncertain_significance": ACMGClass.vus,
    "Likely_benign": ACMGClass.likely_benign,
    "Benign": ACMGClass.benign,
    "Benign/Likely_benign": ACMGClass.likely_benign,
    "Conflicting_interpretations_of_pathogenicity": ACMGClass.conflicting,
    "not_provided": ACMGClass.not_provided,
}


def _map_clinvar_to_acmg(clinvar_sig: str) -> ACMGClass:
    return _CLINVAR_TO_ACMG.get(clinvar_sig, ACMGClass.unknown)


def _build_alert_email(major, minor, other, session) -> str:
    lines = [
        "<h2>Informe de Reclasificación ClinVar</h2>",
        f"<p>Fecha: {datetime.utcnow().strftime('%d/%m/%Y')}</p>",
    ]

    def variant_row(alert):
        v = session.get(TrackedVariant, alert.variant_id)
        if not v:
            return ""
        emoji = "🔴" if alert.breaking_change == BreakingChange.major else "🟡"
        return (
            f"<tr><td>{emoji}</td>"
            f"<td><b>{v.gene_symbol or '-'}</b></td>"
            f"<td>{v.patient_pseudonym}</td>"
            f"<td>{v.hgvs_c or v.variant_key}</td>"
            f"<td>{alert.old_classification}</td><td>→</td>"
            f"<td><b>{alert.new_classification}</b></td>"
            f"<td><a href='{v.reev_url}'>REEV</a></td></tr>"
        )

    for title, items in [("🔴 Cambios MAYORES", major), ("🟡 Cambios menores", minor)]:
        if items:
            lines.append(f"<h3>{title} ({len(items)})</h3>")
            lines.append("<table border='1'><tr><th></th><th>Gen</th><th>Paciente</th>"
                         "<th>Variante</th><th>Antes</th><th></th><th>Ahora</th><th>Link</th></tr>")
            lines.extend(variant_row(a) for a in items)
            lines.append("</table>")

    lines.append(f"<hr><p><small>{settings.lab_name}</small></p>")
    return "\n".join(lines)


def _send_email(subject: str, body: str) -> bool:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = settings.smtp_user
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.info(f"Email enviado: {subject}")
        return True
    except Exception as e:
        logger.error(f"Error enviando email: {e}")
        return False


def _send_webhook(major, minor, other, session):
    try:
        payload = {
            "lab": settings.lab_name,
            "date": datetime.utcnow().isoformat(),
            "summary": {"major": len(major), "minor": len(minor), "other": len(other)},
            "alerts": [
                {
                    "gene": (v := session.get(TrackedVariant, a.variant_id)) and v.gene_symbol,
                    "patient": v and v.patient_pseudonym,
                    "variant": v and (v.hgvs_c or v.variant_key),
                    "old": a.old_classification,
                    "new": a.new_classification,
                    "severity": a.breaking_change.value if a.breaking_change else "unknown",
                }
                for a in major + minor
            ],
        }
        requests.post(settings.webhook_url, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Error enviando webhook: {e}")

