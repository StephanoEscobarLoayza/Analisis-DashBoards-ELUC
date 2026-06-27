# ⚡ Dashboard Electro Ucayali S.A.

Panel de control ejecutivo para el análisis energético de la concesión de Electro Ucayali S.A. — empresa distribuidora de energía eléctrica en la región Ucayali, Perú.

Construido con **Python + Streamlit**, conectado en tiempo real a una base de datos en la nube.

---

## ¿Qué hace este dashboard?

Transforma datos operativos de consumo, facturación y cartera de clientes en indicadores claros para la toma de decisiones gerenciales. Incluye seis módulos de análisis:

- **⚡ Consumo** — evolución mensual del consumo energético y facturación
- **🗺️ Geografía** — distribución territorial por provincia y distrito
- **💰 Tarifas** — estructura tarifaria y precio implícito por segmento
- **👥 Clientes** — cartera de titulares, antigüedad y estado de la cuenta
- **📈 Eficiencia** — indicadores operacionales y rentabilidad por zona
- **🔮 Proyección** — tendencia y proyección de demanda a 6 meses

Cada módulo genera automáticamente conclusiones ejecutivas y permite exportar un **reporte en PDF** personalizado según los filtros activos.

---

## Stack tecnológico

| Capa | Tecnología |
|------|------------|
| Frontend | Streamlit |
| Base de datos | Supabase (PostgreSQL) |
| Visualizaciones | Plotly |
| Reportes PDF | ReportLab + pypdf |
| Lenguaje | Python 3.11+ |

---

## Instalación

```bash
git clone https://github.com/StephanoEscobarLoayza/Analisis-DashBoards-ELUC.git
cd Analisis-DashBoards-ELUC
pip install -r requirements.txt
```

Crear `.streamlit/secrets.toml` con las credenciales de Supabase y ejecutar:

```bash
streamlit run main.py
```
