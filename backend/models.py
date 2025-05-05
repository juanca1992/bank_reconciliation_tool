from pydantic import BaseModel, Field
from typing import List, Literal, Optional # Optional is needed for nullable fields

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
    bankTransactionId: str = Field(..., alias="bankTransactionId") # Use alias for camelCase mapping
    accountingTransactionId: str = Field(..., alias="accountingTransactionId") # Use alias for camelCase mapping

    class Config:
        populate_by_name = True # Allow using either snake_case or alias name

# Response for successful manual reconciliation
class ManualReconcileResponse(BaseModel):
    success: bool
    message: str
    matched_pair: Optional[MatchedPair] = None # Use Optional for potentially null field

# Request body for automatic reconciliation
class AutoReconcileRequest(BaseModel):
    bank_transactions: List[Transaction]
    accounting_transactions: List[Transaction]

# Response for automatic reconciliation
class AutoReconcileResponse(BaseModel):
    success: bool
    message: str
    matched_pairs: List[MatchedPair] # Returns a list of newly matched pairs


# Response for file upload (returns parsed transactions)
class UploadResponse(BaseModel):
    filename: str
    message: str
    transactions: List[Transaction] # Return parsed transactions

