# backend/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Tuple, Literal
import uuid
import pandas as pd
# import tempfile # Ya no es necesario escribir a disco
# import os # Ya no es necesario interactuar con el SO para archivos temp
import traceback # Para imprimir errores completos
import io # Para manejar el archivo en memoria
from starlette.responses import StreamingResponse # Para enviar el archivo
from datetime import date as py_date, datetime # Para nombre de archivo único y tipos

# --- Importar Modelos Pydantic ---
try:
    from .models import (
        Transaction, MatchedPair, InitialDataResponse,
        ManualReconcileRequest, ManualReconcileResponse,
        ManyToOneReconcileRequest, ManyToOneReconcileResponse,
        OneToManyReconcileRequest, OneToManyReconcileResponse,
        AutoReconcileResponse, UploadResponse, ClearDataResponse,
        AvailableFormat # Nuevo modelo para formatos
    )
    print("INFO: Modelos Pydantic cargados desde models.py.")
except ImportError:
    print("ERROR FATAL: No se pudo importar desde models.py. Asegúrate que el archivo existe y no tiene errores.")
    # Definiciones dummy rápidas (no funcionales para la API real)
    class BaseModel: pass
    Transaction = MatchedPair = InitialDataResponse = ManualReconcileRequest = ManualReconcileResponse = ManyToOneReconcileRequest = ManyToOneReconcileResponse = OneToManyReconcileRequest = OneToManyReconcileResponse = AutoReconcileResponse = UploadResponse = ClearDataResponse = AvailableFormat = BaseModel

# --- Importar funciones de procesamiento y configuraciones ---
try:
    from .processing import (
        process_uploaded_file,
        reconcile_data,
        FILE_FORMAT_CONFIGS, # Importar las configuraciones
        # Importar las constantes con los nombres estándar INTERNOS
        FECHA_CONCILIACION,
        MOVIMIENTO_CONCILIACION, # Para banco
        AUXILIAR_DEBITO,      # Para contabilidad
        AUXILIAR_CREDITO,     # Para contabilidad
        DESCRIPCION_EXTRACTO, # Para banco
        DESCRIPCION_AUXILIAR, # Para contabilidad
        DOCUMENTO_AUXILIAR    # Para contabilidad
    )
    print("INFO: Módulo 'processing.py' y configuraciones cargados correctamente.")
    # Crear lista de formatos disponibles para el frontend
    AVAILABLE_FORMATS_LIST: List[AvailableFormat] = [
        AvailableFormat(id=fmt_id, description=f"{config.get('type', 'unknown').capitalize()} - {fmt_id.replace('_', ' ').title()}")
        for fmt_id, config in FILE_FORMAT_CONFIGS.items()
    ]
    print(f"INFO: Formatos disponibles: {[f.id for f in AVAILABLE_FORMATS_LIST]}")
except ImportError as e:
    print(f"ERROR FATAL: No se pudo importar 'processing.py', sus constantes o configuraciones. Detalle: {e}")
    # Definir funciones y constantes dummy si falla la importación
    def process_uploaded_file(content, fmt): print("ERROR: process_uploaded_file no cargado"); return None
    def reconcile_data(df1, df2, include_ids=True): print("ERROR: reconcile_data no cargado"); return None
    FILE_FORMAT_CONFIGS = {}
    AVAILABLE_FORMATS_LIST = []
    FECHA_CONCILIACION = 'fecha_norm'; MOVIMIENTO_CONCILIACION = 'movimiento'
    AUXILIAR_DEBITO = 'debito'; AUXILIAR_CREDITO = 'credito'
    DESCRIPCION_EXTRACTO = 'descripcion_extracto'; DESCRIPCION_AUXILIAR = 'descripcion_auxiliar'
    DOCUMENTO_AUXILIAR = 'documento_auxiliar'


# --- Configuración de la App FastAPI ---
app = FastAPI(
    title="Herramienta de Conciliación Bancaria - Backend vConfigurable",
    description="API con procesamiento configurable, conciliación manual flexible y descarga de reporte.",
    version="1.1.0",
)

