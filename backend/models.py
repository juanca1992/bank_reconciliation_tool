# backend/models.py
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import date as py_date # Importar date

# --- Modelos Base ---

class Transaction(BaseModel):
    id: str
    date: Optional[py_date] = None # Usar py_date aquí
    description: Optional[str] = None
    amount: float
    type: Literal['bank', 'accounting']

class MatchedPair(BaseModel):
    # Usaremos camelCase aquí para coincidir con lo que espera/envía el frontend
    bankTransactionId: str
    accountingTransactionId: str

    # Configuración para permitir la población por nombre de campo o alias (Pydantic v2+)
    # Si usas Pydantic v1, necesitarías 'allow_population_by_field_name = True' en una clase Config interna.
    model_config = {
        "populate_by_name": True
    }

# --- Modelos para Endpoints ---

# GET /api/transactions/initial
class InitialDataResponse(BaseModel):
    bank_transactions: List[Transaction] = []
    accounting_transactions: List[Transaction] = []

# POST /api/transactions/upload/{tx_type}
class UploadResponse(BaseModel):
    filename: str
    message: str
    transaction_count: int
    transactions: List[Transaction] # Incluir transacciones procesadas

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
    matched_pairs: List[MatchedPair] = [] # Devuelve los *nuevos* pares encontrados

# POST /api/admin/clear_data
class ClearDataRequest(BaseModel): # Aunque se usa Body(embed=True), es bueno tener modelo
     confirm: bool

class ClearDataResponse(BaseModel):
     message: str