from pydantic import BaseModel
from typing import List, Literal

# Represents a single transaction, matching src/types/index.ts
class Transaction(BaseModel):
    id: str
    date: str # Keep as string for simplicity, consider date objects for real use
    description: str
    amount: float
    type: Literal['bank', 'accounting']

# Represents the structure for initial data load
class InitialDataResponse(BaseModel):
    bank_transactions: List[Transaction]
    accounting_transactions: List[Transaction]

# Request body for manual reconciliation
class ManualReconcileRequest(BaseModel):
    bank_transaction_id: str
    accounting_transaction_id: str

# Represents a matched pair, matching src/types/index.ts
class MatchedPair(BaseModel):
    bankTransactionId: str # Use camelCase matching frontend type
    accountingTransactionId: str # Use camelCase matching frontend type

# Response for successful reconciliation
class ReconcileResponse(BaseModel):
    success: bool
    message: str
    matched_pair: MatchedPair | None = None # Return the pair if successful

# Response for file upload (could return parsed transactions)
class UploadResponse(BaseModel):
    filename: str
    message: str
    transactions: List[Transaction] # Return parsed transactions