# --- Configuración CORS ---
origins = [
    "http://localhost:9002",
    "http://127.0.0.1:9002",
    "http://localhost:9003", # Puerto actual del frontend
    "http://127.0.0.1:9003",
    # Añadir URLs de producción aquí si se despliega
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Almacenamiento Global en Memoria ---
db: Dict[str, List] = {
    "bank_transactions": [],
    "accounting_transactions": [],
    "matched_pairs": []
}

# --- Funciones Helper ---

def find_transaction(tx_id: str, tx_type: Literal['bank', 'accounting']) -> Optional[Transaction]:
    """Busca una transacción por ID en la lista correspondiente."""
    list_key = f"{tx_type}_transactions"
    return next((tx for tx in db.get(list_key, []) if tx.id == tx_id), None)

def dataframe_to_transactions(df: pd.DataFrame, tx_type: Literal['bank', 'accounting']) -> List[Transaction]:
    """Convierte un DataFrame procesado (con columnas estándar) a una lista de objetos Transaction."""
    transactions = []
    if df is None or df.empty:
        print(f"DEBUG dataframe_to_transactions: DataFrame de entrada vacío para tipo '{tx_type}'.")
        return transactions

    required_cols = [FECHA_CONCILIACION]
    desc_col = None
    amount = 0.0 # Inicializar amount aquí

    # Determinar columnas necesarias según el tipo
    if tx_type == 'bank':
        required_cols.extend([MOVIMIENTO_CONCILIACION, DESCRIPCION_EXTRACTO])
        desc_col = DESCRIPCION_EXTRACTO
    elif tx_type == 'accounting':
        required_cols.extend([AUXILIAR_DEBITO, AUXILIAR_CREDITO, DESCRIPCION_AUXILIAR, DOCUMENTO_AUXILIAR])
        desc_col = DESCRIPCION_AUXILIAR
    else:
        print(f"ERROR dataframe_to_transactions: Tipo de transacción desconocido '{tx_type}'.")
        return transactions # O lanzar excepción

    # Verificar columnas presentes
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"ERROR dataframe_to_transactions: Faltan columnas estándar requeridas para '{tx_type}': {missing_cols}. Columnas presentes: {list(df.columns)}")
        # Podríamos lanzar una excepción o devolver lista vacía
        raise ValueError(f"Columnas estándar faltantes en DataFrame procesado '{tx_type}': {missing_cols}")

    print(f"DEBUG dataframe_to_transactions: Procesando {len(df)} filas para tipo '{tx_type}'.")
    # Iterar sobre filas del DataFrame
    for index, row in df.iterrows():
        tx_id = f"{tx_type[0]}-{uuid.uuid4().hex[:8]}" # Generar ID único interno
        date_val = row.get(FECHA_CONCILIACION)
        processed_date: Optional[py_date] = None

        # Procesar Fecha
        if pd.notna(date_val):
            if isinstance(date_val, datetime): processed_date = date_val.date()
            elif isinstance(date_val, py_date): processed_date = date_val
            else:
                # Intentar convertir si es string u otro tipo (aunque format_date_robust debería haberlo hecho)
                try: processed_date = pd.to_datetime(date_val).date()
                except Exception as date_err: print(f"WARN dataframe_to_transactions: No se pudo convertir fecha '{date_val}' (ID: {tx_id}, Fila: {index}): {date_err}")
        # Si processed_date sigue siendo None, la transacción podría ser inválida o la fecha no es crucial para este punto

        # Procesar Descripción
        description = str(row.get(desc_col, '')).strip() if desc_col else ''

        # Procesar Monto (diferente para banco y contabilidad)
        amount = 0.0 # Reiniciar para cada fila
        if tx_type == 'bank':
            amount = round(float(row.get(MOVIMIENTO_CONCILIACION, 0.0)), 2)
        elif tx_type == 'accounting':
            debito = float(row.get(AUXILIAR_DEBITO, 0.0))
            credito = float(row.get(AUXILIAR_CREDITO, 0.0))
            amount = round(debito - credito, 2) # Monto neto: Débito (+) / Crédito (-)

        # Añadir la transacción a la lista
        transactions.append(Transaction(
            id=tx_id,
            date=processed_date, # Puede ser None si la fecha falló o no era crucial
            description=description,
            amount=amount,
            type=tx_type
        ))

    print(f"DEBUG dataframe_to_transactions: {len(transactions)} transacciones creadas para tipo '{tx_type}'.")
    return transactions


def transactions_to_dataframe(transactions: List[Transaction], tx_type: Literal['bank', 'accounting']) -> pd.DataFrame:
    """Convierte una lista de objetos Transaction de vuelta a DataFrame con columnas estándar (para reconcile_data)."""
    if not transactions:
        # Devolver DataFrame vacío con las columnas estándar esperadas por reconcile_data
        cols = []
        if tx_type == 'bank': cols = MIN_COLS_BANK[:] + ['tx_id_ref']
        elif tx_type == 'accounting': cols = MIN_COLS_ACCOUNTING[:] + ['tx_id_ref']
        print(f"DEBUG transactions_to_dataframe: Lista de entrada vacía para '{tx_type}'. Devolviendo DF vacío.")
        return pd.DataFrame(columns=cols)

    data = []
    print(f"DEBUG transactions_to_dataframe: Convirtiendo {len(transactions)} transacciones tipo '{tx_type}' a DataFrame.")
    for tx in transactions:
        # Crear registro base
        record = {
            'tx_id_ref': tx.id, # Referencia al ID interno de la transacción
            FECHA_CONCILIACION: tx.date # Usar la fecha (puede ser None)
        }
        # Añadir campos específicos del tipo
        if tx_type == 'bank':
            record[MOVIMIENTO_CONCILIACION] = tx.amount
            record[DESCRIPCION_EXTRACTO] = tx.description
        elif tx_type == 'accounting':
            # Reconstruir débito/crédito desde el monto neto
            record[AUXILIAR_DEBITO] = tx.amount if tx.amount >= 0 else 0.0
            record[AUXILIAR_CREDITO] = -tx.amount if tx.amount < 0 else 0.0
            record[DESCRIPCION_AUXILIAR] = tx.description
            # Añadir documento (si lo tuviéramos almacenado en Transaction, o un placeholder)
            record[DOCUMENTO_AUXILIAR] = f"DOC_{tx.id}" # Placeholder si no se guarda el original
        else:
            print(f"WARN transactions_to_dataframe: Tipo desconocido '{tx_type}' para tx ID {tx.id}")
            continue # Saltar esta transacción

        data.append(record)

    # Crear DataFrame
    df = pd.DataFrame(data)

    # Intentar asegurar tipos de datos correctos (crucial para reconcile_data)
    try:
        # Convertir fecha a datetime (reconcile_data lo espera así)
        df[FECHA_CONCILIACION] = pd.to_datetime(df[FECHA_CONCILIACION], errors='coerce')

        # Convertir montos a numérico
        if tx_type == 'bank':
            df[MOVIMIENTO_CONCILIACION] = pd.to_numeric(df[MOVIMIENTO_CONCILIACION], errors='coerce').fillna(0.0)
        elif tx_type == 'accounting':
            df[AUXILIAR_DEBITO] = pd.to_numeric(df[AUXILIAR_DEBITO], errors='coerce').fillna(0.0)
            df[AUXILIAR_CREDITO] = pd.to_numeric(df[AUXILIAR_CREDITO], errors='coerce').fillna(0.0)

        # Asegurar columnas de texto
        for col in [DESCRIPCION_EXTRACTO, DESCRIPCION_AUXILIAR, DOCUMENTO_AUXILIAR]:
            if col in df.columns:
                 df[col] = df[col].astype(str).fillna('')
            elif tx_type == 'accounting' and col == DOCUMENTO_AUXILIAR:
                 df[DOCUMENTO_AUXILIAR] = '' # Asegurar que existe para contabilidad

        print(f"DEBUG transactions_to_dataframe: DataFrame creado para '{tx_type}'. Columnas: {list(df.columns)}")
        # print(df.head()) # Descomentar para ver las primeras filas

    except Exception as e:
        print(f"ERROR transactions_to_dataframe: Fallo al convertir tipos para '{tx_type}': {e}")
        traceback.print_exc()
        # Podríamos devolver el DF tal cual o lanzar excepción
        raise ValueError(f"Error convirtiendo tipos para reconcile_data ({tx_type}): {e}")

    return df


