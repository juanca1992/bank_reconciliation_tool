from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uuid # For generating unique IDs for demo data

# Import models from models.py
from .models import (
    Transaction,
    InitialDataResponse,
    ManualReconcileRequest,
    ReconcileResponse,
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
db = {
    "bank_transactions": [
        Transaction(id='b1', date='2024-07-01', description='Depósito Cliente A', amount=1500.00, type='bank'),
        Transaction(id='b2', date='2024-07-03', description='Retiro Cajero Automático', amount=-100.00, type='bank'),
        Transaction(id='b3', date='2024-07-05', description='Pago Proveedor X', amount=-350.50, type='bank'),
        Transaction(id='b4', date='2024-07-08', description='Intereses Ganados', amount=5.25, type='bank'),
    ],
    "accounting_transactions": [
        Transaction(id='a1', date='2024-07-01', description='Pago Factura #123', amount=1500.00, type='accounting'),
        Transaction(id='a2', date='2024-07-04', description='Gasto Suministros Oficina', amount=-100.00, type='accounting'),
        Transaction(id='a3', date='2024-07-05', description='Pago por INV-SUPX', amount=-350.50, type='accounting'),
        Transaction(id='a4', date='2024-07-09', description='Ingreso Intereses Banco', amount=5.25, type='accounting'),
    ],
    "matched_pairs": [] # Store matched pairs here
}

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
    Devuelve las transacciones iniciales (bancarias y contables) para la demo.
    En una aplicación real, esto cargaría datos desde una base de datos o estado inicial.
    """
    # Return only unmatched transactions initially
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
    Devuelve transacciones de ejemplo.
    """
    # --- Placeholder Parsing Logic ---
    # In a real app, you would parse the file content (file.file.read())
    # using libraries like pandas, csv, openpyxl based on the file type.
    # For demo, we just return new dummy data.
    print(f"Received bank file: {file.filename}, Content-Type: {file.content_type}")

    # Example: Generate new transactions based on upload
    new_transactions = [
        Transaction(id=f'b-up-{uuid.uuid4().hex[:4]}', date='2024-08-01', description=f'Cargo {file.filename[:10]}', amount=-50.00, type='bank'),
        Transaction(id=f'b-up-{uuid.uuid4().hex[:4]}', date='2024-08-02', description=f'Abono {file.filename[:10]}', amount=250.00, type='bank'),
    ]
    db["bank_transactions"].extend(new_transactions) # Add to our "database"
    # --- End Placeholder ---

    return UploadResponse(
        filename=file.filename,
        message="Extracto bancario procesado (simulado).",
        transactions=new_transactions # Return the newly added transactions
    )


@app.post("/api/transactions/upload/accounting", response_model=UploadResponse, summary="Subir Extracto Contable")
async def upload_accounting_statement(file: UploadFile = File(...)):
    """
    Simula la subida y procesamiento de un archivo de extracto contable.
    **Nota:** El procesamiento real del archivo no está implementado.
    Devuelve transacciones de ejemplo.
    """
    # --- Placeholder Parsing Logic ---
    print(f"Received accounting file: {file.filename}, Content-Type: {file.content_type}")

    new_transactions = [
         Transaction(id=f'a-up-{uuid.uuid4().hex[:4]}', date='2024-08-01', description=f'Registro Gasto {file.filename[:10]}', amount=-50.00, type='accounting'),
         Transaction(id=f'a-up-{uuid.uuid4().hex[:4]}', date='2024-08-03', description=f'Ingreso Venta {file.filename[:10]}', amount=250.00, type='accounting'),
    ]
    db["accounting_transactions"].extend(new_transactions)
    # --- End Placeholder ---

    return UploadResponse(
        filename=file.filename,
        message="Extracto contable procesado (simulado).",
        transactions=new_transactions # Return the newly added transactions
    )

@app.post("/api/transactions/reconcile/manual", response_model=ReconcileResponse, summary="Conciliar Manualmente")
async def reconcile_manual(request: ManualReconcileRequest = Body(...)):
    """
    Realiza la conciliación manual entre una transacción bancaria y una contable.
    """
    bank_tx_id = request.bank_transaction_id
    acc_tx_id = request.accounting_transaction_id

    # Check if already matched
    if any(p.bankTransactionId == bank_tx_id for p in db["matched_pairs"]) or \
       any(p.accountingTransactionId == acc_tx_id for p in db["matched_pairs"]):
        raise HTTPException(status_code=400, detail="Una o ambas transacciones ya están conciliadas.")

    # Find transactions (simple lookup in demo data)
    bank_tx = next((tx for tx in db["bank_transactions"] if tx.id == bank_tx_id), None)
    acc_tx = next((tx for tx in db["accounting_transactions"] if tx.id == acc_tx_id), None)

    if not bank_tx or not acc_tx:
        raise HTTPException(status_code=404, detail="No se encontró una o ambas transacciones.")

    # Basic validation (e.g., amount match - can be more complex)
    # Allowing mismatch for demo purposes as per frontend logic
    amount_match = bank_tx.amount == acc_tx.amount
    warning = "" if amount_match else f"Advertencia: Los montos difieren ({bank_tx.amount:.2f} vs {acc_tx.amount:.2f}). "

    # Create and store the matched pair
    new_match = MatchedPair(
        bankTransactionId=bank_tx_id,
        accountingTransactionId=acc_tx_id,
    )
    db["matched_pairs"].append(new_match)

    message = f"{warning}Conciliación manual exitosa: Banco ID {bank_tx_id} con Contabilidad ID {acc_tx_id}."

    return ReconcileResponse(success=True, message=message, matched_pair=new_match)


@app.get("/api/transactions/matched", response_model=List[MatchedPair], summary="Obtener Conciliaciones")
async def get_matched_pairs():
    """
    Devuelve la lista de todas las transacciones que han sido conciliadas.
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
#     uvicorn.run(app, host="0.0.0.0", port=8000)
