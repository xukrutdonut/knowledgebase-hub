"""FastAPI — Variant Tracker REST API"""
import uuid
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from tracker.config import get_settings
from tracker.models import (
    Base, TrackedVariant, ClassificationHistory,
    VariantAlert, ClinVarSyncLog,
    ACMGClass, BreakingChange, GenomeBuild
)
from tracker.tasks import celery_app, run_monthly_clinvar_sync

logger = logging.getLogger(__name__)
settings = get_settings()
engine = create_engine(settings.database_url_sync)


def _wait_for_db(retries: int = 10, delay: int = 3):
    """Espera a que postgres esté disponible antes de arrancar."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Conexión a postgres establecida")
            return
        except OperationalError as e:
            logger.warning(f"⏳ Postgres no disponible (intento {attempt}/{retries}): {e}")
            if attempt == retries:
                raise
            time.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _wait_for_db()
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Variant Tracker — Neuropediatría",
    description="Seguimiento de variantes de pacientes y alertas de reclasificación ClinVar",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    with Session(engine) as session:
        yield session


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class VariantCreate(BaseModel):
    genome_build: GenomeBuild = GenomeBuild.grch38
    chrom: str
    pos: int
    ref: str
    alt: str
    gene_symbol: Optional[str] = None
    hgvs_c: Optional[str] = None
    hgvs_p: Optional[str] = None
    transcript: Optional[str] = None
    clinvar_allele_id: Optional[str] = None
    current_acmg_class: ACMGClass = ACMGClass.unknown
    current_clinvar_sig: Optional[str] = None
    patient_pseudonym: str
    patient_hpo_terms: list[str] = Field(default_factory=list)
    zygosity: Optional[str] = None
    inheritance: Optional[str] = None
    notes: Optional[str] = None


class VariantOut(BaseModel):
    id: str
    variant_key: str
    genome_build: str
    chrom: str
    pos: int
    ref: str
    alt: str
    gene_symbol: Optional[str]
    hgvs_c: Optional[str]
    hgvs_p: Optional[str]
    current_acmg_class: str
    current_clinvar_sig: Optional[str]
    current_clinvar_release: Optional[str]
    patient_pseudonym: str
    patient_hpo_terms: list[str]
    active: bool
    reev_url: str
    added_at: str
    updated_at: str
    alert_count: int = 0

    @classmethod
    def from_orm(cls, v: TrackedVariant, alert_count: int = 0):
        return cls(
            id=str(v.id),
            variant_key=v.variant_key,
            genome_build=v.genome_build.value,
            chrom=v.chrom,
            pos=v.pos,
            ref=v.ref,
            alt=v.alt,
            gene_symbol=v.gene_symbol,
            hgvs_c=v.hgvs_c,
            hgvs_p=v.hgvs_p,
            current_acmg_class=v.current_acmg_class.value,
            current_clinvar_sig=v.current_clinvar_sig,
            current_clinvar_release=v.current_clinvar_release.isoformat() if v.current_clinvar_release else None,
            patient_pseudonym=v.patient_pseudonym,
            patient_hpo_terms=v.patient_hpo_terms or [],
            active=v.active,
            reev_url=v.reev_url,
            added_at=v.added_at.isoformat(),
            updated_at=v.updated_at.isoformat(),
            alert_count=alert_count,
        )


class AlertOut(BaseModel):
    id: str
    variant_id: str
    gene_symbol: Optional[str]
    patient_pseudonym: Optional[str]
    hgvs_c: Optional[str]
    variant_key: str
    alert_type: str
    old_classification: Optional[str]
    new_classification: Optional[str]
    breaking_change: Optional[str]
    clinvar_release_new: Optional[str]
    notified: bool
    created_at: str
    reev_url: str


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints — Variantes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "variant-tracker"}


@app.get("/api/v1/variants", response_model=list[VariantOut])
def list_variants(
    patient: Optional[str] = None,
    gene: Optional[str] = None,
    acmg_class: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    q = select(TrackedVariant)
    if active_only:
        q = q.where(TrackedVariant.active == True)
    if patient:
        q = q.where(TrackedVariant.patient_pseudonym.ilike(f"%{patient}%"))
    if gene:
        q = q.where(TrackedVariant.gene_symbol.ilike(f"%{gene}%"))
    if acmg_class:
        q = q.where(TrackedVariant.current_acmg_class == acmg_class)

    variants = db.scalars(q.order_by(TrackedVariant.added_at.desc())).all()

    result = []
    for v in variants:
        alert_count = db.scalar(
            select(func.count(VariantAlert.id))
            .where(VariantAlert.variant_id == v.id, VariantAlert.notified == False)
        ) or 0
        result.append(VariantOut.from_orm(v, alert_count))
    return result


@app.post("/api/v1/variants", response_model=VariantOut, status_code=201)
def add_variant(data: VariantCreate, db: Session = Depends(get_db)):
    build_prefix = "GRCh38" if data.genome_build == GenomeBuild.grch38 else "GRCh37"
    variant_key = f"{build_prefix}_{data.chrom}_{data.pos}_{data.ref}_{data.alt}"

    existing = db.scalar(select(TrackedVariant).where(TrackedVariant.variant_key == variant_key))
    if existing:
        # Reactivar si estaba inactivo
        if not existing.active:
            existing.active = True
            existing.patient_pseudonym = data.patient_pseudonym
            db.commit()
            return VariantOut.from_orm(existing)
        raise HTTPException(400, f"Variante ya registrada: {variant_key}")

    variant = TrackedVariant(
        variant_key=variant_key,
        genome_build=data.genome_build,
        chrom=data.chrom,
        pos=data.pos,
        ref=data.ref,
        alt=data.alt,
        gene_symbol=data.gene_symbol,
        hgvs_c=data.hgvs_c,
        hgvs_p=data.hgvs_p,
        transcript=data.transcript,
        clinvar_allele_id=data.clinvar_allele_id,
        current_acmg_class=data.current_acmg_class,
        current_clinvar_sig=data.current_clinvar_sig,
        patient_pseudonym=data.patient_pseudonym,
        patient_hpo_terms=data.patient_hpo_terms,
        zygosity=data.zygosity,
        inheritance=data.inheritance,
        notes=data.notes,
    )
    db.add(variant)

    # Registrar clasificación inicial en historial
    if data.current_acmg_class != ACMGClass.unknown:
        history = ClassificationHistory(
            variant_id=variant.id,
            acmg_class=data.current_acmg_class,
            clinvar_sig=data.current_clinvar_sig,
            source="manual",
            notes="Clasificación inicial al registrar la variante",
        )
        db.add(history)

    db.commit()
    db.refresh(variant)
    return VariantOut.from_orm(variant)


@app.get("/api/v1/variants/{variant_id}", response_model=VariantOut)
def get_variant(variant_id: str, db: Session = Depends(get_db)):
    v = db.get(TrackedVariant, uuid.UUID(variant_id))
    if not v:
        raise HTTPException(404, "Variante no encontrada")
    alert_count = db.scalar(
        select(func.count(VariantAlert.id))
        .where(VariantAlert.variant_id == v.id, VariantAlert.notified == False)
    ) or 0
    return VariantOut.from_orm(v, alert_count)


@app.delete("/api/v1/variants/{variant_id}", status_code=204)
def deactivate_variant(variant_id: str, db: Session = Depends(get_db)):
    v = db.get(TrackedVariant, uuid.UUID(variant_id))
    if not v:
        raise HTTPException(404, "Variante no encontrada")
    v.active = False
    db.commit()


@app.get("/api/v1/variants/{variant_id}/history")
def get_history(variant_id: str, db: Session = Depends(get_db)):
    v = db.get(TrackedVariant, uuid.UUID(variant_id))
    if not v:
        raise HTTPException(404, "Variante no encontrada")
    return [
        {
            "id": str(h.id),
            "acmg_class": h.acmg_class.value,
            "clinvar_sig": h.clinvar_sig,
            "clinvar_release": h.clinvar_release.isoformat() if h.clinvar_release else None,
            "source": h.source,
            "breaking_change": h.breaking_change.value if h.breaking_change else None,
            "notes": h.notes,
            "recorded_at": h.recorded_at.isoformat(),
        }
        for h in v.history
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints — Alertas
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/alerts", response_model=list[AlertOut])
def list_alerts(
    unread_only: bool = True,
    breaking_change: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = select(VariantAlert).join(TrackedVariant)
    if unread_only:
        q = q.where(VariantAlert.notified == False)
    if breaking_change:
        q = q.where(VariantAlert.breaking_change == breaking_change)

    alerts = db.scalars(q.order_by(VariantAlert.created_at.desc())).all()

    result = []
    for a in alerts:
        v = db.get(TrackedVariant, a.variant_id)
        result.append(AlertOut(
            id=str(a.id),
            variant_id=str(a.variant_id),
            gene_symbol=v.gene_symbol if v else None,
            patient_pseudonym=v.patient_pseudonym if v else None,
            hgvs_c=v.hgvs_c if v else None,
            variant_key=v.variant_key if v else "",
            alert_type=a.alert_type,
            old_classification=a.old_classification,
            new_classification=a.new_classification,
            breaking_change=a.breaking_change.value if a.breaking_change else None,
            clinvar_release_new=a.clinvar_release_new,
            notified=a.notified,
            created_at=a.created_at.isoformat(),
            reev_url=v.reev_url if v else "",
        ))
    return result


@app.post("/api/v1/alerts/{alert_id}/mark-read", status_code=204)
def mark_alert_read(alert_id: str, db: Session = Depends(get_db)):
    a = db.get(VariantAlert, uuid.UUID(alert_id))
    if not a:
        raise HTTPException(404, "Alerta no encontrada")
    a.notified = True
    a.notified_at = datetime.utcnow()
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints — Sync ClinVar
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/clinvar/sync")
def trigger_clinvar_sync():
    """Dispara manualmente el sync de ClinVar (no esperar al cron mensual)."""
    task = run_monthly_clinvar_sync.apply_async(queue="clinvar")
    return {"task_id": task.id, "status": "queued"}


@app.get("/api/v1/clinvar/history")
def get_sync_history(db: Session = Depends(get_db)):
    logs = db.scalars(
        select(ClinVarSyncLog).order_by(ClinVarSyncLog.release_date.desc()).limit(24)
    ).all()
    return [
        {
            "id": str(log.id),
            "release_date": log.release_date.isoformat(),
            "status": log.status,
            "variants_checked": log.variants_checked,
            "variants_changed": log.variants_changed,
            "alerts_generated": log.alerts_generated,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            "error_msg": log.error_msg,
        }
        for log in logs
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints — Estadísticas
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(TrackedVariant.id)).where(TrackedVariant.active == True))
    unread_alerts = db.scalar(select(func.count(VariantAlert.id)).where(VariantAlert.notified == False))
    major_alerts = db.scalar(
        select(func.count(VariantAlert.id))
        .where(VariantAlert.notified == False, VariantAlert.breaking_change == BreakingChange.major)
    )

    by_class = db.execute(
        select(TrackedVariant.current_acmg_class, func.count())
        .where(TrackedVariant.active == True)
        .group_by(TrackedVariant.current_acmg_class)
    ).all()

    last_sync = db.scalar(
        select(ClinVarSyncLog).order_by(ClinVarSyncLog.release_date.desc())
    )

    return {
        "total_variants": total,
        "unread_alerts": unread_alerts,
        "major_alerts": major_alerts,
        "by_acmg_class": {row[0].value: row[1] for row in by_class},
        "last_clinvar_sync": {
            "release_date": last_sync.release_date.isoformat() if last_sync else None,
            "status": last_sync.status if last_sync else None,
        } if last_sync else None,
    }
