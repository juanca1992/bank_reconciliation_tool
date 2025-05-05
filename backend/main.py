from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Tuple
import uuid
import pandas as pd
import tempfile # Para manejar archivos temporales
import os
from typing import Literal

# Importa modelos desde models.py (asegúrate que existan)
# Si models.py está en el mismo directorio:
# from models import (
# Si está en un subdirectorio 'app':
# from .models import (
# Asumiendo que están definidos como en tu ejemplo original:
from pydantic import BaseModel, Field
from datetime import date as py_date # Usa un alias para evitar conflicto

class Transaction(BaseModel):
    id: str
    date: Optional[py_date] = None # Usa el alias py_date
    description: Optional[str] = None
    amount: float
    type: Literal['bank', 'accounting']

class MatchedPair(BaseModel):
    bankTransactionId: str
    accountingTransactionId: str
    # Puedes añadir más detalles si reconcile_data los devuelve
    # reconciliation_date: Optional[py_date] = None
    # movement_amount: Optional[float] = None

class InitialDataResponse(BaseModel):
    bank_transactions: List[Transaction] = []
    accounting_transactions: List[Transaction] = []

class ManualReconcileRequest(BaseModel):
    bank_transaction_id: str
    accounting_transaction_id: str

class ManualReconcileResponse(BaseModel):
    success: bool
    message: str
    matched_pair: Optional[MatchedPair] = None

# Quitamos AutoReconcileRequest ya que no necesita input del frontend
# class AutoReconcileRequest(BaseModel):
#     bank_transactions: List[Transaction]
#     accounting_transactions: List[Transaction]

class AutoReconcileResponse(BaseModel):
    success: bool
    message: str
    matched_pairs: List[MatchedPair] = [] # Devuelve los *nuevos* pares

class UploadResponse(BaseModel):
    filename: str
    message: str
    transaction_count: int
    transactions: List[Transaction] # <--- AÑADE ESTA LÍNEA DE NUEVO

# main.py (cerca de donde defines otros modelos como ManualReconcileRequest)

class ManyToOneReconcileRequest(BaseModel):
    bank_transaction_id: str
    accounting_transaction_ids: List[str]

class ManyToOneReconcileResponse(BaseModel):
    success: bool
    message: str
    matched_pairs_created: List[MatchedPair] = []

# --- Importa funciones del script de procesamiento ---
try:
    # Asumiendo que processing.py está en el mismo directorio
    from .processing import (
        transform_siesa_auxiliary,
        transform_bancolombia_statement,
        # transform_bancolombia_movements, # Descomenta si también lo usas
        reconcile_data,
        # Constantes REALES necesarias de processing.py
        FECHA_CONCILIACION,
        MOVIMIENTO_CONCILIACION,
        AUXILIAR_DEBITO,
        AUXILIAR_CREDITO
        # --- LÍNEAS CON STRINGS ELIMINADAS ---
    )
    print("INFO: Módulo 'processing.py' cargado correctamente.")

except ImportError as e:
    # El bloque 'except' se mantiene igual que antes,
    # definiendo las funciones y constantes dummy como fallback.
    print(f"ERROR FATAL: No se pudo importar 'processing.py' o sus constantes. Asegúrate de que el archivo existe, no tiene errores y define las constantes necesarias (FECHA_CONCILIACION, MOVIMIENTO_CONCILIACION, AUXILIAR_DEBITO, AUXILIAR_CREDITO). Detalle: {e}")
    # Salir o manejar el error como prefieras si el procesamiento es esencial
    # exit()
    # Definir funciones y constantes dummy para que FastAPI al menos inicie:
    def transform_siesa_auxiliary(fp): print("ERROR: transform_siesa_auxiliary no cargado"); return None
    def transform_bancolombia_statement(fp): print("ERROR: transform_bancolombia_statement no cargado"); return None
    def reconcile_data(df1, df2): print("ERROR: reconcile_data no cargado"); return None
    FECHA_CONCILIACION = 'fecha_norm' # Fallback
    MOVIMIENTO_CONCILIACION = 'movimiento' # Fallback
    AUXILIAR_DEBITO = 'debito' # Fallback
    AUXILIAR_CREDITO = 'credito' # Fallback
    # (Ya no necesitamos definir los nombres de columna aquí porque las funciones helper los usan directamente)

