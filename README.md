# Herramienta de Conciliación Bancaria

Esta es una aplicación Next.js y FastAPI para conciliar transacciones bancarias y contables.

## Requisitos Previos

- Node.js (versión 18 o superior recomendada)
- npm (generalmente viene con Node.js)
- Python (versión 3.8 o superior recomendada)
- pip (generalmente viene con Python)
- `uvicorn` y `fastapi` para el backend (se instalan con los requisitos)

## Instalación

1.  **Clonar el Repositorio (si aplica):**
    ```bash
    git clone <url-del-repositorio>
    cd <nombre-del-directorio>
    ```

2.  **Instalar Dependencias del Frontend (Next.js):**
    Navega a la raíz del proyecto (donde está `package.json`) y ejecuta:
    ```bash
    npm install
    ```

3.  **Instalar Dependencias del Backend (FastAPI):**
    Navega al directorio `backend` y crea un entorno virtual (recomendado):
    ```bash
    cd backend
    python -m venv venv
    ```
    Activa el entorno virtual:
    -   En Windows: `.\venv\Scripts\activate`
    -   En macOS/Linux: `source venv/bin/activate`

    Instala los requisitos de Python:
    ```bash
    pip install -r requirements.txt
    ```
    Regresa al directorio raíz del proyecto:
    ```bash
    cd ..
    ```

## Ejecución de la Aplicación

Necesitas ejecutar tanto el frontend (Next.js) como el backend (FastAPI) simultáneamente.

Abre dos terminales separadas en el directorio raíz del proyecto.

**Terminal 1: Ejecutar el Backend (FastAPI)**

Asegúrate de estar en el directorio raíz y que el entorno virtual del backend esté activado si lo creaste. Luego ejecuta:

```bash
npm run dev:backend
# O directamente con uvicorn (desde la raíz):
# uvicorn backend.main:app --reload --port 8000
```

El backend estará disponible en `http://localhost:8000`.

**Terminal 2: Ejecutar el Frontend (Next.js)**

En la segunda terminal (en el directorio raíz), ejecuta:

```bash
npm run dev:next
```

La aplicación frontend estará disponible en `http://localhost:9002`.

**Alternativa: Ejecutar Ambos con un Solo Comando**

Puedes usar el script `dev` que ejecuta ambos en paralelo:

```bash
npm run dev
```

Esto ejecutará ambos servidores (backend en el puerto 8000 y frontend en el 9002) al mismo tiempo.

## Uso

Abre tu navegador y ve a `http://localhost:9002` para usar la herramienta de conciliación.

## Scripts Disponibles

-   `npm run dev`: Inicia ambos, frontend y backend, en modo de desarrollo.
-   `npm run dev:next`: Inicia solo el frontend Next.js en modo de desarrollo (`localhost:9002`).
-   `npm run dev:backend`: Inicia solo el backend FastAPI en modo de desarrollo (`localhost:8000`).
-   `npm run build`: Compila la aplicación Next.js para producción.
-   `npm run start`: Inicia ambos, frontend y backend, en modo de producción (requiere `npm run build` primero).
-   `npm run start:next`: Inicia solo el frontend Next.js en modo de producción (`localhost:9002`).
-   `npm run start:backend`: Inicia solo el backend FastAPI en modo de producción (`localhost:8000`).
-   `npm run lint`: Ejecuta el linter de Next.js.
-   `npm run typecheck`: Ejecuta la comprobación de tipos de TypeScript.
