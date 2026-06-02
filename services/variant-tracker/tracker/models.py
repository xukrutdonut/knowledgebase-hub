import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Date, Boolean,
    ForeignKey, Enum as SAEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class GenomeBuild(str, enum.Enum):
    grch37 = "GRCh37"
    grch38 = "GRCh38"


class ACMGClass(str, enum.Enum):
    pathogenic = "Pathogenic"
    likely_pathogenic = "Likely_pathogenic"
    vus = "Uncertain_significance"
    likely_benign = "Likely_benign"
    benign = "Benign"
    conflicting = "Conflicting_interpretations_of_pathogenicity"
    not_provided = "not_provided"
    unknown = "unknown"


class BreakingChange(str, enum.Enum):
    major = "major"
    minor = "minor"
    warning = "warning"
    unknown = "unknown"
    null = "null"


class TrackedVariant(Base):
    """Variante de paciente bajo seguimiento activo."""
    __tablename__ = "tracked_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Identificador estable: GRCh38_CHROM_POS_REF_ALT (formato variant-alert)
    variant_key = Column(String(500), unique=True, nullable=False, index=True)
    genome_build = Column(SAEnum(GenomeBuild), default=GenomeBuild.grch38, nullable=False)
    chrom = Column(String(10), nullable=False)
    pos = Column(Integer, nullable=False)
    ref = Column(String(1000), nullable=False)
    alt = Column(String(1000), nullable=False)

    # Anotación génica
    gene_symbol = Column(String(100), index=True)
    hgvs_c = Column(String(500))
    hgvs_p = Column(String(500))
    transcript = Column(String(100))

    # ClinVar
    clinvar_allele_id = Column(String(50), index=True)
    clinvar_rcv = Column(String(50))

    # Clasificación actual (se actualiza con cada sync de ClinVar)
    current_acmg_class = Column(SAEnum(ACMGClass), default=ACMGClass.unknown)
    current_clinvar_sig = Column(String(200))
    current_clinvar_review_status = Column(String(200))
    current_clinvar_release = Column(Date)

    # Datos clínicos del paciente (seudonimizado)
    patient_pseudonym = Column(String(255), nullable=False, index=True)
    patient_hpo_terms = Column(ARRAY(String), default=list)
    zygosity = Column(String(50))
    inheritance = Column(String(100))

    # Control
    active = Column(Boolean, default=True)
    notes = Column(Text)
    added_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    history = relationship("ClassificationHistory", back_populates="variant",
                           cascade="all, delete-orphan", order_by="ClassificationHistory.recorded_at")
    alerts = relationship("VariantAlert", back_populates="variant",
                          cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tracked_gene_active", "gene_symbol", "active"),
        Index("ix_tracked_patient", "patient_pseudonym", "active"),
    )

    @property
    def reev_url(self) -> str:
        build = "grch38" if self.genome_build == GenomeBuild.grch38 else "grch37"
        return f"https://reev.neuropedialab.org/seqvar/{build}-{self.chrom}-{self.pos}-{self.ref}-{self.alt}"


class ClassificationHistory(Base):
    """Historial completo de clasificaciones de una variante."""
    __tablename__ = "classification_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("tracked_variants.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    acmg_class = Column(SAEnum(ACMGClass), nullable=False)
    clinvar_sig = Column(String(200))
    clinvar_review_status = Column(String(200))
    clinvar_release = Column(Date)

    # Origen del cambio
    source = Column(String(50), default="clinvar")  # clinvar | manual | reev | autoacmg
    breaking_change = Column(SAEnum(BreakingChange))

    notes = Column(Text)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    variant = relationship("TrackedVariant", back_populates="history")


class VariantAlert(Base):
    """Alertas generadas por cambios de clasificación."""
    __tablename__ = "variant_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("tracked_variants.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    alert_type = Column(String(50), nullable=False)  # reclassification | new_evidence | removed
    old_classification = Column(String(200))
    new_classification = Column(String(200))
    breaking_change = Column(SAEnum(BreakingChange))

    clinvar_release_old = Column(String(20))
    clinvar_release_new = Column(String(20))

    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime)
    recipients = Column(ARRAY(String), default=list)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    variant = relationship("TrackedVariant", back_populates="alerts")


class ClinVarSyncLog(Base):
    """Registro de sincronizaciones mensuales con ClinVar."""
    __tablename__ = "clinvar_sync_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    release_date = Column(Date, nullable=False, unique=True)
    vcf_file = Column(String(500))
    variants_checked = Column(Integer, default=0)
    variants_changed = Column(Integer, default=0)
    alerts_generated = Column(Integer, default=0)
    status = Column(String(50), default="pending")  # pending | running | done | error
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error_msg = Column(Text)