# --- El resto del archivo main.py sigue igual ---
# ... (definición de FastAPI, modelos, endpoints, etc.) ...

app = FastAPI(
    title="Herramienta de Conciliación Bancaria - Backend v2",
    description="API que usa lógica de procesamiento real para la conciliación.",
    version="0.2.0",
)

# --- CORS Configuration ---
origins = [
    "http://localhost:9002",
    "http://127.0.0.1:9002",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Almacenamiento Global en Memoria ---
# Ahora almacenará objetos Transaction procesados desde los archivos
# y los pares conciliados. Se inicializa vacío.
db: Dict[str, List] = {
    "bank_transactions": [],        # Lista de objetos Transaction bancarios
    "accounting_transactions": [],  # Lista de objetos Transaction contables
    "matched_pairs": []             # Lista de objetos MatchedPair
}

# --- Funciones Helper ---
def find_transaction(tx_id: str, tx_type: Literal['bank', 'accounting']) -> Optional[Transaction]:
    """Encuentra una transacción en la 'db' global por ID y tipo."""
    list_key = f"{tx_type}_transactions" # <--- CORREGIDO
    return next((tx for tx in db.get(list_key, []) if tx.id == tx_id), None) # Añadí .get() para seguridad

def dataframe_to_transactions(df: pd.DataFrame, tx_type: Literal['bank', 'accounting']) -> List[Transaction]:
    """Convierte un DataFrame procesado (SIESA o Bancolombia) a una lista de objetos Transaction."""
    transactions = []
    if df is None or df.empty:
        return transactions

    # Asegurar que las columnas esperadas existen
    required_cols = [FECHA_CONCILIACION]
    desc_col = None
    if tx_type == 'bank':
        required_cols.extend([MOVIMIENTO_CONCILIACION, 'descripcion_extracto'])
        desc_col = 'descripcion_extracto'
    else: # accounting
        required_cols.extend([AUXILIAR_DEBITO, AUXILIAR_CREDITO, 'descripcion_auxiliar'])
        desc_col = 'descripcion_auxiliar'

    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"ERROR: DataFrame de tipo '{tx_type}' no contiene las columnas requeridas: {missing_cols}")
        # Podrías lanzar una excepción aquí o devolver lista vacía
        raise ValueError(f"Columnas faltantes en DataFrame '{tx_type}': {missing_cols}")
        # return transactions

    for _, row in df.iterrows():
        tx_id = f"{tx_type[:1]}-{uuid.uuid4().hex[:8]}" # Genera un ID único corto
        date_val = row[FECHA_CONCILIACION]
        # Asegurarse que la fecha es un objeto date de Python, no Timestamp de Pandas
        processed_date = None
        if pd.notna(date_val):
             if isinstance(date_val, pd.Timestamp):
                 processed_date = date_val.date()
             elif isinstance(date_val, py_date):
                 processed_date = date_val
             else:
                 # Intenta convertir si es string u otro formato (puede fallar)
                 try:
                     processed_date = pd.to_datetime(date_val).date()
                 except Exception:
                     print(f"ADVERTENCIA: No se pudo convertir fecha {date_val} para ID {tx_id}")
                     processed_date = None # O manejar como error

        description = row.get(desc_col, None) # Usa .get para manejar si falta la columna (aunque ya validamos)

        if tx_type == 'bank':
            amount = row.get(MOVIMIENTO_CONCILIACION, 0.0)
        else: # accounting
            debit = row.get(AUXILIAR_DEBITO, 0.0)
            credit = row.get(AUXILIAR_CREDITO, 0.0)
            amount = debit - credit # Calcula el movimiento neto

        transactions.append(
            Transaction(
                id=tx_id,
                date=processed_date,
                description=str(description) if pd.notna(description) else None,
                amount=float(amount) if pd.notna(amount) else 0.0,
                type=tx_type
            )
        )
    return transactions