# --- Endpoints ---

@app.get("/", summary="Endpoint de Bienvenida", include_in_schema=False)
async def read_root():
    return {"message": "Bienvenido al API de Conciliación Bancaria vConfigurable"}

@app.get("/api/formats", response_model=List[AvailableFormat], summary="Obtener Formatos Soportados")
async def get_available_formats():
    """Devuelve la lista de identificadores de formatos de archivo soportados por el backend."""
    print(f"INFO: Devolviendo {len(AVAILABLE_FORMATS_LIST)} formatos disponibles.")
    return AVAILABLE_FORMATS_LIST

@app.post("/api/transactions/upload", response_model=UploadResponse, summary="Subir y Procesar Archivo")
async def upload_and_process_file(
    format_id: str = Query(..., description="Identificador del formato del archivo (ej: 'bancolombia_csv_9col', 'siesa_xlsx'). Ver /api/formats."),
    file: UploadFile = File(...)
):
    """
    Endpoint genérico para subir archivos.
    Requiere especificar el `format_id` como query parameter.
    """
    print(f"\n--- Recibida solicitud de carga para formato: {format_id} ---")
    if format_id not in FILE_FORMAT_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Formato '{format_id}' no soportado o inválido. Formatos disponibles: {[f.id for f in AVAILABLE_FORMATS_LIST]}")

    config = FILE_FORMAT_CONFIGS[format_id]
    tx_type = config.get("type") # 'bank' o 'accounting'

    if tx_type not in ['bank', 'accounting']:
        raise HTTPException(status_code=500, detail=f"Configuración interna inválida para formato '{format_id}': tipo desconocido '{tx_type}'.")

    try:
        # Leer contenido del archivo en memoria
        content = await file.read()
        print(f"INFO: Archivo '{file.filename}' leído en memoria ({len(content)} bytes).")

        # Procesar usando la función genérica y el format_id
        df_processed = process_uploaded_file(content, format_id)

        if df_processed is None:
            # process_uploaded_file ya imprimió el error específico
            raise HTTPException(status_code=400, detail=f"Error al procesar archivo '{file.filename}' con formato '{format_id}'. Verifique el archivo y la configuración del formato. Consulte los logs del servidor para más detalles.")

        # Convertir DataFrame procesado a lista de objetos Transaction
        new_transactions = []
        if not df_processed.empty:
            try:
                new_transactions = dataframe_to_transactions(df_processed, tx_type)
            except ValueError as val_err: # Capturar error de columnas faltantes de dataframe_to_transactions
                 print(f"ERROR post-procesamiento: {val_err}")
                 raise HTTPException(status_code=500, detail=f"Error interno al convertir datos procesados para '{format_id}': {val_err}")

        # Actualizar "base de datos" en memoria
        db_key = f"{tx_type}_transactions"
        db[db_key] = new_transactions
        db["matched_pairs"] = [] # Reiniciar conciliaciones existentes al cargar nuevo archivo
        print(f"INFO: Datos para '{tx_type}' actualizados. {len(new_transactions)} transacciones cargadas.")
        print("INFO: Conciliaciones previas reiniciadas.")

        # Preparar respuesta
        message = f"Archivo '{file.filename}' (formato '{format_id}') procesado como '{tx_type}'. {len(new_transactions)} transacciones cargadas."
        if df_processed is not None and df_processed.empty and not new_transactions:
            message = f"Archivo '{file.filename}' (formato '{format_id}') procesado como '{tx_type}', pero no se encontraron transacciones válidas."

        print(f"INFO: Enviando respuesta para {file.filename}.")
        return UploadResponse(
            filename=file.filename,
            message=message,
            transaction_count=len(new_transactions),
            transactions=new_transactions # Enviar las transacciones procesadas al frontend
        )

    except HTTPException as h:
        # Re-lanzar HTTPException para que FastAPI la maneje
        print(f"ERROR (HTTPException) en upload: {h.detail}")
        raise h
    except ValueError as v:
        # Errores de validación durante la lectura o procesamiento
        print(f"ERROR (ValueError) en upload {file.filename}: {v}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error de validación/formato: {v}")
    except Exception as e:
        # Otros errores inesperados
        print(f"ERROR FATAL en upload {file.filename}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno del servidor al procesar el archivo: {e}")
    finally:
        # Cerrar el archivo (aunque FastAPI podría manejarlo)
        await file.close()
        print(f"--- Fin solicitud de carga para {file.filename} ---")


