# Alternativas Modernas para Análisis de Exomas/Paneles NGS

## 🎯 Objetivo
Reemplazar Exome Slicer (2019, deprecated) con herramientas modernas para evaluar calidad de secuenciación en paneles virtuales NGS.

---

## 🔬 Alternativas Recomendadas

### 1. **GATK (Genome Analysis Toolkit)** ⭐⭐⭐⭐⭐
**Desarrollador:** Broad Institute  
**Última versión:** GATK 4.5+ (2024)  
**Licencia:** BSD 3-Clause (Open Source)

**Características:**
- ✅ Estándar de oro para análisis de variantes
- ✅ Pipeline completo: alineamiento → variantes → QC
- ✅ Excelente para exomas y paneles dirigidos
- ✅ Bien mantenido y actualizado regularmente
- ✅ Docker disponible
- ✅ Compatible con WDL (Workflow Description Language)

**Ventajas:**
- Usado por proyectos como gnomAD, UK Biobank
- Excelente documentación
- Comunidad activa
- Integración con Terra/Cromwell para workflows

**Instalación Docker:**
```bash
docker pull broadinstitute/gatk:latest
```

**Uso básico:**
```bash
docker run -v /data:/data broadinstitute/gatk:latest \
  gatk HaplotypeCaller \
  -R reference.fa \
  -I sample.bam \
  -O variants.vcf
```

**URLs:**
- https://github.com/broadinstitute/gatk
- https://gatk.broadinstitute.org/

---

### 2. **BCFtools + SAMtools** ⭐⭐⭐⭐⭐
**Desarrollador:** Heng Li & comunidad  
**Licencia:** MIT (Open Source)

**Características:**
- ✅ Suite completa para manipulación de archivos NGS
- ✅ Muy rápido y eficiente
- ✅ Ideal para QC y filtrado de variantes
- ✅ Ampliamente usado en producción
- ✅ Soporta VCF, BCF, SAM, BAM, CRAM

**Ventajas:**
- Ligero y rápido
- Bajo consumo de recursos
- Perfecto para RPi/ARM
- Scripts y pipelines sencillos