def transactions_to_dataframe(transactions: List[Transaction], tx_type: Literal['bank', 'accounting']) -> pd.DataFrame:
    """Convierte una lista de Transaction de vuelta a un DataFrame para reconcile_data."""
    if not transactions:
        # Devuelve un DataFrame vacío con las columnas esperadas por reconcile_data
        if tx_type == 'bank':
            return pd.DataFrame(columns=[FECHA_CONCILIACION, MOVIMIENTO_CONCILIACION, 'descripcion_extracto', 'tx_id_ref'])
        else: # accounting
            return pd.DataFrame(columns=[FECHA_CONCILIACION, AUXILIAR_DEBITO, AUXILIAR_CREDITO, 'descripcion_auxiliar', 'documento_auxiliar', 'tx_id_ref'])

    data = []
    for tx in transactions:
        record = {
            'tx_id_ref': tx.id, # Guardamos el ID original para referencia
            FECHA_CONCILIACION: tx.date,
            # Nota: La descripción original podría haberse perdido un poco, usamos la del objeto Transaction
            # No tenemos el 'documento_auxiliar' original aquí a menos que lo guardemos en Transaction
        }
        if tx_type == 'bank':
            record[MOVIMIENTO_CONCILIACION] = tx.amount
            record['descripcion_extracto'] = tx.description
        else: # accounting
            # Asumimos que amount > 0 es débito, amount < 0 es crédito
            record[AUXILIAR_DEBITO] = tx.amount if tx.amount > 0 else 0.0
            record[AUXILIAR_CREDITO] = -tx.amount if tx.amount < 0 else 0.0
            record['descripcion_auxiliar'] = tx.description
            # Necesitaríamos añadir 'documento_auxiliar' al modelo Transaction si es crucial para reconcile_data
            record['documento_auxiliar'] = f"DOC_{tx.id}" # Placeholder

        data.append(record)

    df = pd.DataFrame(data)
    # Asegurar tipos correctos para reconcile_data si es necesario
    df[FECHA_CONCILIACION] = pd.to_datetime(df[FECHA_CONCILIACION]) # reconcile_data puede necesitar datetime
    if tx_type == 'bank':
        df[MOVIMIENTO_CONCILIACION] = df[MOVIMIENTO_CONCILIACION].astype(float)
    else:
        df[AUXILIAR_DEBITO] = df[AUXILIAR_DEBITO].astype(float)
        df[AUXILIAR_CREDITO] = df[AUXILIAR_CREDITO].astype(float)

    return df

# --- Endpoints ---

@app.get("/", summary="Endpoint de Bienvenida")
async def read_root():
    return {"message": "Bienvenido al API de Conciliación Bancaria v2"}

@app.post("/api/transactions/upload/{tx_type}", response_model=UploadResponse, summary="Subir y Procesar Extracto")
async def upload_and_process_statement(tx_type: Literal['bank', 'accounting'], file: UploadFile = File(...)):
    """
    Recibe un archivo (Excel para contable, CSV para bancario), lo procesa
    usando la lógica de `processing.py`, y actualiza la base de datos en memoria.
    """
    if tx_type not in ['bank', 'accounting']:
        raise HTTPException(status_code=400, detail="Tipo de transacción inválido. Usar 'bank' o 'accounting'.")

    # Usar tempfile para guardar el archivo de forma segura
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        print(f"INFO: Archivo '{file.filename}' guardado temporalmente en '{tmp_file_path}'")

        # Llamar a la función de procesamiento adecuada
        df_processed = None
        if tx_type == 'bank':
            # Asumiendo que el extracto bancario siempre usa transform_bancolombia_statement
            # Si tienes lógica para detectar el tipo de archivo bancario, añádela aquí
            print("INFO: Procesando archivo como extracto bancario (Bancolombia Statement)...")
            df_processed = transform_bancolombia_statement(tmp_file_path)
        else: # accounting
            print("INFO: Procesando archivo como auxiliar contable (SIESA)...")
            df_processed = transform_siesa_auxiliary(tmp_file_path)

        # Limpiar archivo temporal
        os.remove(tmp_file_path)
        print(f"INFO: Archivo temporal '{tmp_file_path}' eliminado.")

        if df_processed is None:
            # La función de procesamiento ya debería haber impreso el error
            raise HTTPException(status_code=400, detail=f"Error al procesar el archivo '{file.filename}' con la lógica de '{tx_type}'. Revisa los logs del servidor.")
        if df_processed.empty:
             print(f"ADVERTENCIA: El procesamiento de '{file.filename}' resultó en 0 transacciones válidas.")
             # Decide si esto es un error o no
             # raise HTTPException(status_code=400, detail=f"El archivo '{file.filename}' no contiene transacciones válidas después del procesamiento.")


        # Convertir DataFrame a lista de Transaction
        try:
            new_transactions = dataframe_to_transactions(df_processed, tx_type)
        except ValueError as e:
             raise HTTPException(status_code=500, detail=f"Error interno al convertir DataFrame a Transaction: {e}")


        # Actualizar la base de datos global (REEMPLAZANDO los datos anteriores)
        db[f"{tx_type}_transactions"] = new_transactions
        # Si quisieras añadir en vez de reemplazar:
        # db[f"{tx_type}_transactions"].extend(new_transactions)
        # ¡Ojo! Si añades, necesitas una forma de evitar duplicados si se carga el mismo archivo.

        # Limpiar conciliaciones previas al cargar nuevos datos? Es una decisión de negocio.
        # db["matched_pairs"] = [] # Descomenta si cada carga debe reiniciar la conciliación

        print(f"INFO: {len(new_transactions)} transacciones de tipo '{tx_type}' procesadas y almacenadas desde '{file.filename}'.")

        return UploadResponse(
            filename=file.filename,
            message=f"Archivo '{tx_type}' procesado exitosamente.",
            transaction_count=len(new_transactions),
            transactions=new_transactions # <--- AÑADE ESTA LÍNEA DE NUEVO
        )

    except HTTPException as http_exc:
        # Re-lanzar excepciones HTTP que ya generamos
        raise http_exc
    except Exception as e:
        # Capturar cualquier otro error inesperado durante el proceso
        print(f"ERROR FATAL durante la carga y procesamiento de {file.filename}: {e}")
        # Asegurarse de limpiar el archivo temporal si aún existe
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            try:
                os.remove(tmp_file_path)
                print(f"INFO: Archivo temporal '{tmp_file_path}' eliminado después de error.")
            except OSError as ose:
                 print(f"ERROR: No se pudo eliminar el archivo temporal '{tmp_file_path}': {ose}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor al procesar el archivo: {e}")
    finally:
        # Asegurar que el objeto UploadFile se cierra
        await file.close()


