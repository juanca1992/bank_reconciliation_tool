# backend/models.py
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import date as py_date # Importar date

# --- Modelos Base ---

class Transaction(BaseModel):
    id: str                     # ID interno generado por el backend
    date: Optional[py_date] = None # Fecha normalizada
    description: Optional[str] = None # Descripción normalizada
    amount: float               # Monto normalizado (positivo/negativo para banco, neto para contable)
    type: Literal['bank', 'accounting'] # Tipo de transacción

class MatchedPair(BaseModel):
    # Usaremos camelCase aquí para coincidir con lo que espera/envía el frontend
    bankTransactionId: str
    accountingTransactionId: str

    # Configuración para permitir la población por nombre de campo o alias (Pydantic v2+)
    model_config = {
        "populate_by_name": True
    }

# --- Modelo para Formatos Disponibles ---

class AvailableFormat(BaseModel):
    id: str # Identificador único del formato (ej: 'bancolombia_csv_9col')
    description: str # Descripción legible para el usuario (ej: 'Banco - Bancolombia CSV (9 Col)')

# --- Modelos para Endpoints ---

# GET /api/transactions/initial
class InitialDataResponse(BaseModel):
    bank_transactions: List[Transaction] = []
    accounting_transactions: List[Transaction] = []

# POST /api/transactions/upload (Ahora genérico)
class UploadResponse(BaseModel):
    filename: str
    message: str
    transaction_count: int
    transactions: List[Transaction] # Incluir transacciones procesadas para mostrarlas inmediatamente

# POST /api/transactions/reconcile/manual (1 a 1)
class ManualReconcileRequest(BaseModel):
    bank_transaction_id: str
    accounting_transaction_id: str

class ManualReconcileResponse(BaseModel):
    success: bool
    message: str
    matched_pair: Optional[MatchedPair] = None

# POST /api/transactions/reconcile/manual/many_to_one (1 Banco -> Múltiples Contables)
class ManyToOneReconcileRequest(BaseModel):
    bank_transaction_id: str
    accounting_transaction_ids: List[str]

class ManyToOneReconcileResponse(BaseModel):
    success: bool
    message: str
    matched_pairs_created: List[MatchedPair] = []

# POST /api/transactions/reconcile/manual/one_to_many (Múltiples Bancos -> 1 Contable)
class OneToManyReconcileRequest(BaseModel):
    accounting_transaction_id: str
    bank_transaction_ids: List[str]

class OneToManyReconcileResponse(BaseModel):
    success: bool
    message: str
    matched_pairs_created: List[MatchedPair] = []

# POST /api/transactions/reconcile/auto
class AutoReconcileResponse(BaseModel):
    success: bool
    message: str
    matched_pairs: List[MatchedPair] = [] # Devuelve los *nuevos* pares encontrados en esa ejecución

# POST /api/admin/clear_data
class ClearDataRequest(BaseModel): # Aunque se usa Body(embed=True), es bueno tener modelo
     confirm: bool

class ClearDataResponse(BaseModel):
     message: str
```