@app.get("/api/transactions/initial", response_model=InitialDataResponse, summary="Obtener Datos No Conciliados")
async def get_initial_transactions():
    """Devuelve las transacciones bancarias y contables que aún no han sido conciliadas."""
    print("--- Solicitud GET /api/transactions/initial ---")
    try:
        # Obtener IDs de las transacciones ya conciliadas
        matched_pairs_list = db.get("matched_pairs", [])
        matched_bank_ids = {p.bankTransactionId for p in matched_pairs_list}
        matched_acc_ids = {p.accountingTransactionId for p in matched_pairs_list}
        print(f"DEBUG: IDs conciliados - Banco: {len(matched_bank_ids)}, Contable: {len(matched_acc_ids)}")

        # Filtrar las listas globales para obtener solo las no conciliadas
        all_bank_txs = db.get("bank_transactions", [])
        all_acc_txs = db.get("accounting_transactions", [])

        unmatched_bank = [tx for tx in all_bank_txs if tx.id not in matched_bank_ids]
        unmatched_acc = [tx for tx in all_acc_txs if tx.id not in matched_acc_ids]

        print(f"INFO: Devolviendo {len(unmatched_bank)} bancarias y {len(unmatched_acc)} contables no conciliadas.")
        print(f"INFO: Total Banco: {len(all_bank_txs)}, Total Contable: {len(all_acc_txs)}, Total Pares: {len(matched_pairs_list)}")

        return InitialDataResponse(
            bank_transactions=unmatched_bank,
            accounting_transactions=unmatched_acc
        )
    except Exception as e:
        print(f"ERROR en get_initial_transactions: {e}")
        traceback.print_exc()
        # Devolver respuesta vacía o lanzar excepción HTTP
        # return InitialDataResponse(bank_transactions=[], accounting_transactions=[])
        raise HTTPException(status_code=500, detail="Error interno al obtener transacciones iniciales.")


@app.post("/api/transactions/reconcile/manual", response_model=ManualReconcileResponse, summary="Conciliar Manualmente (1 a 1)")
async def reconcile_manual(request: ManualReconcileRequest = Body(...)):
    """Realiza una conciliación manual entre una transacción bancaria y una contable."""
    print("--- Solicitud POST /api/transactions/reconcile/manual ---")
    bank_tx_id = request.bank_transaction_id
    acc_tx_id = request.accounting_transaction_id
    print(f"DEBUG: Intentando conciliar Banco ID: {bank_tx_id} con Contable ID: {acc_tx_id}")

    # Validaciones exhaustivas
    matched_pairs_list = db.get("matched_pairs", [])
    if any(p.bankTransactionId == bank_tx_id for p in matched_pairs_list):
        raise HTTPException(status_code=400, detail=f"Transacción bancaria {bank_tx_id} ya está conciliada.")
    if any(p.accountingTransactionId == acc_tx_id for p in matched_pairs_list):
        raise HTTPException(status_code=400, detail=f"Transacción contable {acc_tx_id} ya está conciliada.")

    bank_tx = find_transaction(bank_tx_id, 'bank')
    acc_tx = find_transaction(acc_tx_id, 'accounting')

    if not bank_tx:
        raise HTTPException(status_code=404, detail=f"Transacción bancaria {bank_tx_id} no encontrada o ya conciliada.")
    if not acc_tx:
        raise HTTPException(status_code=404, detail=f"Transacción contable {acc_tx_id} no encontrada o ya conciliada.")

    # Verificar diferencia de montos (opcional, solo informativo)
    tolerance = 0.01 # Pequeña tolerancia para errores de redondeo
    amount_match = abs(bank_tx.amount - acc_tx.amount) < tolerance
    warning = ""
    if not amount_match:
        warning = f"Advertencia: Los montos difieren significativamente (Banco: {bank_tx.amount:.2f} vs Contable: {acc_tx.amount:.2f}). "
        print(f"WARN: {warning}")

    # Crear y añadir el nuevo par conciliado
    new_match = MatchedPair(bankTransactionId=bank_tx_id, accountingTransactionId=acc_tx_id)
    db["matched_pairs"].append(new_match)

    message = f"{warning}Conciliación manual (1-1) exitosa: Banco {bank_tx_id} con Contable {acc_tx_id}."
    print(f"INFO: {message}")

    return ManualReconcileResponse(success=True, message=message, matched_pair=new_match)