**Instalación Docker:**
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y \
    bcftools samtools tabix \
    && rm -rf /var/lib/apt/lists/*
```

**Uso básico:**
```bash
# QC de BAM
samtools flagstat sample.bam
samtools stats sample.bam

# Análisis de variantes
bcftools stats variants.vcf
bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\n' variants.vcf
```

**URLs:**
- http://www.htslib.org/
- https://github.com/samtools/bcftools

---

### 3. **MultiQC** ⭐⭐⭐⭐⭐
**Desarrollador:** Phil Ewels (Seqera Labs)  
**Última versión:** 1.20+ (2024)  
**Licencia:** GPL-3.0 (Open Source)

**Características:**
- ✅ Agregador de reportes de QC
- ✅ Interfaz web interactiva
- ✅ Soporta 100+ herramientas bioinformáticas
- ✅ Reportes HTML hermosos y exportables
- ✅ Ideal para paneles y exomas

**Ventajas:**
- Consolida múltiples herramientas en un solo reporte
- Muy fácil de usar
- Interfaz moderna
- Perfecto para presentar resultados

**Herramientas compatibles:**
- FastQC, SAMtools, GATK, Picard
- Qualimap, Mosdepth, VerifyBAMID
- Y muchas más...

**Instalación Docker:**
```bash
docker pull quay.io/biocontainers/multiqc:latest
```

**Uso:**
```bash
docker run -v /data:/data quay.io/biocontainers/multiqc \
  multiqc /data/qc_results/ -o /data/reports/
```

**URLs:**
- https://multiqc.info/
- https://github.com/ewels/MultiQC

---

### 4. **Nextflow + nf-core/sarek** ⭐⭐⭐⭐⭐
**Desarrollador:** Seqera Labs + nf-core community  
**Licencia:** Apache 2.0 / MIT (Open Source)

**Características:**
- ✅ Pipeline completo germline/somatic
- ✅ Workflow reproducible y portable
- ✅ Incluye todo: QC, alineamiento, variantes
- ✅ Optimizado para exomas y paneles
- ✅ Reportes automáticos con MultiQC

**Ventajas:**
- Pipeline "todo en uno"
- Muy bien documentado
- Actualizado constantemente
- Usa mejores prácticas GATK

**Instalación:**
```bash
# Nextflow
curl -s https://get.nextflow.io | bash

# Pipeline sarek
nextflow run nf-core/sarek -profile docker \
  --input samplesheet.csv \
  --genome GRCh38 \
  --intervals targets.bed
```

**URLs:**
- https://nf-co.re/sarek
- https://www.nextflow.io/

---

### 5. **Qualimap** ⭐⭐⭐⭐
**Desarrollador:** Spanish National Cancer Research Centre  
**Última versión:** 2.3 (2023)  
**Licencia:** GPL-3.0 (Open Source)

**Características:**
- ✅ QC especializado para NGS
- ✅ Reportes HTML detallados
- ✅ Métricas específicas para exomas/paneles
- ✅ Interfaz gráfica opcional
- ✅ Análisis de cobertura profundo

**Ventajas:**
- Específico para targeted sequencing
- Gráficos de cobertura excelentes
- Detecta regiones problemáticas
- Integra bien con MultiQC

**Instalación Docker:**
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y \
    qualimap \
    && rm -rf /var/lib/apt/lists/*
```

**Uso:**
```bash
qualimap bamqc \
  -bam sample.bam \
  -gff targets.bed \
  -outdir qc_results/
```

**URLs:**
- http://qualimap.conesalab.org/
- https://github.com/scchess/Qualimap

---

### 6. **VarDict** ⭐⭐⭐⭐
**Desarrollador:** AstraZeneca  
**Licencia:** MIT (Open Source)

**Características:**
- ✅ Caller de variantes sensible
- ✅ Optimizado para paneles pequeños
- ✅ Detecta variantes de baja frecuencia
- ✅ Bueno para muestras tumorales

**Ventajas:**
- Muy sensible (baja frecuencia alélica)
- Rápido en regiones pequeñas
- Ideal para paneles clínicos

**URLs:**
- https://github.com/AstraZeneca-NGS/VarDict

---

### 7. **Mosdepth** ⭐⭐⭐⭐⭐
**Desarrollador:** Brent Pedersen  
**Licencia:** MIT (Open Source)

**Características:**
- ✅ Análisis de cobertura ultra-rápido
- ✅ Mucho más rápido que samtools depth
- ✅ Ideal para evaluar paneles
- ✅ Gráficos de distribución de cobertura

**Ventajas:**
- Extremadamente rápido (usa threads)
- Bajo consumo de memoria
- Perfecto para QC de paneles

**Instalación:**
```bash
docker pull quay.io/biocontainers/mosdepth:latest
```

**Uso:**
```bash
mosdepth -t 4 -b targets.bed sample sample.bam
```

**URLs:**
- https://github.com/brentp/mosdepth

---

## 🎯 Recomendaciones por Caso de Uso

### Para Evaluación Rápida de Calidad (QC):
```
MultiQC + Mosdepth + SAMtools
```
- Rápido
- Reportes bonitos
- Bajo consumo de recursos

### Para Pipeline Completo:
```
Nextflow + nf-core/sarek
```
- Todo incluido
- Reproducible
- Mejores prácticas

### Para Análisis Manual/Exploración:
```
GATK + BCFtools + IGV (visualización)
```
- Control total
- Flexible
- Estándar de la industria

### Para Paneles Clínicos Pequeños:
```
VarDict + Qualimap + MultiQC
```
- Sensible a variantes raras
- QC detallado
- Reportes profesionales

---

## 🐳 Stack Recomendado para tu Swarm

### Opción 1: Pipeline Ligero (Recomendado para RPi)
```yaml
version: '3.8'
services:
  multiqc:
    image: quay.io/biocontainers/multiqc:latest
    volumes:
      - ./data:/data
    command: multiqc /data/qc -o /data/reports

  mosdepth:
    image: quay.io/biocontainers/mosdepth:latest
    volumes:
      - ./data:/data
```

### Opción 2: GATK Completo
```yaml
version: '3.8'
services:
  gatk:
    image: broadinstitute/gatk:latest
    volumes:
      - ./data:/data
      - ./reference:/reference
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4'
```

---

## 📊 Comparativa

| Herramienta | Complejidad | Recursos | Mantenimiento | Recomendación |
|-------------|-------------|----------|---------------|---------------|
| **MultiQC** | Baja | Bajo | Activo | ⭐⭐⭐⭐⭐ |
| **GATK** | Alta | Alto | Activo | ⭐⭐⭐⭐⭐ |
| **Mosdepth** | Baja | Bajo | Activo | ⭐⭐⭐⭐⭐ |
| **nf-core/sarek** | Media | Medio | Activo | ⭐⭐⭐⭐⭐ |
| **BCFtools** | Media | Bajo | Activo | ⭐⭐⭐⭐⭐ |
| **Qualimap** | Media | Medio | Activo | ⭐⭐⭐⭐ |
| **VarDict** | Media | Medio | Activo | ⭐⭐⭐⭐ |

---

## 🚀 Próximos Pasos

1. **Para empezar rápido:** Instalar MultiQC + Mosdepth
2. **Para análisis completo:** Desplegar nf-core/sarek
3. **Para flexibilidad máxima:** GATK + BCFtools

¿Cuál quieres que instale primero?