@app.get("/api/transactions/initial", response_model=InitialDataResponse, summary="Obtener Datos No Conciliados")
async def get_initial_transactions():
    """
    Devuelve las transacciones bancarias y contables actualmente almacenadas
    que *no* están en la lista de `matched_pairs`.
    """
    matched_bank_ids = {p.bankTransactionId for p in db["matched_pairs"]}
    matched_acc_ids = {p.accountingTransactionId for p in db["matched_pairs"]}

    unmatched_bank = [tx for tx in db["bank_transactions"] if tx.id not in matched_bank_ids]
    unmatched_acc = [tx for tx in db["accounting_transactions"] if tx.id not in matched_acc_ids]

    print(f"INFO: Devolviendo {len(unmatched_bank)} transacciones bancarias y {len(unmatched_acc)} contables no conciliadas.")

    return InitialDataResponse(
        bank_transactions=unmatched_bank,
        accounting_transactions=unmatched_acc
    )

@app.post("/api/transactions/reconcile/manual", response_model=ManualReconcileResponse, summary="Conciliar Manualmente")
async def reconcile_manual(request: ManualReconcileRequest = Body(...)):
    """
    Marca un par específico de transacciones (bancaria y contable) como conciliadas.
    Usa los IDs generados durante la carga de archivos.
    """
    bank_tx_id = request.bank_transaction_id
    acc_tx_id = request.accounting_transaction_id

    # Verificar si ya están conciliadas globalmente
    if any(p.bankTransactionId == bank_tx_id and p.accountingTransactionId == acc_tx_id for p in db["matched_pairs"]):
         raise HTTPException(status_code=400, detail="Este par exacto ya está conciliado globalmente.")
    # Verificar si alguna ya participa en *otra* conciliación
    if any(p.bankTransactionId == bank_tx_id for p in db["matched_pairs"]):
        raise HTTPException(status_code=400, detail=f"La transacción bancaria {bank_tx_id} ya está conciliada con otra transacción.")
    if any(p.accountingTransactionId == acc_tx_id for p in db["matched_pairs"]):
        raise HTTPException(status_code=400, detail=f"La transacción contable {acc_tx_id} ya está conciliada con otra transacción.")


    # Encontrar las transacciones en nuestra 'db'
    bank_tx = find_transaction(bank_tx_id, 'bank')
    acc_tx = find_transaction(acc_tx_id, 'accounting')

    if not bank_tx:
        raise HTTPException(status_code=404, detail=f"No se encontró la transacción bancaria con ID {bank_tx_id}.")
    if not acc_tx:
        raise HTTPException(status_code=404, detail=f"No se encontró la transacción contable con ID {acc_tx_id}.")

    # Validaciones opcionales (ej. montos)
    amount_match = bank_tx.amount == acc_tx.amount
    warning = "" if amount_match else f"Advertencia: Los montos difieren ({bank_tx.amount:.2f} vs {acc_tx.amount:.2f}). "

    # Crear y almacenar el par conciliado
    new_match = MatchedPair(
        bankTransactionId=bank_tx_id,
        accountingTransactionId=acc_tx_id,
    )
    db["matched_pairs"].append(new_match)

    message = f"{warning}Conciliación manual exitosa: Banco ID {bank_tx_id} con Contabilidad ID {acc_tx_id}."
    print(f"INFO: {message}")

    return ManualReconcileResponse(success=True, message=message, matched_pair=new_match)