@app.post("/api/transactions/reconcile/manual/many_to_one", response_model=ManyToOneReconcileResponse, summary="Conciliar Manualmente (1 Banco a Múltiples Contables)")
async def reconcile_manual_many_to_one(request: ManyToOneReconcileRequest = Body(...)):
    """Concilia una transacción bancaria con múltiples transacciones contables."""
    print("--- Solicitud POST /reconcile/manual/many_to_one ---")
    bank_tx_id = request.bank_transaction_id
    acc_tx_ids = request.accounting_transaction_ids
    print(f"DEBUG: Intentando conciliar Banco ID: {bank_tx_id} con Contables IDs: {acc_tx_ids}")

    if not acc_tx_ids:
        raise HTTPException(status_code=400, detail="Se requiere al menos un ID de transacción contable.")

    # Validar transacción bancaria
    bank_tx = find_transaction(bank_tx_id, 'bank')
    if not bank_tx:
        raise HTTPException(status_code=404, detail=f"Transacción bancaria {bank_tx_id} no encontrada.")

    matched_pairs_list = db.get("matched_pairs", [])
    if any(p.bankTransactionId == bank_tx_id for p in matched_pairs_list):
        # Permitir que un banco se concilie con múltiples grupos? O debe ser único?
        # Por ahora, asumimos que si ya está en *algún* par, no puede estar en otro M-1.
        # Si se permite conciliación parcial, esta lógica debe cambiar.
        raise HTTPException(status_code=400, detail=f"Transacción bancaria {bank_tx_id} ya está involucrada en una conciliación.")

    # Validar transacciones contables y calcular suma
    accounting_txs: List[Transaction] = []
    total_accounting_amount = 0.0
    processed_acc_ids = set() # Para evitar duplicados en la solicitud

    for acc_id in acc_tx_ids:
        if acc_id in processed_acc_ids:
            print(f"WARN: ID contable duplicado en solicitud: {acc_id}. Se ignora.")
            continue
        processed_acc_ids.add(acc_id)

        acc_tx = find_transaction(acc_id, 'accounting')
        if not acc_tx:
            raise HTTPException(status_code=404, detail=f"Transacción contable {acc_id} no encontrada.")
        if any(p.accountingTransactionId == acc_id for p in matched_pairs_list):
            raise HTTPException(status_code=400, detail=f"Transacción contable {acc_id} ya está conciliada.")

        accounting_txs.append(acc_tx)
        total_accounting_amount += acc_tx.amount

    total_accounting_amount = round(total_accounting_amount, 2)

    # Verificar diferencia de montos
    tolerance = 0.01
    amount_match = abs(bank_tx.amount - total_accounting_amount) < tolerance
    warning = ""
    if not amount_match:
        warning = f"Advertencia: La suma contable ({total_accounting_amount:.2f}) difiere del monto bancario ({bank_tx.amount:.2f}). "
        print(f"WARN: {warning}")

    # Crear y añadir los nuevos pares conciliados (uno por cada transacción contable)
    newly_created_pairs: List[MatchedPair] = []
    for acc_tx in accounting_txs:
        new_match = MatchedPair(bankTransactionId=bank_tx_id, accountingTransactionId=acc_tx.id)
        db["matched_pairs"].append(new_match)
        newly_created_pairs.append(new_match)

    message = f"{warning}Conciliación (1 Banco a {len(newly_created_pairs)} Contables) exitosa para Banco {bank_tx_id}."
    print(f"INFO: {message}. {len(newly_created_pairs)} nuevos pares añadidos.")

    return ManyToOneReconcileResponse(success=True, message=message, matched_pairs_created=newly_created_pairs)


