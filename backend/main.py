# backend/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Tuple, Literal
import uuid
import pandas as pd
import tempfile
import os
import traceback # Para imprimir errores completos
import io # Para manejar el archivo en memoria
from starlette.responses import StreamingResponse # Para enviar el archivo
from datetime import datetime # Para nombre de archivo único

# --- Importar Modelos Pydantic desde models.py ---
# (Asegúrate que models.py esté en el mismo directorio o ajusta la ruta)
try:
    from .models import (
        Transaction, MatchedPair, InitialDataResponse,
        ManualReconcileRequest, ManualReconcileResponse,
        ManyToOneReconcileRequest, ManyToOneReconcileResponse,
        OneToManyReconcileRequest, OneToManyReconcileResponse,
        AutoReconcileResponse, UploadResponse, ClearDataResponse
        # No necesitamos importar ClearDataRequest si usamos embed=True
    )
    print("INFO: Modelos Pydantic cargados desde models.py.")
except ImportError:
    print("ERROR FATAL: No se pudo importar desde models.py. Asegúrate que el archivo existe y no tiene errores.")
    # Podrías salir aquí o definir modelos dummy si quieres que la app intente iniciar
    # exit()
    # Definiciones dummy rápidas (no funcionales para la API real)
    class BaseModel: pass
    Transaction = MatchedPair = InitialDataResponse = ManualReconcileRequest = ManualReconcileResponse = ManyToOneReconcileRequest = ManyToOneReconcileResponse = OneToManyReconcileRequest = OneToManyReconcileResponse = AutoReconcileResponse = UploadResponse = ClearDataResponse = BaseModel

# --- Importar funciones de procesamiento ---
try:
    # Asumiendo que processing.py está en el mismo directorio que main.py
    from .processing import (
        transform_siesa_auxiliary,
        transform_bancolombia_statement,
        reconcile_data,
        FECHA_CONCILIACION, MOVIMIENTO_CONCILIACION,
        AUXILIAR_DEBITO, AUXILIAR_CREDITO
    )
    print("INFO: Módulo 'processing.py' cargado correctamente.")
except ImportError as e:
    print(f"ERROR FATAL: No se pudo importar 'processing.py' o sus constantes. Detalle: {e}")
    # Definir funciones y constantes dummy si falla la importación
    def transform_siesa_auxiliary(fp): print("ERROR: transform_siesa_auxiliary no cargado"); return None
    def transform_bancolombia_statement(fp): print("ERROR: transform_bancolombia_statement no cargado"); return None
    def reconcile_data(df1, df2, include_ids=True): print("ERROR: reconcile_data no cargado"); return None
    FECHA_CONCILIACION = 'fecha_norm'; MOVIMIENTO_CONCILIACION = 'movimiento'
    AUXILIAR_DEBITO = 'debito'; AUXILIAR_CREDITO = 'credito'


# --- Configuración de la App FastAPI ---
app = FastAPI(
    title="Herramienta de Conciliación Bancaria - Backend vFinal",
    description="API con procesamiento real, conciliación manual flexible y descarga de reporte.",
    version="1.0.0",
)

# --- Configuración CORS (Incluyendo Puerto 9003) ---
origins = [
    "http://localhost:9002",    # Puerto anterior
    "http://127.0.0.1:9002",
    "http://localhost:9003",    # Puerto nuevo del frontend
    "http://127.0.0.1:9003",
    # Añadir URLs de producción aquí si se despliega
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # Importante si manejas cookies o autenticación
    allow_methods=["*"],    # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"],    # Permite todas las cabeceras
)

# --- Almacenamiento Global en Memoria ---
# Simula una base de datos simple. Los datos se pierden al reiniciar.
db: Dict[str, List] = {
    "bank_transactions": [],
    "accounting_transactions": [],
    "matched_pairs": []
}

# --- Funciones Helper ---
# (find_transaction, dataframe_to_transactions, transactions_to_dataframe: sin cambios respecto a la versión anterior)
def find_transaction(tx_id: str, tx_type: Literal['bank', 'accounting']) -> Optional[Transaction]:
    list_key = f"{tx_type}_transactions"
    return next((tx for tx in db.get(list_key, []) if tx.id == tx_id), None)

