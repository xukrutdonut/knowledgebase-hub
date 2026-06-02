# NeuropedGx Hub — Guía de Uso Clínico

**Versión:** 2026.06 | **Audiencia:** Neuropediatras, genetistas clínicos, consejeros genéticos  
**URL local:** http://localhost:8405 | **API:** http://localhost:8405/docs

> ⚠️ **Aviso importante:** NeuropedGx Hub es una capa de **recomendación y orientación clínica**, no un clasificador automático. La clasificación definitiva de variantes debe realizarse en REEV/auto-ACMG con criterio del genetista responsable.

---

## Índice

1. [Arquitectura del sistema](#arquitectura)
2. [Flujo de trabajo por grupo de enfermedad](#flujos)
   - [Canalopatías](#canalopatias)
   - [DEE (Epilepsias del desarrollo y epilépticas)](#dee)
   - [RASopatías](#rasopatias)
   - [mTORopatías](#mtoropatias)
   - [Cohesinopatías](#cohesinopatias)
   - [Microtubulopatías](#microtubulopatias)
   - [Remodelación de cromatina / Factores de transcripción](#cromatina)
   - [Sinaptopatías](#sinaptopatias)
   - [Mitocondriales](#mitocondriales)
   - [Metabólicas](#metabolicas)
   - [Leucodistrofias / Mielino](#leucodistrofias)
   - [Reparación del ADN](#dna-repair)
   - [Ciliopatías con afectación SNC](#ciliopatias)
3. [Alertas terapéuticas urgentes](#alertas)
4. [Interpretación de flags del sistema](#flags)
5. [Integración con el stack genómico](#integracion)
6. [Limitaciones y caveats](#limitaciones)

---

## 1. Arquitectura del sistema {#arquitectura}

```
VCF / variante individual
        │
        ▼
   REEV (anotación, ACMG automático, HGVS, ClinVar, gnomAD)
        │
        ├──► auto-ACMG (clasificación automática basada en reglas)
        │
        ▼
  NeuropedGx Hub ◄── POST /api/variant/classify
        │
        ├── ¿El gen está en el panel? → grupos de enfermedad, mecanismo
        ├── ¿La variante es un hotspot conocido? → flag inmediato
        ├── Flags específicos del grupo: GoF/LoF dual, mosaicismo, dominante negativo
        ├── Notas de interpretación gene-específicas (perlas clínicas)
        ├── Criterios ACMG gene-específicos (PM1, PS3, PP3, etc.)
        └── Links: REEV, Visualizador 3D (Mol*/AlphaFold), gnomAD, ClinVar
                │
                ▼
        Protein Viewer (estructura AlphaFold con dominio de la variante)
```

**Componentes del stack:**

| Servicio | Puerto | Función |
|---|---|---|
| REEV | :8200 | Anotación, ACMG, ClinVar, gnomAD |
| auto-ACMG | interno | Clasificación ACMG automática |
| protein-viewer | :8404 | Visualización 3D (Mol* + AlphaFold) |
| variant-tracker | :8403 | Gestión de variantes del laboratorio |
| **NeuropedGx Hub** | **:8405** | Contexto neuropediátrico, orientación clínica |

---

## 2. Flujo de trabajo por grupo de enfermedad {#flujos}

### Canalopatías {#canalopatias}
**Genes clave:** SCN1A, SCN2A, SCN8A, KCNQ2, KCNT1, CACNA1A, HCN1, CLCN4…

**Flujo recomendado:**

1. **Anotar en REEV** → obtener HGVS normalizado, frecuencia gnomAD, ClinVar.
2. **Clasificar en NeuropedGx Hub** → el sistema devuelve:
   - Flag GoF vs LoF (crítico para decisión terapéutica)
   - Alerta si hotspot conocido (p.ej., SCN2A p.Arg1882Gln)
3. **Visualizar en Protein Viewer** → localizar la variante en el dominio del canal (VSD, poro, inactivación).
4. **Interpretar según mecanismo:**
   - **GoF (SCN2A neonatal, SCN8A, KCNT1):** Considerar bloqueantes de sodio (fenitoína, carbamazepina en SCN2A neonatal). **Evitar bloqueantes de sodio en LoF.**
   - **LoF (SCN1A/Dravet):** Evitar bloqueantes de sodio (carbamazepina, fenitoína, lamotrigina, rufinamida). Usar valproato, clobazam, estiripentol, fenfluramine, cannabidiol.
   - **KCNQ2 GoF:** Considerar retigabina/ezogabina (abridor de canal) si disponible.
   - **KCNT1:** quinidina experimental (evidencia limitada).

**Puntos críticos:**
- SCN2A: la edad de inicio predice el mecanismo. Inicio <3 meses → GoF. Inicio >2 años → LoF. Impacto terapéutico directo.
- CACNA1A: mismo gen causa hemiplejia alternante (GoF), ataxia episódica tipo 2 (LoF) y ataxia cerebelosa progresiva. Verificar p.Arg192Gln para EA2.

---

### DEE — Epilepsias del Desarrollo y Epilépticas {#dee}
**Genes clave:** CDKL5, ARX, FOXG1, MEF2C, TCF4, SHANK3, SYNGAP1…

**Concepto clave:** DEE es una etiqueta funcional (síndrome), no un mecanismo. Muchos genes de otros grupos (canalopatías, RASopatías) también causan DEE.

**Flujo:**
1. Clasificar la variante en NeuropedGx Hub → el gen puede aparecer en múltiples grupos.
2. CDKL5: verificar si es en el dominio quinasa (exones 1-12) → mayor severidad.
3. ARX: variantes de expansión de polialanina (p.Ala(23dup), p.Ala(14dup)) → patrón diferente a truncantes. Herencia XLD.
4. FOXG1: patrones posicionales (N-terminal vs C-terminal). Síndrome congénito vs regresivo.

---

### RASopatías {#rasopatias}
**Genes clave:** PTPN11, SOS1, RAF1, BRAF, MAP2K1, MAP2K2, KRAS, HRAS, NRAS, SHOC2, CBL, RIT1, RASA1, NF1, SPRED1…

**Concepto clave:** Hiperactivación de la vía RAS/MAPK. Todos los genes actúan en la misma cascada de señalización.

**Flujo:**
1. NeuropedGx Hub identifica el gen como rasopathy y devuelve el contexto de la vía.
2. Verificar si hay hotspot específico de síndrome (p.ej., PTPN11 p.Asp61Gly → Síndrome de Noonan con leucemia mieloide).
3. **Manifestaciones neuropediátricas:** DI leve-moderada, dificultades de aprendizaje, macrocefalia, hipotoría, hidrocefalia.
4. NF1: riesgo de glioma óptico, tumores SNC → imagen cerebral en contexto clínico.
5. **Inhibidores MEK:** trametinib (uso en tumores NF1-asociados, experimental en otras manifestaciones).

**Flags del sistema:**
- `[GoF/hiperactivación de vía RAS-MAPK]` → orienta a mecanismo de ganancia de función en la cascada.
- `[somatic_mosaicism_risk]` → HRAS (síndrome de Costello) y otros pueden presentar mosaicismo.

---

### mTORopatías {#mtoropatias}
**Genes clave:** MTOR, PIK3CA, PIK3R1, TSC1, TSC2, PTEN, AKT3, RHEB, DEPDC5, NPRL2, NPRL3…

**CRÍTICO — Mosaicismo somático:**

> ⚠️ PIK3CA y MTOR frecuentemente causan enfermedad por **mosaicismo somático cerebral** (HMEG, FCD tipo II). El WES estándar de sangre puede ser **NEGATIVO**. Requiere:
> - Secuenciación de tejido cerebral (quirúrgico) con profundidad ≥500x
> - Panel de mosaicismo somático con VAF de detección <1%
> - Si hay FCD en RMN y epilepsia refractaria → sospechar mTORopatía somática incluso con WES negativo

**Flujo:**
1. Si RMN muestra esclerosis tuberosa o FCD → NeuropedGx Hub alerta sobre mosaicismo.
2. TSC1/TSC2: diagnóstico frecuentemente clínico (criterios Northam). Everolimus/sirolimus para SEGA y angiomiolipomas.
3. DEPDC5/NPRL2/NPRL3 (complejo GATOR1): epilepsia focal de buen pronóstico con cirugía → considerar evaluación quirúrgica temprana.
4. PTEN: macrocefalia + autismo → solicitar PTEN. Riesgo tumoral elevado (síndrome de Cowden-like).

---

### Cohesinopatías {#cohesinopatias}
**Genes clave:** NIPBL, SMC1A, SMC3, RAD21, HDAC8, ESCO2, PDS5A, PDS5B, ANKRD11 (KBG), EP300, CREBBP…

**Concepto:** Alteración del complejo cohesina → errores en la regulación transcripcional durante el desarrollo.

**Flujo:**
1. Síndrome de Cornelia de Lange (NIPBL, SMC1A, SMC3): fenotipo variable. NIPBL → formas más severas.
2. HDAC8: XLD. Varones hemizigóticos más afectados; portadoras pueden tener fenotipo leve.
3. ANKRD11 (síndrome KBG): dientes grandes, macrodontia característica + DI + baja estatura.
4. EP300/CREBBP (Rubinstein-Taybi): pulgares anchos característicos. Riesgo de tumores (neural crest).
5. **Verificar:** variantes intrónicas profundas, SVs (CNVs, inversiones) frecuentes en NIPBL.

---

### Microtubulopatías {#microtubulopatias}
**Genes clave:** TUBA1A, TUBB2B, TUBB3, TUBB4A, LIS1 (PAFAH1B1), DCX, DYNC1H1, KIF2A, KIF5C, CENPJ/CPAP…

**Flujo:**
1. **Patrones de imagen cerebelar:**
   - Lisencefalia clásica: LIS1 (más grave si deleccion), DCX (lisencefalia en ♂, band heterotopia en ♀)
   - Cobblestone lisencefalia: POMT1, POMT2, FKTN, FKRP (distrofinopatías musculares → síndrome Walker-Warburg)
   - Micropoligiria: TUBB2B → micropoligiria bilateral fronto-parietal
2. TUBA1A: amplio espectro — lissencefalia, agiria, heterotopia de banda, hipoplasia cerebelosa.
3. TUBB4A: HDLS (leucodistrofia + distrofia musculares), también causa distonía (DYT4).
4. DCX: recuerda la herencia XLD — secuenciar siempre DCX en varones con lisencefalia.
5. **Coordinar con neurorradiología** para catalogación del patrón de malformación.

---

### Remodelación de Cromatina / Factores de Transcripción {#cromatina}
**Genes clave (cromatina):** ARID1B, CHD7, CHD8, KDM5C, SETD5, EHMT1, KMT2A, KMT2D, DNMT3A, SETBP1, MBD5…  
**Genes clave (TFs):** FOXG1, MEF2C, TCF4, PURA, TBR1, SATB2, ZEB2, SOX11, ZBTB20, BCL11B…

**Concepto clave:** Muchos genes de este grupo se expresan en ventanas temporales específicas del neurodesarrollo. Las variantes de novo son predominantes.

**Flujo:**
1. CHD7 (CHARGE): verificar criterios CHARGE (coloboma, anomalías cardíacas, atresia coanal, retraso, genitales hipoplásicos, anomalías de oído). Evaluar audición siempre.
2. KMT2D/KMT2A: síndrome de Kabuki (KMT2D, KDM6A) — rasgos faciales + DI + anomalías óseas + cardiacas.
3. DNMT3A (Tatton-Brown-Rahman): overgrowth + DI. Riesgo de tumor de Wilms.
4. SETD5: DI moderada + TDAH prominente. Considerar en DEI + comportamiento.
5. TCF4 (Pitt-Hopkins): apneas + dismotilidad → evaluación respiratoria y GI rutinaria.
6. TBR1, SATB2: analizar en contexto de TEA + DI + anomalías del cuerpo calloso.

---

### Sinaptopatías {#sinaptopatias}
**Genes clave:** SYNGAP1, SHANK3, SHANK2, NRXN1, NLGN3, NLGN4X, CNTN5, CNTNAP2, STXBP1, CASK, GRIN2A, GRIN2B…

**Nota:** SYNGAP1 es simultáneamente sinaptopatía y RASopatía (regula RAS en sinapsis).

**Flujo:**
1. STXBP1 (síndrome de Ohtahara): LoF de SNARE → epilepsia de inicio neonatal grave.
2. SYNGAP1: DI + epilepsia + TEA. Sensibilidad a estimulación (fotosensibilidad frecuente). Dieta baja en grasa experimental.
3. SHANK3 (síndrome de Phelan-McDermid): velocidad de regresión con fiebre → verificar episodios de regresión aguda.
4. GRIN2A/GRIN2B: variantes en el dominio ATD (aminoterminal) vs canal tienen diferente impacto. GoF → considerar memantina (experimental).
5. NLGN3/NLGN4X: herencia ligada al X → secuenciar en familias con múltiples varones afectados.

---

### Mitocondriales {#mitocondriales}
**Genes nucleares:** POLG, SURF1, SDHA, SCO2, COX10, DGUOK, RRM2B, TWNK, TFAM, MPV17…  
**mtDNA:** (variantes en mtDNA no cubiertas en este panel nuclear)

**ALERTA CRÍTICA:**
> 🚨 **POLG:** El **ácido valproico está CONTRAINDICADO** en pacientes con variantes patogénicas en POLG (síndrome de Alpers-Huttenlocher). El VPA puede precipitar fallo hepático agudo fatal. NeuropedGx Hub genera alerta automática.

**Flujo:**
1. Sospecha clínica: combinación de síntomas multisistémicos (neuromusculares + hepáticos + cardíacos) + histología (ragged red fibers, COX-neg).
2. POLG: secuenciar en epilepsia + neuropatía + regresión + afectación hepática. Verificar **ambos alelos** (AR).
3. SURF1 (Leigh): RMN muestra lesiones simétricas en ganglios de la base. Tiamina, biotina, coenzima Q10 empíricos.
4. DGUOK/TWNK: síndrome de depleción del mtDNA → indicación de trasplante hepático en algunos casos.
5. Coordinar con **bioquímica:** cadena respiratoria en músculo, lactato/piruvato, aminoácidos.

---

### Enfermedades Metabólicas {#metabolicas}
**Genes clave:** ALDH7A1, PNPO, SLC2A1, SLC19A3, SLC6A8, PKU (PAH), GFAP, PLP1, GBA, HEXA, HEXB, GALC, ARSA, NPC1, NPC2, ATP7A, ATP7B, OTC, CPS1, ASS1, ASL…

**Alertas terapéuticas urgentes (ver sección 3):**

| Gen | Alerta | Tratamiento |
|---|---|---|
| ALDH7A1 | Epilepsia dependiente de piridoxina | Piridoxina 100mg IV → diagnóstico-terapéutico |
| PNPO | Epilepsia dependiente de PLP | Piridoxal-5-fosfato (no piridoxina) |
| SLC2A1 | Déficit de GLUT1 | Dieta cetogénica → muy efectiva |
| SLC19A3 | Déficit de tiamina/biotina | Biotina + tiamina (biotin-thiamine-responsive) |
| OTC | Déficit de OTC (XLD) | Evitar proteína alta, bencilpenicilina en crisis |

**Flujo:**
1. En epilepsia neonatal o infantil de causa no filiada → NeuropedGx Hub alerta sobre metabolopatías tratables.
2. Solicitar perfil metabólico: aminoácidos plasma/orina, ácidos orgánicos, acilcarnitinas, neurotransmisores LCR.
3. Piridoxina empírica en epilepsia neonatal refractaria antes de conocer resultado genético.

---

### Leucodistrofias / Enfermedades de la Mielina {#leucodistrofias}
**Genes clave:** MLC1, GJB1, PLP1, GALC, ARSA, ABCD1, LMNB1, ADAR, RNASEH2A/B/C, TREX1, IFIH1 (Aicardi-Goutières), EIF2B1-5, GFAP (Alexander)…

**Concepto:** Amplio grupo con patrón leucodistrófico en RMN. La genética guía el diagnóstico y la historia natural.

**Flujo:**
1. Evaluar patrón de señal en RMN (sustancia blanca periférica vs profunda vs U-fibers, sustancia gris, tronco, cerebelo).
2. ADAR/RNASEH/TREX1/IFIH1 (Aicardi-Goutières): leucodistrofia + calcificaciones + interferonpatía. Riesgo de LES-like. Inhibidores JAK en ensayos clínicos.
3. GALC (Krabbe): determinación de actividad galactocerebrosidasa en leucocitos. **Trasplante de CPH en fase presintomática** → ventana diagnóstica crítica.
4. ARSA (MLD): actividad arilsulfatasa A. Terapia génica (atidarsagene autotemcel) aprobada en forma juvenil temprana.
5. ABCD1 (X-ALD): solo en varones. Proteína ALDP por citometría. Trasplante / terapia génica en forma cerebral infantil.
6. EIF2B (leucodistrofia vanilinante): exacerbaciones con infecciones febriles → evitar fiebre prolongada.
7. GFAP (Alexander): diagnóstico clínico-radiológico (macrocefalia, megalencefalia, punta frontal). Mutaciones de novo.

---

### Reparación del ADN {#dna-repair}
**Genes clave:** ATM, MRE11, NBN, RAD50, BRCA2 (Fanconi), FANC genes, XPC/XPD/XPG (Xeroderma), ERCC genes, APTX (Ataxia-Oculomotora 1), SETX (AOA2), DNMT3B (ICF)…

**Flujo:**
1. Clínica: ataxia cerebelosa progresiva + inmunodeficiencia + telangiectasias → ATM (ataxia-telangiectasia).
2. ATM: nivel de alfafetoproteína elevado → útil como biomarcador. Evitar rayos X innecesarios (radiosensibilidad). **Riesgo oncológico elevado** → seguimiento tumoral.
3. Fanconi (FANC genes): anemia aplásica + malformaciones radiales. Prueba de fragilidad cromosómica con DEB/MMC.
4. Xeroderma pigmentoso: fotosensibilidad extrema + tumores cutáneos + afectación neurológica variable.
5. **Consejo genético tumoral** coordinado con oncología/genética.

---

### Ciliopatías con Afectación SNC {#ciliopatias}
**Genes clave:** AHI1, CPLANE1, CC2D2A, RPGRIP1L, CEP290, KIF7, INPP5E, MKS1…

**Concepto:** Síndrome de Joubert y espectro relacionado. Sello: molar tooth sign en RMN + hipotonía + oculomotricidad anormal.

**Flujo:**
1. Verificar "molar tooth sign" en corte axial de mesencéfalo-puente → hallazgo patognomónico.
2. Evaluar riñón (nefronoptisis), retina (distrofia), hígado (fibrosis hepática congénita) según gen específico.
3. CEP290: formas graves + amaurosis de Leber. Terapia génica intravítrea en ensayos.
4. KIF7 (acrocallosal): combinación con malformaciones de cuerpo calloso y polidactilia.

---

## 3. Alertas Terapéuticas Urgentes {#alertas}

El sistema NeuropedGx Hub genera **flags críticos automáticos** para las siguientes situaciones:

| Gen | Alerta | Acción |
|---|---|---|
| POLG | ⛔ VALPROATO CONTRAINDICADO | Retirar VPA inmediatamente; riesgo de fallo hepático fulminante |
| SCN1A (Dravet) | ⛔ Bloqueantes de Na+ empeoran la epilepsia | Evitar carbamazepina, fenitoína, lamotrigina, rufinamida |
| ALDH7A1 / PNPO | 🟡 Epilepsia vitamino-dependiente | Ensayo terapéutico con piridoxina/PLP antes de resultado genético |
| SLC2A1 (GLUT1) | 🟡 Dieta cetogénica muy efectiva | Inicio precoz de dieta cetogénica |
| SLC19A3 | 🟡 Biotina + tiamina responsivo | Iniciar biotina 5-10 mg/kg/día + tiamina empírica |
| GCH1 (DRD) | 🟡 L-DOPA response dramático | Ensayo diagnóstico-terapéutico con levodopa |
| CLN2 (Batten) | 🟢 Terapia enzimática disponible | Cerliponase alfa (Brineura) aprobada |
| DDC | 🟢 Terapia génica aprobada | Upstaza (eladocagene exuparvovec) |
| PIK3CA / MTOR | 🟡 Mosaicismo somático — WES sangre puede ser negativo | Solicitar secuenciación de tejido cerebral profunda |
| OTC | ⛔ Hiperamonemia aguda | Protocolo de emergencia: stop proteínas, glucosa IV, carnitina, benzoato/fenilbutirato |

---

## 4. Interpretación de Flags del Sistema {#flags}

| Flag | Significado | Acción sugerida |
|---|---|---|
| `GoF` | Ganancia de función | Pensar en bloqueantes del canal/vía |
| `LoF` | Pérdida de función | Terapias de restauración, evitar inhibidores |
| `dual_GoF_LoF` | Mismo gen puede actuar por GoF o LoF | El fenotipo/posición determina el mecanismo real |
| `dominant_negative` | La proteína mutante inhibe la normal | Fenotipos más graves que haploinsuficiencia pura |
| `hotspot_match` | La variante coincide con hotspot documentado | Alta probabilidad de patogenicidad; revisar PMID |
| `mosaicism_risk` | Gen asociado a mosaicismo somático | Solicitar secuenciación tisular si WES negativo |
| `X-linked` | Gen ligado al X | Diferente expresividad en ♀ portadoras |
| `de_novo_expected` | La variante se espera de novo | Verificar parentesco con estudios en trío |
| `acmg_PS1` | Hotspot = mismo aminoácido documentado patogénico | Criterio ACMG PS1 aplicable |
| `acmg_PM1` | Variante en dominio funcional crítico sin polimorfismos | Criterio ACMG PM1 aplicable |

---

## 5. Integración con el Stack Genómico {#integracion}

### Flujo típico de caso clínico

```
1. Paciente con epilepsia refractaria neonatal
         │
         ▼
2. WES/WGS → VCF filtrado (genes de interés)
         │
         ▼
3. REEV (http://localhost:8200)
   • Anotar variante candidata
   • Ver frecuencia gnomAD, ClinVar, ACMG auto
         │
         ▼
4. NeuropedGx Hub (http://localhost:8405)
   • Buscar gen → ver grupo de enfermedad, notas clínicas
   • Clasificar variante → obtener flags de mecanismo + guía ACMG gene-específica
   • Seguir link → REEV (clasificación completa) + Protein Viewer (localización 3D)
         │
         ▼
5. Protein Viewer (http://localhost:8404)
   • Ver estructura AlphaFold del canal/proteína
   • Localizar dominio donde cae la variante
   • Comparar con variantes conocidas
         │
         ▼
6. Informe final del genetista
   • Integrar todos los datos
   • Clasificación ACMG definitiva (P/LP/VUS/LB/B)
   • Implicaciones terapéuticas y de manejo
```

### API endpoints principales

```bash
# Obtener información de un gen
curl http://localhost:8405/api/genes/SCN1A

# Listar genes de un grupo
curl http://localhost:8405/api/groups/channelopathy

# Clasificar variante
curl -X POST http://localhost:8405/api/variant/classify \
  -H "Content-Type: application/json" \
  -d '{
    "gene": "SCN1A",
    "genome_build": "GRCh38",
    "hgvs_p": "p.Arg1648His",
    "transcript": "NM_006514.4"
  }'

# Estadísticas del panel
curl http://localhost:8405/api/stats
```

---

## 6. Limitaciones y Caveats {#limitaciones}

1. **No es un clasificador final.** Los flags y criterios ACMG son orientativos. La clasificación definitiva corresponde al genetista con REEV/auto-ACMG.

2. **Panel curado, no exhaustivo.** El panel cubre los genes de mayor relevancia neuropediátrica. Genes ultrararos (<5 casos publicados) pueden no estar incluidos.

3. **Datos de hotspots.** Los hotspots incluidos tienen respaldo de literatura, pero nuevas publicaciones pueden cambiar la interpretación. Verificar siempre ClinVar y literature reciente.

4. **Mosaicismo.** El sistema alerta sobre riesgo de mosaicismo somático pero no puede detectarlo. Requiere análisis de tejido específico.

5. **VUS (variantes de significado incierto).** El sistema no puede resolver VUS. Para VUS en genes críticos: estudios funcionales, co-segregación familiar, bases de datos de variantes somáticas.

6. **Actualizaciones del panel.** El YAML gene_panel.yml debe revisarse periódicamente. Nuevas publicaciones, cambios en ClinGen, nuevos genes → actualizar el panel y reiniciar el servicio.

7. **mtDNA no incluido.** Las variantes en ADN mitocondrial (ND genes, CYB, ATPase) no están en el panel. Usar herramientas específicas (Mitomap, HaploGrep).

---

*Panel generado por NeuropedGx Hub · Laboratorio de Neuropediatría*  
*Para reportar errores o solicitar adición de genes: actualizar gene_panel.yml y abrir issue en el repositorio.*