@app.post("/api/transactions/reconcile/manual/one_to_many", response_model=OneToManyReconcileResponse, summary="Conciliar Manualmente (Múltiples Bancos a 1 Contable)")
async def reconcile_manual_one_to_many(request: OneToManyReconcileRequest = Body(...)):
    """Concilia múltiples transacciones bancarias con una única transacción contable."""
    print("--- Solicitud POST /reconcile/manual/one_to_many ---")
    acc_tx_id = request.accounting_transaction_id
    bank_tx_ids = request.bank_transaction_ids
    print(f"DEBUG: Intentando conciliar Contable ID: {acc_tx_id} con Bancos IDs: {bank_tx_ids}")

    if not bank_tx_ids:
        raise HTTPException(status_code=400, detail="Se requiere al menos un ID de transacción bancaria.")

    # Validar transacción contable
    acc_tx = find_transaction(acc_tx_id, 'accounting')
    if not acc_tx:
        raise HTTPException(status_code=404, detail=f"Transacción contable {acc_tx_id} no encontrada.")

    matched_pairs_list = db.get("matched_pairs", [])
    if any(p.accountingTransactionId == acc_tx_id for p in matched_pairs_list):
        # Asumimos que una transacción contable solo puede estar en una conciliación 1-M
        raise HTTPException(status_code=400, detail=f"Transacción contable {acc_tx_id} ya está involucrada en una conciliación.")

    # Validar transacciones bancarias y calcular suma
    bank_txs: List[Transaction] = []
    total_bank_amount = 0.0
    processed_bank_ids = set() # Para evitar duplicados

    for bank_id in bank_tx_ids:
        if bank_id in processed_bank_ids:
            print(f"WARN: ID bancario duplicado en solicitud: {bank_id}. Se ignora.")
            continue
        processed_bank_ids.add(bank_id)

        bank_tx = find_transaction(bank_id, 'bank')
        if not bank_tx:
            raise HTTPException(status_code=404, detail=f"Transacción bancaria {bank_id} no encontrada.")
        if any(p.bankTransactionId == bank_id for p in matched_pairs_list):
            raise HTTPException(status_code=400, detail=f"Transacción bancaria {bank_id} ya está conciliada.")

        bank_txs.append(bank_tx)
        total_bank_amount += bank_tx.amount

    total_bank_amount = round(total_bank_amount, 2)

    # Verificar diferencia de montos
    tolerance = 0.01
    amount_match = abs(total_bank_amount - acc_tx.amount) < tolerance
    warning = ""
    if not amount_match:
        warning = f"Advertencia: La suma bancaria ({total_bank_amount:.2f}) difiere del monto contable ({acc_tx.amount:.2f}). "
        print(f"WARN: {warning}")

    # Crear y añadir los nuevos pares conciliados (uno por cada transacción bancaria)
    newly_created_pairs: List[MatchedPair] = []
    for bank_tx in bank_txs:
        new_match = MatchedPair(bankTransactionId=bank_tx.id, accountingTransactionId=acc_tx_id)
        db["matched_pairs"].append(new_match)
        newly_created_pairs.append(new_match)

    message = f"{warning}Conciliación ({len(newly_created_pairs)} Bancos a 1 Contable) exitosa para Contable {acc_tx_id}."
    print(f"INFO: {message}. {len(newly_created_pairs)} nuevos pares añadidos.")

    return OneToManyReconcileResponse(success=True, message=message, matched_pairs_created=newly_created_pairs)


