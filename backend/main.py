
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uuid # For generating unique IDs for demo data

# Import models from models.py
from .models import (
    Transaction,
    InitialDataResponse,
    ManualReconcileRequest,
    ManualReconcileResponse, # Renamed from ReconcileResponse for clarity
    AutoReconcileRequest, # New model for auto request
    AutoReconcileResponse, # New model for auto response
    MatchedPair,
    UploadResponse,
)

app = FastAPI(
    title="Herramienta de Conciliación Bancaria - Backend",
    description="API para gestionar la conciliación de extractos bancarios y contables.",
    version="0.1.0",
)

# --- CORS Configuration ---
# Adjust origins based on your frontend URL during development and production
origins = [
    "http://localhost:9002", # Next.js default dev port in this project
    "http://127.0.0.1:9002",
    # Add production frontend URL here if applicable
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

# --- In-memory storage (replace with database in production) ---
# Placeholder initial data (translated and slightly modified)
# Note: This `db` now represents the *total available* transactions,
# including ones that might be matched during the application lifecycle.
# The frontend sends the *currently unmatched* transactions for auto-reconciliation.
db = {
    "bank_transactions": [
        Transaction(id='b1', date='2024-07-01', description='Depósito Cliente A', amount=1500.00, type='bank'),
        Transaction(id='b2', date='2024-07-03', description='Retiro Cajero Automático', amount=-100.00, type='bank'),
        Transaction(id='b3', date='2024-07-05', description='Pago Proveedor X', amount=-350.50, type='bank'),
        Transaction(id='b4', date='2024-07-08', description='Intereses Ganados', amount=5.25, type='bank'),
        Transaction(id='b5', date='2024-07-10', description='Transferencia Recibida', amount=500.00, type='bank'), # Extra bank tx
    ],
    "accounting_transactions": [
        Transaction(id='a1', date='2024-07-01', description='Pago Factura #123', amount=1500.00, type='accounting'),
        Transaction(id='a2', date='2024-07-04', description='Gasto Suministros Oficina', amount=-100.00, type='accounting'),
        Transaction(id='a3', date='2024-07-05', description='Pago por INV-SUPX', amount=-350.50, type='accounting'),
        Transaction(id='a4', date='2024-07-09', description='Ingreso Intereses Banco', amount=5.25, type='accounting'),
        Transaction(id='a5', date='2024-07-11', description='Registro Factura Cliente B', amount=750.00, type='accounting'), # Extra acc tx
    ],
    "matched_pairs": [] # Store matched pairs here (can be populated by manual or auto)
}

# --- Helper Function to find a transaction in the main DB by ID ---
def find_transaction(tx_id: str, tx_type: Literal['bank', 'accounting']):
    list_key = f"{tx_type}_transactions"
    return next((tx for tx in db[list_key] if tx.id == tx_id), None)


# --- API Endpoints ---

@app.get("/", summary="Endpoint de Bienvenida")
async def read_root():
    """
    Endpoint raíz que devuelve un mensaje de bienvenida.
    """
    return {"message": "Bienvenido al API de Conciliación Bancaria"}

@app.get("/api/transactions/initial", response_model=InitialDataResponse, summary="Obtener Datos Iniciales")
async def get_initial_transactions():
    """
    Devuelve las transacciones iniciales consideradas *unmatched* al inicio.
    En una aplicación real, esto cargaría datos desde una base de datos o estado inicial.
    """
    # Filter out transactions whose IDs are in the matched_pairs list
    matched_bank_ids = {p.bankTransactionId for p in db["matched_pairs"]}
    matched_acc_ids = {p.accountingTransactionId for p in db["matched_pairs"]}

    unmatched_bank = [tx for tx in db["bank_transactions"] if tx.id not in matched_bank_ids]
    unmatched_acc = [tx for tx in db["accounting_transactions"] if tx.id not in matched_acc_ids]

    return InitialDataResponse(
        bank_transactions=unmatched_bank,
        accounting_transactions=unmatched_acc
    )

@app.post("/api/transactions/upload/bank", response_model=UploadResponse, summary="Subir Extracto Bancario")
async def upload_bank_statement(file: UploadFile = File(...)):
    """
    Simula la subida y procesamiento de un archivo de extracto bancario.
    **Nota:** El procesamiento real del archivo (CSV, Excel, etc.) no está implementado.
    Devuelve transacciones de ejemplo y las añade a la "base de datos" global.
    """
    print(f"Received bank file: {file.filename}, Content-Type: {file.content_type}")

    new_transactions = [
        Transaction(id=f'b-up-{uuid.uuid4().hex[:4]}', date='2024-08-01', description=f'Cargo {file.filename[:10]}', amount=-50.00, type='bank'),
        Transaction(id=f'b-up-{uuid.uuid4().hex[:4]}', date='2024-08-02', description=f'Abono {file.filename[:10]}', amount=250.00, type='bank'),
    ]
    # Add to the global list, duplicates are possible if file uploaded twice
    db["bank_transactions"].extend(new_transactions)

    return UploadResponse(
        filename=file.filename,
        message="Extracto bancario procesado (simulado).",
        transactions=new_transactions # Return only the newly added transactions
    )


@app.post("/api/transactions/upload/accounting", response_model=UploadResponse, summary="Subir Extracto Contable")
async def upload_accounting_statement(file: UploadFile = File(...)):
    """
    Simula la subida y procesamiento de un archivo de extracto contable.
    **Nota:** El procesamiento real del archivo no está implementado.
    Devuelve transacciones de ejemplo y las añade a la "base de datos" global.
    """
    print(f"Received accounting file: {file.filename}, Content-Type: {file.content_type}")

    new_transactions = [
         Transaction(id=f'a-up-{uuid.uuid4().hex[:4]}', date='2024-08-01', description=f'Registro Gasto {file.filename[:10]}', amount=-50.00, type='accounting'),
         Transaction(id=f'a-up-{uuid.uuid4().hex[:4]}', date='2024-08-03', description=f'Ingreso Venta {file.filename[:10]}', amount=250.00, type='accounting'),
    ]
    # Add to the global list
    db["accounting_transactions"].extend(new_transactions)

    return UploadResponse(
        filename=file.filename,
        message="Extracto contable procesado (simulado).",
        transactions=new_transactions # Return only the newly added transactions
    )

@app.post("/api/transactions/reconcile/manual", response_model=ManualReconcileResponse, summary="Conciliar Manualmente")
async def reconcile_manual(request: ManualReconcileRequest = Body(...)):
    """
    Realiza la conciliación manual entre una transacción bancaria y una contable específicas.
    Actualiza el estado global de `matched_pairs`.
    """
    bank_tx_id = request.bank_transaction_id
    acc_tx_id = request.accounting_transaction_id

    # Check if already matched in the global list
    if any(p.bankTransactionId == bank_tx_id for p in db["matched_pairs"]) or \
       any(p.accountingTransactionId == acc_tx_id for p in db["matched_pairs"]):
        raise HTTPException(status_code=400, detail="Una o ambas transacciones ya están conciliadas globalmente.")

    # Find transactions in the global DB (important!)
    bank_tx = find_transaction(bank_tx_id, 'bank')
    acc_tx = find_transaction(acc_tx_id, 'accounting')

    if not bank_tx or not acc_tx:
         # This might happen if frontend sends IDs not present in the backend's current state
        raise HTTPException(status_code=404, detail="No se encontró una o ambas transacciones en la base de datos global.")

    # Basic validation (optional, can be done on frontend too)
    amount_match = bank_tx.amount == acc_tx.amount
    warning = "" if amount_match else f"Advertencia: Los montos difieren ({bank_tx.amount:.2f} vs {acc_tx.amount:.2f}). "

    # Create and store the matched pair in the global list
    new_match = MatchedPair(
        bankTransactionId=bank_tx_id,
        accountingTransactionId=acc_tx_id,
    )
    db["matched_pairs"].append(new_match)

    message = f"{warning}Conciliación manual exitosa: Banco ID {bank_tx_id} con Contabilidad ID {acc_tx_id}."

    return ManualReconcileResponse(success=True, message=message, matched_pair=new_match)


@app.post("/api/transactions/reconcile/auto", response_model=AutoReconcileResponse, summary="Conciliar Automáticamente (Simulado)")
async def reconcile_auto(request: AutoReconcileRequest = Body(...)):
    """
    Simula una conciliación automática basada en criterios simples (ej. monto y fecha cercana).
    **Nota:** La lógica de coincidencia es muy básica para fines de demostración.
            Una implementación real usaría reglas más complejas o IA.
    Recibe las listas de transacciones *actualmente no conciliadas* del frontend.
    Devuelve las *nuevas* parejas encontradas en esta ejecución.
    Actualiza el estado global de `matched_pairs`.
    """
    bank_txs = request.bank_transactions
    acc_txs = request.accounting_transactions
    newly_matched_pairs: List[MatchedPair] = []

    # --- Placeholder Matching Logic ---
    # Extremely basic: Match if amount is identical and date is identical (or very close).
    # In a real app: Use fuzzy matching on description, date ranges, reference numbers, etc.
    # IMPORTANT: Avoid matching IDs that are *already* globally matched.

    available_acc_txs = list(acc_txs) # Create a mutable list to track available accounting txs

    for b_tx in bank_txs:
        # Check if this bank tx is already globally matched
        if any(p.bankTransactionId == b_tx.id for p in db["matched_pairs"]):
            continue # Skip if already matched globally

        best_match_acc_tx = None
        for a_tx in available_acc_txs:
            # Check if this accounting tx is already globally matched
            if any(p.accountingTransactionId == a_tx.id for p in db["matched_pairs"]):
                continue # Skip if already matched globally

            # Basic matching criteria (exact amount, exact date for demo)
            if b_tx.amount == a_tx.amount and b_tx.date == a_tx.date:
                best_match_acc_tx = a_tx
                break # Found a match, stop searching for this bank tx

        if best_match_acc_tx:
            # Found a potential match, create pair and remove from available list
            match = MatchedPair(
                bankTransactionId=b_tx.id,
                accountingTransactionId=best_match_acc_tx.id
            )
            newly_matched_pairs.append(match)
            # Add to global matched list *immediately* to prevent re-matching in this run
            db["matched_pairs"].append(match)
            available_acc_txs.remove(best_match_acc_tx) # Remove matched accounting tx

    # --- End Placeholder Matching Logic ---

    count = len(newly_matched_pairs)
    message = f"Conciliación automática simulada completada. Se encontraron {count} nuevas coincidencias."
    if count == 0:
        message = "Conciliación automática simulada completada. No se encontraron nuevas coincidencias con los criterios actuales."


    return AutoReconcileResponse(
        success=True,
        message=message,
        matched_pairs=newly_matched_pairs # Return only the pairs matched in *this* run
    )


@app.get("/api/transactions/matched", response_model=List[MatchedPair], summary="Obtener Todas las Conciliaciones Globales")
async def get_matched_pairs():
    """
    Devuelve la lista de *todas* las transacciones que han sido conciliadas globalmente
    (tanto manual como automáticamente).
    """
    return db["matched_pairs"]

# --- Health Check Endpoint ---
@app.get("/health", summary="Chequeo de Salud")
async def health_check():
    """
    Endpoint simple para verificar que el API está funcionando.
    """
    return {"status": "ok"}

# --- Optional: Run with uvicorn directly if needed ---
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) # Added reload=True for dev