@app.post("/api/transactions/reconcile/auto", response_model=AutoReconcileResponse, summary="Ejecutar Conciliación Automática Real")
async def reconcile_auto():
    """
    Ejecuta la función `reconcile_data` de `processing.py` sobre las transacciones
    actualmente no conciliadas en la 'db'. Actualiza `matched_pairs`.
    """
    print("INFO: Iniciando proceso de conciliación automática real...")

    # 1. Obtener transacciones no conciliadas de la DB
    matched_bank_ids = {p.bankTransactionId for p in db["matched_pairs"]}
    matched_acc_ids = {p.accountingTransactionId for p in db["matched_pairs"]}

    unmatched_bank_txs = [tx for tx in db["bank_transactions"] if tx.id not in matched_bank_ids]
    unmatched_acc_txs = [tx for tx in db["accounting_transactions"] if tx.id not in matched_acc_ids]

    print(f"INFO: {len(unmatched_bank_txs)} bancarias y {len(unmatched_acc_txs)} contables candidatas para conciliación automática.")

    if not unmatched_bank_txs or not unmatched_acc_txs:
        message = "No hay suficientes transacciones bancarias y contables no conciliadas para intentar la conciliación automática."
        print(f"INFO: {message}")
        return AutoReconcileResponse(success=True, message=message, matched_pairs=[])

    # 2. Convertir listas de Transaction a DataFrames para reconcile_data
    try:
        df_ledger = transactions_to_dataframe(unmatched_acc_txs, 'accounting')
        df_statement = transactions_to_dataframe(unmatched_bank_txs, 'bank')
        print(f"INFO: DataFrames creados para reconcile_data. Ledger: {df_ledger.shape}, Statement: {df_statement.shape}")
        # print("Ledger DF Head:\n", df_ledger.head()) # Debug
        # print("Statement DF Head:\n", df_statement.head()) # Debug

    except Exception as e:
        print(f"ERROR: Fallo al convertir Transaction a DataFrame para reconcile_data: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno preparando datos para conciliación: {e}")

    # 3. Llamar a la función de conciliación real
    try:
        # Asegúrate que tu función reconcile_data maneja DataFrames vacíos si es posible
        reconciliation_result = reconcile_data(df_ledger, df_statement)
    except Exception as e:
        print(f"ERROR: La función reconcile_data falló: {e}")
        # Imprime más detalles si es posible
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error durante la ejecución de reconcile_data: {e}")

    if reconciliation_result is None:
        message = "La función de conciliación (reconcile_data) devolvió None. Ver logs para detalles."
        print(f"ERROR: {message}")
        # Podría ser un error dentro de reconcile_data que ya imprimió algo
        return AutoReconcileResponse(success=False, message=message, matched_pairs=[])
        # O lanzar un 500 si se considera un fallo crítico
        # raise HTTPException(status_code=500, detail=message)

    _, df_conciliados, _ = reconciliation_result # Solo necesitamos los conciliados

    print(f"INFO: reconcile_data completado. Encontró {len(df_conciliados)} pares potenciales basados en sus criterios.")
    # print("Conciliados DF Head:\n", df_conciliados.head()) # Debug


    # 4. Procesar los resultados y actualizar db['matched_pairs']
    newly_matched_pairs: List[MatchedPair] = []
    if not df_conciliados.empty:
        # Verificar que las columnas 'tx_id_ref' están presentes (deberían estar si se añadieron bien)
        if 'tx_id_ref_x' not in df_conciliados.columns or 'tx_id_ref_y' not in df_conciliados.columns:
             print("ERROR: El DataFrame de conciliados no contiene las columnas 'tx_id_ref_x' y 'tx_id_ref_y' necesarias para identificar los pares originales.")
             # Puedes intentar buscar por otros campos si tienes la certeza, pero es arriesgado
             raise HTTPException(status_code=500, detail="Error interno: Resultado de conciliación no contiene IDs de referencia.")

        for _, row in df_conciliados.iterrows():
            # Obtener los IDs originales que guardamos en los DataFrames de entrada
            # _x usualmente viene de la izquierda (ledger), _y de la derecha (statement) en el merge
            acc_tx_id = row['tx_id_ref_x']
            bank_tx_id = row['tx_id_ref_y']

            # Doble chequeo: asegurarse que estos IDs no están ya en db["matched_pairs"]
            # (Podría pasar si reconcile_data tiene lógica diferente o si se ejecuta dos veces)
            is_already_matched = any(
                p.accountingTransactionId == acc_tx_id and p.bankTransactionId == bank_tx_id
                for p in db["matched_pairs"]
            )

            if not is_already_matched:
                # Verificar si alguno ya está en otra pareja (importante)
                 is_acc_already_in_pair = any(p.accountingTransactionId == acc_tx_id for p in db["matched_pairs"])
                 is_bank_already_in_pair = any(p.bankTransactionId == bank_tx_id for p in db["matched_pairs"])

                 if not is_acc_already_in_pair and not is_bank_already_in_pair:
                     new_match = MatchedPair(
                         bankTransactionId=str(bank_tx_id),
                         accountingTransactionId=str(acc_tx_id)
                         # Podrías añadir más datos del DataFrame conciliado si quieres
                         # movement_amount=row.get(MOVIMIENTO_CONCILIACION, None)
                     )
                     newly_matched_pairs.append(new_match)
                     db["matched_pairs"].append(new_match) # Añadir al estado global
                 else:
                     print(f"ADVERTENCIA: El par ({acc_tx_id}, {bank_tx_id}) encontrado por reconcile_data no se añadirá porque uno de los IDs ya participa en otra conciliación global.")

            # else: # Descomenta si quieres loguear los que ya estaban
            #      print(f"INFO: Par ({acc_tx_id}, {bank_tx_id}) encontrado por reconcile_data ya estaba en matched_pairs globales.")


    count = len(newly_matched_pairs)
    message = f"Conciliación automática completada. Se encontraron y añadieron {count} nuevas coincidencias únicas."
    if count == 0 and not df_conciliados.empty:
         message = f"Conciliación automática completada. reconcile_data encontró {len(df_conciliados)} coincidencias, pero todas ya estaban registradas o involucraban IDs ya conciliados."
    elif count == 0 and df_conciliados.empty:
         message = "Conciliación automática completada. No se encontraron nuevas coincidencias con los criterios de reconcile_data."

    print(f"INFO: {message}")
    return AutoReconcileResponse(
        success=True,
        message=message,
        matched_pairs=newly_matched_pairs # Devolver solo los añadidos en *esta* ejecución
    )


