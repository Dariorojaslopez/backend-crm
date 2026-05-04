"""
Punto de entrada de la API CRM.

Render (y otros hosts) ejecutan el servidor con:
    uvicorn app.main:app --host 0.0.0.0 --port 10000

La variable `app` debe existir en este módulo para que uvicorn la resuelva.
"""

from fastapi import FastAPI

# Instancia principal de FastAPI: aquí se registran rutas, middlewares, etc.
app = FastAPI(
    title="Backend CRM",
    description="API básica sin base de datos, lista para desplegar en Render.",
    version="0.1.0",
)


@app.get("/")
def read_root():
    """
    Ruta raíz: comprobación rápida de que el servicio responde.
    """
    return {"message": "API funcionando 🔥"}


@app.get("/health")
def health_check():
    """
    Health check para balanceadores y monitoreo (Render, Kubernetes, etc.).
    """
    return {"status": "ok"}