def dataframe_to_transactions(df: pd.DataFrame, tx_type: Literal['bank', 'accounting']) -> List[Transaction]:
    transactions = []
    if df is None or df.empty: return transactions
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
        print(f"ERROR dataframe_to_transactions: Faltan columnas requeridas para '{tx_type}': {missing_cols}")
        raise ValueError(f"Columnas faltantes en DataFrame '{tx_type}': {missing_cols}")
    for _, row in df.iterrows():
        tx_id = f"{tx_type[0]}-{uuid.uuid4().hex[:8]}"
        date_val = row.get(FECHA_CONCILIACION)
        processed_date = None
        if pd.notna(date_val):
            try:
                if isinstance(date_val, pd.Timestamp): processed_date = date_val.date()
                elif isinstance(date_val, datetime.date): processed_date = date_val
                else: processed_date = pd.to_datetime(date_val).date()
            except Exception as date_err: print(f"WARN dataframe_to_transactions: No se pudo convertir fecha '{date_val}' (ID: {tx_id}): {date_err}")
        description = str(row.get(desc_col, ''))
        amount = 0.0
        if tx_type == 'bank': amount = float(row.get(MOVIMIENTO_CONCILIACION, 0.0))
        else: amount = float(row.get(AUXILIAR_DEBITO, 0.0)) - float(row.get(AUXILIAR_CREDITO, 0.0))
        transactions.append(Transaction(id=tx_id, date=processed_date, description=description, amount=round(amount, 2), type=tx_type))
    return transactions

def transactions_to_dataframe(transactions: List[Transaction], tx_type: Literal['bank', 'accounting']) -> pd.DataFrame:
    if not transactions:
        cols = [FECHA_CONCILIACION, 'tx_id_ref']
        if tx_type == 'bank': cols.extend([MOVIMIENTO_CONCILIACION, 'descripcion_extracto'])
        else: cols.extend([AUXILIAR_DEBITO, AUXILIAR_CREDITO, 'descripcion_auxiliar', 'documento_auxiliar'])
        return pd.DataFrame(columns=cols)
    data = []
    for tx in transactions:
        record = {'tx_id_ref': tx.id, FECHA_CONCILIACION: tx.date}
        if tx_type == 'bank':
            record[MOVIMIENTO_CONCILIACION] = tx.amount
            record['descripcion_extracto'] = tx.description
        else:
            record[AUXILIAR_DEBITO] = tx.amount if tx.amount >= 0 else 0.0
            record[AUXILIAR_CREDITO] = -tx.amount if tx.amount < 0 else 0.0
            record['descripcion_auxiliar'] = tx.description
            record['documento_auxiliar'] = f"DOC_{tx.id}" # Placeholder
        data.append(record)
    df = pd.DataFrame(data)
    try:
        df[FECHA_CONCILIACION] = pd.to_datetime(df[FECHA_CONCILIACION], errors='coerce')
        if tx_type == 'bank': df[MOVIMIENTO_CONCILIACION] = pd.to_numeric(df[MOVIMIENTO_CONCILIACION], errors='coerce').fillna(0.0)
        else:
            df[AUXILIAR_DEBITO] = pd.to_numeric(df[AUXILIAR_DEBITO], errors='coerce').fillna(0.0)
            df[AUXILIAR_CREDITO] = pd.to_numeric(df[AUXILIAR_CREDITO], errors='coerce').fillna(0.0)
            if 'documento_auxiliar' not in df.columns: df['documento_auxiliar'] = ''
    except Exception as e:
        print(f"ERROR transactions_to_dataframe: Fallo al convertir tipos para '{tx_type}': {e}")
        raise ValueError(f"Error convirtiendo tipos para reconcile_data ({tx_type}): {e}")
    return df

# --- Endpoints ---

@app.get("/", summary="Endpoint de Bienvenida", include_in_schema=False)
async def read_root():
    return {"message": "Bienvenido al API de Conciliación Bancaria vFinal"}