@app.get("/api/transactions/matched", response_model=List[MatchedPair], summary="Obtener Todas las Conciliaciones Globales")
async def get_matched_pairs():
    """
    Devuelve la lista completa de pares que han sido marcados como conciliados
    globalmente (manual o automáticamente).
    """
    print(f"INFO: Devolviendo {len(db['matched_pairs'])} pares conciliados globales.")
    return db["matched_pairs"]

@app.get("/health", summary="Chequeo de Salud")
async def health_check():
    return {"status": "ok"}

# --- Opcional: Añadir endpoint para limpiar datos ---
@app.post("/api/admin/clear_data", summary="Limpiar Datos (¡Cuidado!)")
async def clear_all_data(confirm: bool = Body(..., embed=True)):
    """Endpoint administrativo para borrar todos los datos en memoria."""
    if not confirm:
        raise HTTPException(status_code=400, detail="Se requiere confirmación para limpiar datos.")
    
    db["bank_transactions"] = []
    db["accounting_transactions"] = []
    db["matched_pairs"] = []
    message = "Todos los datos en memoria (transacciones y conciliaciones) han sido eliminados."
    print(f"INFO: {message}")
    return {"message": message}

# --- Pega este bloque completo en tu main.py ---

@app.post("/api/transactions/reconcile/manual/many_to_one",
          response_model=ManyToOneReconcileResponse,
          summary="Conciliar Múltiples Contables con Una Bancaria Manualmente")
