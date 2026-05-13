# EMPA según Manual REM 2025-2026

## Fuente

**Manual REM 2025-2026, Serie A**  
**REM A02: Examen de Medicina Preventiva en mayores de 15 años**

Documento fuente:  
https://repositoriodeis.minsal.cl/ContenidoSitioWeb2020/REM/2025/SERIE/Manual%20Series%20REM%202025%20-2026%20SERIE%20A%20-BS-BM-%20DV1.2.pdf

---

## Texto literal del Manual REM 2025-2026

### REM A02: Examen de Medicina Preventiva en mayores de 15 años

> El Examen de Medicina Preventiva (EMP), corresponde al examen de medicina preventiva que se realiza desde los 15 años y hasta los 64 años incluidos.

> El EMPAM corresponde al examen preventivo realizado a personas desde los 65 años en adelante.

---

## Sección A: EMP realizado por profesional

> Corresponde a la aplicación de acciones de salud garantizadas en el Sistema Público, de monitoreo y evaluación de la salud a lo largo del ciclo vital, que se realizan de forma anual.

> Se registrarán los EMP, según rango etario y sexo de los pacientes atendidos, desagregados por profesional que efectúa la actividad.

> El registro corresponde a EMP efectuado, es decir, que en el examen se haya evaluado al paciente, clasificado por estado nutricional, aplicado escalas y solicitando exámenes, independiente de los resultados de éstos.

> Posteriormente cuando el paciente vuelve para control de exámenes indicados previamente en EMP, esta actividad se registra como Consulta profesional Médico o no Médico sección A y B del REM A04.

---

## Qué se puede afirmar literalmente desde el manual

Según el Manual REM 2025-2026:

- El REM A02 registra el **Examen de Medicina Preventiva en mayores de 15 años**.
- El **EMP** corresponde al examen preventivo realizado desde los **15 años hasta los 64 años incluidos**.
- El **EMPAM** corresponde al examen preventivo realizado desde los **65 años en adelante**.
- La **Sección A** corresponde al **EMP realizado por profesional**.
- Los EMP se registran según:
  - rango etario,
  - sexo,
  - profesional que efectúa la actividad.
- El registro corresponde a un **EMP efectuado**.
- Para considerarse efectuado, el examen debe incluir evaluación del paciente, clasificación por estado nutricional, aplicación de escalas y solicitud de exámenes, independiente de los resultados.
- El control posterior de exámenes indicados en el EMP no se registra nuevamente como EMP, sino como consulta profesional en REM A04.

---

## Qué NO aparece definido literalmente en el manual

El Manual REM 2025-2026, en la sección revisada del REM A02:

- No define una fórmula de **tasa EMPA**.
- No define una fórmula de **cobertura EMPA**.
- No define un denominador para EMPA.
- No indica restar embarazadas.
- No indica restar población bajo control PSCV.
- No desarrolla una fórmula IAAPS.
- No usa explícitamente la expresión “calcular tasa EMPA”.

---

## Fórmula oficial IAAPS 2025

La fórmula oficial de cobertura EMPA no está en el Manual REM A02. Para IAAPS 2025 se encuentra en el Diario Oficial, Núm. 44.132, jueves 24 de abril de 2025, CVE 2636798, decreto del Ministerio de Salud / Subsecretaría de Redes Asistenciales “Determina aporte estatal a las municipalidades que indica, para sus entidades administradoras de salud municipal, año 2025”.

En el indicador N° 6, “Cobertura Examen de Medicina Preventiva realizado a hombres y mujeres de 20 años y más”, la parte EMPA adulto corresponde a:

- **6.1.A mujeres 20 a 64 años**: EMP realizados a mujeres de 20 a 64 años dividido por población de mujeres de 20 a 64 años inscrita validada, menos población embarazada de 20 a 54 años en control.
- **6.1.B hombres 20 a 64 años**: EMP realizados a hombres de 20 a 64 años dividido por población de hombres de 20 a 64 años inscrita validada.

Formulación operativa:

```text
Cobertura EMPA mujeres 20-64 =
EMP mujeres 20-64 /
(mujeres 20-64 inscritas validadas - gestantes 20-54 en control) * 100

Cobertura EMPA hombres 20-64 =
EMP hombres 20-64 /
hombres 20-64 inscritos validados * 100
```

La población embarazada 20-54 en control se obtiene desde REM Serie P, Sección B: Gestantes en Control con evaluación Riesgo Biopsicosocial, variable “Total de Gestantes en Control”.

---

## Interpretación operativa, no literal

Si se desea construir un cálculo operativo de EMPA usando los datos del REM A02, se debe tener presente que esto ya es una **interpretación de uso de los datos**, no una instrucción literal del manual.

Una forma operativa sería usar como numerador:

```text
EMP realizados en personas adultas, según los tramos de edad definidos para el análisis.
```

Para EMPA adulto, habitualmente se utilizan los tramos de **20 a 64 años**, pero esa definición específica de edad, si corresponde a IAAPS u otro indicador, debe verificarse en la fuente normativa del indicador respectivo.

En este proyecto, la salida IAAPS 2025 usa:

- Fórmula: Diario Oficial / Decreto IAAPS 2025 / indicador 6.1.A y 6.1.B.
- Numerador 2025: REM A02, Sección A, EMP realizado por profesional, 20 a 64 años por sexo.
- Numerador histórico 2023-2024: REM A02, Sección B como proxy, porque la Sección A de esos años no contiene desglose etario.
- Denominador: población inscrita validada FONASA 20 a 64 años por sexo.
- Ajuste mujeres: gestantes 20 a 54 años en control desde REM Serie P, Sección B.

---

## Resumen

Basándose solo en el Manual REM 2025-2026:

```text
El manual permite identificar y registrar EMP realizados,
pero no entrega una fórmula completa para calcular tasa o cobertura EMPA.
```

El dato REM directamente utilizable es:

```text
EMP realizados en REM A02, Sección A: EMP realizado por profesional,
según rango etario, sexo y profesional que efectúa la actividad.
```