@app.post("/api/transactions/upload/{tx_type}", response_model=UploadResponse, summary="Subir y Procesar Extracto")
async def upload_and_process_statement(tx_type: Literal['bank', 'accounting'], file: UploadFile = File(...)):
    # (Sin cambios respecto a la versión anterior)
    if tx_type not in ['bank', 'accounting']: raise HTTPException(status_code=400, detail="Tipo inválido.")
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read(); tmp_file.write(content); tmp_file_path = tmp_file.name
        print(f"INFO: Archivo '{file.filename}' -> '{tmp_file_path}'")
        df_processed = None
        if tx_type == 'bank': df_processed = transform_bancolombia_statement(tmp_file_path)
        else: df_processed = transform_siesa_auxiliary(tmp_file_path)
        os.remove(tmp_file_path); print(f"INFO: Temporal '{tmp_file_path}' eliminado.")
        if df_processed is None: raise HTTPException(status_code=400, detail=f"Error al procesar archivo '{file.filename}'. Ver logs.")
        new_transactions = []
        if not df_processed.empty: new_transactions = dataframe_to_transactions(df_processed, tx_type)
        db[f"{tx_type}_transactions"] = new_transactions
        db["matched_pairs"] = [] # Reiniciar conciliaciones
        message = f"Archivo '{tx_type}' procesado. {len(new_transactions)} txs cargadas."
        if df_processed is not None and df_processed.empty: message = f"Archivo '{tx_type}' procesado, 0 txs válidas."
        print(f"INFO: {message}. Conciliaciones reiniciadas.")
        return UploadResponse(filename=file.filename, message=message, transaction_count=len(new_transactions), transactions=new_transactions)
    except HTTPException as h: raise h
    except ValueError as v: print(f"ERROR (ValueError) {file.filename}: {v}"); raise HTTPException(status_code=400, detail=f"Error validación/formato: {v}")
    except Exception as e: print(f"ERROR FATAL {file.filename}: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"Error interno: {e}")
    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
             try: os.remove(tmp_file_path); print(f"INFO: Temporal '{tmp_file_path}' eliminado (finally).")
             except OSError as ose: print(f"ERROR: Fallo eliminando temp (finally) '{tmp_file_path}': {ose}")
        await file.close()


@app.get("/api/transactions/initial", response_model=InitialDataResponse, summary="Obtener Datos No Conciliados")
async def get_initial_transactions():
    # (Sin cambios respecto a la versión anterior)
    matched_bank_ids = {p.bankTransactionId for p in db.get("matched_pairs", [])}
    matched_acc_ids = {p.accountingTransactionId for p in db.get("matched_pairs", [])}
    unmatched_bank = [tx for tx in db.get("bank_transactions", []) if tx.id not in matched_bank_ids]
    unmatched_acc = [tx for tx in db.get("accounting_transactions", []) if tx.id not in matched_acc_ids]
    print(f"INFO: Devolviendo {len(unmatched_bank)} bancarias y {len(unmatched_acc)} contables no conciliadas.")
    return InitialDataResponse(bank_transactions=unmatched_bank, accounting_transactions=unmatched_acc)

@app.post("/api/transactions/reconcile/manual", response_model=ManualReconcileResponse, summary="Conciliar Manualmente (1 a 1)")
async def reconcile_manual(request: ManualReconcileRequest = Body(...)):
    # (Sin cambios respecto a la versión anterior, con validación estricta)
    bank_tx_id = request.bank_transaction_id; acc_tx_id = request.accounting_transaction_id
    if any(p.bankTransactionId == bank_tx_id for p in db["matched_pairs"]): raise HTTPException(status_code=400, detail=f"Banco {bank_tx_id} ya conciliado.")
    if any(p.accountingTransactionId == acc_tx_id for p in db["matched_pairs"]): raise HTTPException(status_code=400, detail=f"Contable {acc_tx_id} ya conciliado.")
    bank_tx = find_transaction(bank_tx_id, 'bank'); acc_tx = find_transaction(acc_tx_id, 'accounting')
    if not bank_tx: raise HTTPException(status_code=404, detail=f"Banco {bank_tx_id} no encontrado.")
    if not acc_tx: raise HTTPException(status_code=404, detail=f"Contable {acc_tx_id} no encontrado.")
    tolerance = 0.01; amount_match = abs(bank_tx.amount - acc_tx.amount) < tolerance
    warning = "" if amount_match else f"Advertencia: Montos difieren ({bank_tx.amount:.2f} vs {acc_tx.amount:.2f}). "
    new_match = MatchedPair(bankTransactionId=bank_tx_id, accountingTransactionId=acc_tx_id)
    db["matched_pairs"].append(new_match)
    message = f"{warning}Conciliación manual (1-1) exitosa: Banco {bank_tx_id} con Contable {acc_tx_id}."
    print(f"INFO: {message}")
    return ManualReconcileResponse(success=True, message=message, matched_pair=new_match)

@app.post("/api/transactions/reconcile/manual/many_to_one", response_model=ManyToOneReconcileResponse, summary="Conciliar Manualmente (1 Banco a Múltiples Contables)")
async def reconcile_manual_many_to_one(request: ManyToOneReconcileRequest = Body(...)):
    # (Sin cambios respecto a la versión anterior, con validación estricta)
    bank_tx_id = request.bank_transaction_id; acc_tx_ids = request.accounting_transaction_ids
    if not acc_tx_ids: raise HTTPException(status_code=400, detail="Se requiere al menos un ID contable.")
    bank_tx = find_transaction(bank_tx_id, 'bank')
    if not bank_tx: raise HTTPException(status_code=404, detail=f"Banco {bank_tx_id} no encontrado.")
    # Comentar la siguiente línea si se permite conciliación parcial/múltiple para el banco
    if any(p.bankTransactionId == bank_tx_id for p in db["matched_pairs"]): raise HTTPException(status_code=400, detail=f"Banco {bank_tx_id} ya está conciliado.")
    accounting_txs: List[Transaction] = []; total_accounting_amount = 0.0; processed_acc_ids = set()
    for acc_id in acc_tx_ids:
        if acc_id in processed_acc_ids: continue
        acc_tx = find_transaction(acc_id, 'accounting')
        if not acc_tx: raise HTTPException(status_code=404, detail=f"Contable {acc_id} no encontrado.")
        if any(p.accountingTransactionId == acc_id for p in db["matched_pairs"]): raise HTTPException(status_code=400, detail=f"Contable {acc_id} ya está conciliado.")
        accounting_txs.append(acc_tx); total_accounting_amount += acc_tx.amount; processed_acc_ids.add(acc_id)
    tolerance = 0.01; amount_match = abs(bank_tx.amount - total_accounting_amount) < tolerance
    warning = "" if amount_match else f"Advertencia: Suma contable ({total_accounting_amount:.2f}) difiere del banco ({bank_tx.amount:.2f}). "
    newly_created_pairs: List[MatchedPair] = []
    for acc_tx in accounting_txs:
        new_match = MatchedPair(bankTransactionId=bank_tx_id, accountingTransactionId=acc_tx.id)
        db["matched_pairs"].append(new_match); newly_created_pairs.append(new_match)
    message = f"{warning}Conciliación (1 Banco a {len(newly_created_pairs)} Contables) exitosa para Banco {bank_tx_id}."
    print(f"INFO: {message}")
    return ManyToOneReconcileResponse(success=True, message=message, matched_pairs_created=newly_created_pairs)

@app.post("/api/transactions/reconcile/manual/one_to_many", response_model=OneToManyReconcileResponse, summary="Conciliar Manualmente (Múltiples Bancos a 1 Contable)")
async def reconcile_manual_one_to_many(request: OneToManyReconcileRequest = Body(...)):
    # (Sin cambios respecto a la versión anterior, con validación estricta)
    acc_tx_id = request.accounting_transaction_id; bank_tx_ids = request.bank_transaction_ids
    if not bank_tx_ids: raise HTTPException(status_code=400, detail="Se requiere al menos un ID bancario.")
    acc_tx = find_transaction(acc_tx_id, 'accounting')
    if not acc_tx: raise HTTPException(status_code=404, detail=f"Contable {acc_tx_id} no encontrado.")
    # Comentar la siguiente línea si se permite conciliación parcial/múltiple para el contable
    if any(p.accountingTransactionId == acc_tx_id for p in db["matched_pairs"]): raise HTTPException(status_code=400, detail=f"Contable {acc_tx_id} ya está conciliado.")
    bank_txs: List[Transaction] = []; total_bank_amount = 0.0; processed_bank_ids = set()
    for bank_id in bank_tx_ids:
        if bank_id in processed_bank_ids: continue
        bank_tx = find_transaction(bank_id, 'bank')
        if not bank_tx: raise HTTPException(status_code=404, detail=f"Banco {bank_id} no encontrado.")
        if any(p.bankTransactionId == bank_id for p in db["matched_pairs"]): raise HTTPException(status_code=400, detail=f"Banco {bank_id} ya está conciliado.")
        bank_txs.append(bank_tx); total_bank_amount += bank_tx.amount; processed_bank_ids.add(bank_id)
    tolerance = 0.01; amount_match = abs(total_bank_amount - acc_tx.amount) < tolerance
    warning = "" if amount_match else f"Advertencia: Suma bancaria ({total_bank_amount:.2f}) difiere del contable ({acc_tx.amount:.2f}). "
    newly_created_pairs: List[MatchedPair] = []
    for bank_tx in bank_txs:
        new_match = MatchedPair(bankTransactionId=bank_tx.id, accountingTransactionId=acc_tx_id)
        db["matched_pairs"].append(new_match); newly_created_pairs.append(new_match)
    message = f"{warning}Conciliación ({len(newly_created_pairs)} Bancos a 1 Contable) exitosa para Contable {acc_tx_id}."
    print(f"INFO: {message}")
    return OneToManyReconcileResponse(success=True, message=message, matched_pairs_created=newly_created_pairs)

@app.post("/api/transactions/reconcile/auto", response_model=AutoReconcileResponse, summary="Ejecutar Conciliación Automática")
async def reconcile_auto():
    # (Sin cambios respecto a la versión anterior)
    print("INFO: Iniciando conciliación automática...")
    matched_bank_ids = {p.bankTransactionId for p in db.get("matched_pairs", [])}
    matched_acc_ids = {p.accountingTransactionId for p in db.get("matched_pairs", [])}
    unmatched_bank_txs = [tx for tx in db.get("bank_transactions", []) if tx.id not in matched_bank_ids]
    unmatched_acc_txs = [tx for tx in db.get("accounting_transactions", []) if tx.id not in matched_acc_ids]
    print(f"INFO: Candidatos Auto: {len(unmatched_bank_txs)} B, {len(unmatched_acc_txs)} A.")
    if not unmatched_bank_txs or not unmatched_acc_txs: return AutoReconcileResponse(success=True, message="No hay suficientes txs pendientes.", matched_pairs=[])
    try:
        df_ledger = transactions_to_dataframe(unmatched_acc_txs, 'accounting')
        df_statement = transactions_to_dataframe(unmatched_bank_txs, 'bank')
        if df_ledger.empty or df_statement.empty: return AutoReconcileResponse(success=True, message="DFs vacíos para reconcile_data.", matched_pairs=[])
    except Exception as e: print(f"ERROR pre-reconcile_data: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail="Error preparando datos.")
    reconciliation_result = None
    try: reconciliation_result = reconcile_data(df_ledger, df_statement, include_ids=True)
    except Exception as e: print(f"ERROR reconcile_data: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail="Error en reconcile_data.")
    if reconciliation_result is None: raise HTTPException(status_code=500, detail="Fallo reconcile_data.")
    _, df_conciliados, _ = reconciliation_result; print(f"INFO: reconcile_data encontró {len(df_conciliados)} coincidencias.")
    newly_matched_pairs: List[MatchedPair] = []
    if not df_conciliados.empty:
        if 'tx_id_ref_x' not in df_conciliados.columns or 'tx_id_ref_y' not in df_conciliados.columns: raise HTTPException(status_code=500, detail="Resultado reconcile_data sin IDs.")
        current_bank_matched = {p.bankTransactionId for p in db["matched_pairs"]}
        current_acc_matched = {p.accountingTransactionId for p in db["matched_pairs"]}
        for _, row in df_conciliados.iterrows():
            acc_tx_id = str(row['tx_id_ref_x']); bank_tx_id = str(row['tx_id_ref_y'])
            if acc_tx_id not in current_acc_matched and bank_tx_id not in current_bank_matched:
                 new_match = MatchedPair(bankTransactionId=bank_tx_id, accountingTransactionId=acc_tx_id)
                 db["matched_pairs"].append(new_match); newly_matched_pairs.append(new_match)
                 current_bank_matched.add(bank_tx_id); current_acc_matched.add(acc_tx_id) # Actualizar sets para chequeos intra-loop
    count = len(newly_matched_pairs); message = f"Auto completado. {count} nuevas coincidencias añadidas."
    if count == 0: message = f"Auto completado. No se encontraron nuevas coincidencias aplicables ({len(df_conciliados)} potenciales)."
    print(f"INFO: {message}")
    return AutoReconcileResponse(success=True, message=message, matched_pairs=newly_matched_pairs)

@app.get("/api/transactions/matched", response_model=List[MatchedPair], summary="Obtener Conciliaciones Globales")
async def get_matched_pairs():
    # (Sin cambios)
    print(f"INFO: Devolviendo {len(db['matched_pairs'])} pares conciliados globales.")
    return db.get("matched_pairs", [])

# --- Endpoint de Descarga ---
@app.get("/api/reconciliation/download",
         response_class=StreamingResponse,
         summary="Descargar Estado Actual de Conciliación en Excel")
async def download_reconciliation():
    # (Sin cambios respecto a la versión anterior)
    print("INFO: Solicitud para descargar estado de conciliación.")
    current_bank_txs = db.get("bank_transactions", []); current_acc_txs = db.get("accounting_transactions", [])
    current_matched_pairs = db.get("matched_pairs", [])
    if not current_bank_txs and not current_acc_txs: raise HTTPException(status_code=404, detail="No hay txs cargadas.")
    matched_bank_ids = {p.bankTransactionId for p in current_matched_pairs}
    matched_acc_ids = {p.accountingTransactionId for p in current_matched_pairs}
    pending_bank = [tx for tx in current_bank_txs if tx.id not in matched_bank_ids]
    pending_acc = [tx for tx in current_acc_txs if tx.id not in matched_acc_ids]
    conciliados_data = []
    for pair in current_matched_pairs:
        bank_tx = find_transaction(pair.bankTransactionId, 'bank'); acc_tx = find_transaction(pair.accountingTransactionId, 'accounting')
        if bank_tx and acc_tx: conciliados_data.append({'ID Banco': bank_tx.id, 'Fecha Banco': bank_tx.date, 'Descripción Banco': bank_tx.description, 'Monto Banco': bank_tx.amount, 'ID Contable': acc_tx.id, 'Fecha Contable': acc_tx.date, 'Descripción Contable': acc_tx.description, 'Monto Contable': acc_tx.amount})
    pendientes_banco_data = [{'ID Banco': tx.id, 'Fecha': tx.date, 'Descripción': tx.description, 'Monto': tx.amount} for tx in pending_bank]
    pendientes_contable_data = [{'ID Contable': tx.id, 'Fecha': tx.date, 'Descripción': tx.description, 'Monto': tx.amount} for tx in pending_acc]
    df_conciliados = pd.DataFrame(conciliados_data); df_pendientes_banco = pd.DataFrame(pendientes_banco_data); df_pendientes_contable = pd.DataFrame(pendientes_contable_data)
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_conciliados.to_excel(writer, sheet_name='Conciliados', index=False)
            df_pendientes_banco.to_excel(writer, sheet_name='Pendientes Banco', index=False)
            df_pendientes_contable.to_excel(writer, sheet_name='Pendientes Contable', index=False)
        excel_data = output.getvalue()
    except Exception as excel_err: print(f"ERROR generando Excel: {excel_err}"); traceback.print_exc(); raise HTTPException(status_code=500, detail="Error generando Excel.")
    filename = f"conciliacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
    print(f"INFO: Enviando archivo '{filename}'.")
    return StreamingResponse(io.BytesIO(excel_data), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)

@app.get("/health", summary="Chequeo de Salud", include_in_schema=False)
async def health_check():
    return {"status": "ok"}

@app.post("/api/admin/clear_data", response_model=ClearDataResponse, summary="Limpiar Datos (ADMIN)", include_in_schema=False)
async def clear_all_data(confirm: bool = Body(..., embed=True)):
    # (Sin cambios)
    if not confirm: raise HTTPException(status_code=400, detail="Se requiere confirmación (confirm=true).")
    db["bank_transactions"] = []; db["accounting_transactions"] = []; db["matched_pairs"] = []
    message = "Datos en memoria eliminados."; print(f"INFO: {message}"); return ClearDataResponse(message=message)

# --- Uvicorn Runner (opcional) ---
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)