async def reconcile_manual_many_to_one(request: ManyToOneReconcileRequest = Body(...)):
    """
    Permite conciliar una transacción bancaria específica con una o más
    transacciones contables. Verifica sumas y estados de conciliación previos.
    """
    bank_tx_id = request.bank_transaction_id
    acc_tx_ids = request.accounting_transaction_ids

    if not acc_tx_ids:
        raise HTTPException(status_code=400, detail="Debe proporcionar al menos un ID de transacción contable.")

    # --- Validación ---
    # 1. Encontrar transacción bancaria
    bank_tx = find_transaction(bank_tx_id, 'bank')
    if not bank_tx:
        raise HTTPException(status_code=404, detail=f"No se encontró la transacción bancaria con ID {bank_tx_id}.")

    # 2. Verificar si la transacción bancaria ya está conciliada (participa en CUALQUIER par)
    # ¡OJO! Esta validación podría ser demasiado estricta si permites que una bancaria
    # se concilie con múltiples contables en diferentes momentos.
    # Si quieres permitirlo (como hace la lógica actual), podrías comentar esta parte.
    # Pero si una bancaria solo debe conciliarse una vez (quizás con varias contables a la vez), déjala.
    # Decisión: La dejaremos por ahora para ser estrictos, pero considera comentarla si necesitas más flexibilidad.
    if any(p.bankTransactionId == bank_tx_id for p in db["matched_pairs"]):
        raise HTTPException(status_code=400, detail=f"La transacción bancaria {bank_tx_id} ya participa en otra conciliación.")

    # 3. Encontrar transacciones contables y verificar su estado
    accounting_txs: List[Transaction] = []
    total_accounting_amount = 0.0
    for acc_id in acc_tx_ids:
        acc_tx = find_transaction(acc_id, 'accounting')
        if not acc_tx:
            raise HTTPException(status_code=404, detail=f"No se encontró la transacción contable con ID {acc_id}.")
        # Verificar si esta transacción contable específica ya está en algún par
        if any(p.accountingTransactionId == acc_id for p in db["matched_pairs"]):
            raise HTTPException(status_code=400, detail=f"La transacción contable {acc_id} ya participa en otra conciliación.")
        accounting_txs.append(acc_tx)
        total_accounting_amount += acc_tx.amount

    # 4. (Recomendado) Verificar Suma de Montos
    tolerance = 0.01 # Ej: 1 céntimo de diferencia permitido
    amount_match = abs(bank_tx.amount - total_accounting_amount) < tolerance
    warning_message = ""
    if not amount_match:
        warning_message = (f"Advertencia: La suma de los montos contables ({total_accounting_amount:.2f}) "
                           f"no coincide exactamente (tolerancia {tolerance:.2f}) "
                           f"con el monto bancario ({bank_tx.amount:.2f}). ")
        print(f"WARN: {warning_message} para Banco ID {bank_tx_id}")
        # Decisión: Solo advertencia, no error. Cambia a HTTPException(400) si quieres que sea error.

    # --- Creación de Pares ---
    newly_created_pairs: List[MatchedPair] = []
    for acc_tx in accounting_txs:
        new_match = MatchedPair(
            bankTransactionId=bank_tx_id,
            accountingTransactionId=acc_tx.id,
        )
        db["matched_pairs"].append(new_match) # Añadir al estado global
        newly_created_pairs.append(new_match)

    count = len(newly_created_pairs)
    final_message = (f"{warning_message}Conciliación manual muchos-a-uno exitosa. "
                     f"Se vincularon {count} transacciones contables con la transacción bancaria {bank_tx_id}.")
    print(f"INFO: {final_message}")

    return ManyToOneReconcileResponse(
        success=True,
        message=final_message,
        matched_pairs_created=newly_created_pairs
    )

# --- Fin del bloque para pegar ---

# --- Para ejecutar con uvicorn (si este es tu archivo principal) ---
# if __name__ == "__main__":
#     import uvicorn
#     # Ajusta host y port según necesites
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)