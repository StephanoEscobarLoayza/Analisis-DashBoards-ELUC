# Dashboard Electro Ucayali S.A. ⚡

Dashboard ejecutivo de análisis energético para Electro Ucayali S.A., desarrollado con Streamlit y conectado a Supabase como backend de datos.

## Módulos

| Módulo | Descripción |
|--------|-------------|
| ⚡ Consumo | Análisis de consumo energético por período y zona |
| 🗺️ Geografía | Distribución territorial del consumo |
| 💰 Tarifas | Estructura tarifaria y precio implícito por segmento |
| 👥 Clientes | Cartera de titulares, antigüedad y estado |
| 📈 Eficiencia | Indicadores operacionales por distrito |
| 🔮 Proyección | Regresión lineal y proyección a 6 meses |

## Tecnologías

- **Frontend:** [Streamlit](https://streamlit.io/)
- **Base de datos:** [Supabase](https://supabase.com/) (PostgreSQL)
- **Gráficos:** Plotly
- **Reportes PDF:** ReportLab + pypdf

## Configuración local

### 1. Clonar el repositorio

```bash
git clone https://github.com/StephanoEscobarLoayza/Analisis-DashBoards-ELUC.git
cd Analisis-DashBoards-ELUC
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar credenciales

Crear el archivo `.streamlit/secrets.toml` (nunca subir a Git):

```toml
SUPABASE_URL = "https://<tu-proyecto>.supabase.co"
SUPABASE_KEY = "<tu-clave-anon>"
```

### 4. Ejecutar

```bash
streamlit run main.py
```

## Deploy en Streamlit Cloud

1. Conectar el repositorio en [share.streamlit.io](https://share.streamlit.io/)
2. Archivo principal: `main.py`
3. En **Settings → Secrets**, agregar:

```toml
SUPABASE_URL = "https://<tu-proyecto>.supabase.co"
SUPABASE_KEY = "<tu-clave-anon>"
```

Los cambios futuros se despliegan automáticamente al hacer `git push` a la rama principal.

## Seguridad

- Las credenciales de Supabase se leen desde `st.secrets` o variables de entorno, nunca hardcodeadas.
- Se recomienda usar la clave `anon` de Supabase con políticas RLS de solo `SELECT`.