@app.post("/api/transactions/reconcile/auto", response_model=AutoReconcileResponse, summary="Ejecutar Conciliación Automática")
async def reconcile_auto():
    """Ejecuta el proceso de conciliación automática sobre las transacciones pendientes."""
    print("--- Solicitud POST /api/transactions/reconcile/auto ---")
    print("INFO: Iniciando conciliación automática...")

    # 1. Obtener transacciones pendientes
    matched_pairs_list = db.get("matched_pairs", [])
    matched_bank_ids = {p.bankTransactionId for p in matched_pairs_list}
    matched_acc_ids = {p.accountingTransactionId for p in matched_pairs_list}

    unmatched_bank_txs = [tx for tx in db.get("bank_transactions", []) if tx.id not in matched_bank_ids]
    unmatched_acc_txs = [tx for tx in db.get("accounting_transactions", []) if tx.id not in matched_acc_ids]

    num_unmatched_bank = len(unmatched_bank_txs)
    num_unmatched_acc = len(unmatched_acc_txs)
    print(f"INFO: Candidatos para conciliación automática: {num_unmatched_bank} Bancarias, {num_unmatched_acc} Contables.")

    if num_unmatched_bank == 0 or num_unmatched_acc == 0:
        message = "No hay suficientes transacciones pendientes en ambos lados para realizar la conciliación automática."
        print(f"INFO: {message}")
        return AutoReconcileResponse(success=True, message=message, matched_pairs=[])

    # 2. Convertir transacciones pendientes a DataFrames con IDs de referencia
    try:
        df_ledger = transactions_to_dataframe(unmatched_acc_txs, 'accounting')
        df_statement = transactions_to_dataframe(unmatched_bank_txs, 'bank')
        print(f"DEBUG: DataFrames para reconcile_data creados. Ledger: {df_ledger.shape}, Statement: {df_statement.shape}")
        # print("Ledger Dtypes:\n", df_ledger.dtypes) # Descomentar para depurar tipos
        # print("Statement Dtypes:\n", df_statement.dtypes)
    except ValueError as df_conv_err:
         print(f"ERROR preparando DataFrames para conciliación: {df_conv_err}")
         traceback.print_exc()
         raise HTTPException(status_code=500, detail=f"Error interno preparando datos para conciliación: {df_conv_err}")
    except Exception as e:
         print(f"ERROR inesperado preparando DataFrames para conciliación: {e}")
         traceback.print_exc()
         raise HTTPException(status_code=500, detail="Error interno inesperado preparando datos.")

    if df_ledger.empty or df_statement.empty:
        message = "Uno de los conjuntos de datos pendientes (banco o contable) está vacío después de la preparación. No se puede conciliar."
        print(f"WARN: {message}")
        return AutoReconcileResponse(success=True, message=message, matched_pairs=[])

    # 3. Ejecutar la función de conciliación del módulo processing
    reconciliation_result = None
    try:
        # Llamar a reconcile_data (asegúrate que esté importado)
        reconciliation_result = reconcile_data(df_ledger, df_statement, include_ids=True)
    except ValueError as rec_val_err: # Capturar errores de validación de columnas de reconcile_data
         print(f"ERROR durante reconcile_data (Validación): {rec_val_err}")
         traceback.print_exc()
         raise HTTPException(status_code=500, detail=f"Error interno durante conciliación (Validación): {rec_val_err}")
    except Exception as e:
        print(f"ERROR durante la ejecución de reconcile_data: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno durante el proceso de conciliación: {e}")

    if reconciliation_result is None:
        # reconcile_data ya debería haber impreso un error si devolvió None
        raise HTTPException(status_code=500, detail="La función de conciliación automática falló y no devolvió resultados.")

    # 4. Procesar los resultados de la conciliación
    # reconcile_data devuelve: _, df_conciliados, _ (ignoramos el merge completo y los pendientes aquí)
    _, df_conciliados, _ = reconciliation_result
    num_potential_matches = len(df_conciliados)
    print(f"INFO: reconcile_data encontró {num_potential_matches} coincidencias potenciales.")

    newly_matched_pairs: List[MatchedPair] = []
    if not df_conciliados.empty:
        # Verificar que las columnas de ID renombradas existan
        if 'tx_id_ref_x' not in df_conciliados.columns or 'tx_id_ref_y' not in df_conciliados.columns:
            print("ERROR: El resultado de reconcile_data no contiene las columnas de ID esperadas ('tx_id_ref_x', 'tx_id_ref_y').")
            raise HTTPException(status_code=500, detail="Error interno: Resultado de conciliación incompleto.")

        # Añadir los nuevos pares a la lista global 'db["matched_pairs"]'
        # Usar los sets actuales para asegurar que no añadimos duplicados si se corre auto varias veces
        current_bank_matched = {p.bankTransactionId for p in db["matched_pairs"]}
        current_acc_matched = {p.accountingTransactionId for p in db["matched_pairs"]}

        for index, row in df_conciliados.iterrows():
            # Recordar: _x es libro (accounting), _y es extracto (bank)
            acc_tx_id = str(row['tx_id_ref_x'])
            bank_tx_id = str(row['tx_id_ref_y'])

            # Comprobar si alguno de los IDs ya fue conciliado (manualmente o en una ejecución anterior)
            if acc_tx_id not in current_acc_matched and bank_tx_id not in current_bank_matched:
                 # Si ambos son nuevos, crear el par y añadirlo
                 new_match = MatchedPair(bankTransactionId=bank_tx_id, accountingTransactionId=acc_tx_id)
                 db["matched_pairs"].append(new_match)
                 newly_matched_pairs.append(new_match)
                 # Actualizar los sets para el resto del bucle
                 current_bank_matched.add(bank_tx_id)
                 current_acc_matched.add(acc_tx_id)
                 print(f"DEBUG: Nuevo par automático añadido: B:{bank_tx_id} <-> A:{acc_tx_id}")
            # else: # Descomentar si quieres loguear por qué se omitió un par potencial
            #      reason = []
            #      if acc_tx_id in current_acc_matched: reason.append(f"Contable {acc_tx_id} ya conciliado")
            #      if bank_tx_id in current_bank_matched: reason.append(f"Banco {bank_tx_id} ya conciliado")
            #      print(f"DEBUG: Par potencial omitido (Fila {index}): {'; '.join(reason)}")


    count_added = len(newly_matched_pairs)
    message = f"Conciliación automática completada. Se añadieron {count_added} nuevas conciliaciones."
    if count_added == 0 and num_potential_matches > 0:
        message = f"Conciliación automática completada. Se encontraron {num_potential_matches} coincidencias potenciales, pero ya estaban conciliadas previamente o involucraban transacciones ya conciliadas."
    elif count_added == 0 and num_potential_matches == 0:
         message = "Conciliación automática completada. No se encontraron nuevas coincidencias."

    print(f"INFO: {message}")

    # Devolver solo los *nuevos* pares encontrados en esta ejecución
    return AutoReconcileResponse(success=True, message=message, matched_pairs=newly_matched_pairs)


@app.get("/api/transactions/matched", response_model=List[MatchedPair], summary="Obtener Conciliaciones Globales")
async def get_matched_pairs():
    """Devuelve todos los pares de transacciones que han sido conciliados (manual o automáticamente)."""
    print("--- Solicitud GET /api/transactions/matched ---")
    matched_pairs_list = db.get("matched_pairs", [])
    print(f"INFO: Devolviendo {len(matched_pairs_list)} pares conciliados globales.")
    return matched_pairs_list

# --- Endpoint de Descarga ---
@app.get("/api/reconciliation/download",
         response_class=StreamingResponse,
         summary="Descargar Estado Actual de Conciliación en Excel")
async def download_reconciliation():
    """Genera y devuelve un archivo Excel con el estado actual de la conciliación."""
    print("--- Solicitud GET /api/reconciliation/download ---")
    print("INFO: Solicitud para descargar estado de conciliación.")

    # Obtener todos los datos actuales
    current_bank_txs = db.get("bank_transactions", [])
    current_acc_txs = db.get("accounting_transactions", [])
    current_matched_pairs = db.get("matched_pairs", [])

    if not current_bank_txs and not current_acc_txs:
        print("WARN: No hay transacciones cargadas para generar reporte.")
        raise HTTPException(status_code=404, detail="No hay transacciones cargadas para generar el reporte.")

    # Identificar IDs conciliados
    matched_bank_ids = {p.bankTransactionId for p in current_matched_pairs}
    matched_acc_ids = {p.accountingTransactionId for p in current_matched_pairs}
    print(f"DEBUG Descarga: {len(matched_bank_ids)} IDs banco conciliados, {len(matched_acc_ids)} IDs contables conciliados.")

    # Separar transacciones pendientes
    pending_bank = [tx for tx in current_bank_txs if tx.id not in matched_bank_ids]
    pending_acc = [tx for tx in current_acc_txs if tx.id not in matched_acc_ids]
    print(f"DEBUG Descarga: {len(pending_bank)} bancos pendientes, {len(pending_acc)} contables pendientes.")

    # Preparar datos para la hoja de Conciliados
    conciliados_data = []
    for pair in current_matched_pairs:
        bank_tx = find_transaction(pair.bankTransactionId, 'bank')
        acc_tx = find_transaction(pair.accountingTransactionId, 'accounting')
        if bank_tx and acc_tx:
            conciliados_data.append({
                'ID Banco': bank_tx.id,
                'Fecha Banco': bank_tx.date,
                'Descripción Banco': bank_tx.description,
                'Monto Banco': bank_tx.amount,
                'ID Contable': acc_tx.id,
                'Fecha Contable': acc_tx.date,
                'Descripción Contable': acc_tx.description,
                'Monto Contable': acc_tx.amount,
                # 'Diferencia Monto': round(bank_tx.amount - acc_tx.amount, 2) # Opcional
            })
        elif bank_tx:
             print(f"WARN Descarga: Transacción contable {pair.accountingTransactionId} del par conciliado no encontrada.")
        elif acc_tx:
             print(f"WARN Descarga: Transacción bancaria {pair.bankTransactionId} del par conciliado no encontrada.")
        else:
             print(f"WARN Descarga: Ninguna transacción encontrada para el par B:{pair.bankTransactionId}, A:{pair.accountingTransactionId}")

    print(f"DEBUG Descarga: {len(conciliados_data)} filas para hoja 'Conciliados'.")


    # Preparar datos para hojas de Pendientes
    # Usar nombres de columna estándar internos
    pendientes_banco_data = [{
        'ID Transacción': tx.id,
        FECHA_CONCILIACION: tx.date,
        DESCRIPCION_EXTRACTO: tx.description,
        MOVIMIENTO_CONCILIACION: tx.amount
    } for tx in pending_bank]

    pendientes_contable_data = [{
        'ID Transacción': tx.id,
        FECHA_CONCILIACION: tx.date,
        DESCRIPCION_AUXILIAR: tx.description,
        # Reconstruir débito/crédito
        AUXILIAR_DEBITO: tx.amount if tx.amount >= 0 else 0.0,
        AUXILIAR_CREDITO: -tx.amount if tx.amount < 0 else 0.0,
        # DOCUMENTO_AUXILIAR: tx.document_ref # Si tuviéramos esta info
    } for tx in pending_acc]

    print(f"DEBUG Descarga: {len(pendientes_banco_data)} filas para 'Pendientes Banco'.")
    print(f"DEBUG Descarga: {len(pendientes_contable_data)} filas para 'Pendientes Contable'.")


    # Crear DataFrames
    df_conciliados = pd.DataFrame(conciliados_data)
    df_pendientes_banco = pd.DataFrame(pendientes_banco_data)
    df_pendientes_contable = pd.DataFrame(pendientes_contable_data)

    # Crear archivo Excel en memoria
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_conciliados.to_excel(writer, sheet_name='Conciliados', index=False)
            df_pendientes_banco.to_excel(writer, sheet_name='Pendientes Banco', index=False)
            df_pendientes_contable.to_excel(writer, sheet_name='Pendientes Contable', index=False)
        excel_data = output.getvalue()
        print("INFO: Archivo Excel generado en memoria.")
    except Exception as excel_err:
        print(f"ERROR generando archivo Excel: {excel_err}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error interno al generar el archivo Excel.")

    # Preparar respuesta para descarga
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"reporte_conciliacion_{timestamp}.xlsx"
    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
    media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    print(f"INFO: Enviando archivo '{filename}' para descarga.")
    return StreamingResponse(io.BytesIO(excel_data), media_type=media_type, headers=headers)


@app.get("/health", summary="Chequeo de Salud", include_in_schema=False)
async def health_check():
    """Endpoint simple para verificar que el servicio está activo."""
    return {"status": "ok"}

@app.post("/api/admin/clear_data", response_model=ClearDataResponse, summary="Limpiar Datos (ADMIN)", include_in_schema=False)
async def clear_all_data(confirm: bool = Body(..., embed=True)):
    """Elimina todas las transacciones y conciliaciones en memoria (requiere confirmación)."""
    if not confirm:
        raise HTTPException(status_code=400, detail="La operación requiere confirmación explícita. Envíe {'confirm': true} en el cuerpo de la solicitud.")

    db["bank_transactions"] = []
    db["accounting_transactions"] = []
    db["matched_pairs"] = []

    message = "Todos los datos de transacciones y conciliaciones en memoria han sido eliminados."
    print(f"INFO (Admin): {message}")
    return ClearDataResponse(message=message)

# --- Uvicorn Runner (opcional, útil para debug directo) ---
# if __name__ == "__main__":
#     import uvicorn
#     print("Ejecutando backend con Uvicorn (modo debug)...")
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```