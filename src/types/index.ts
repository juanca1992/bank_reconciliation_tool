
/** Represents a single financial transaction, either from a bank statement or accounting ledger. */
export interface Transaction {
  id: string;                 // Unique identifier assigned by the backend
  date: string | null;        // Transaction date (YYYY-MM-DD) or null if unavailable/invalid
  description: string;        // Transaction description
  amount: number;             // Transaction amount (positive/negative for bank, net debit/credit for accounting)
  type: 'bank' | 'accounting';// Origin of the transaction
}

/** Represents a pair of matched bank and accounting transaction IDs. */
export interface MatchedPair {
  bankTransactionId: string;
  accountingTransactionId: string;
}

/** Represents a file format supported by the backend for upload. */
export interface AvailableFormat {
    id: string;             // Unique identifier for the format (e.g., 'bancolombia_csv_9col')
    description: string;    // User-friendly description (e.g., 'Banco - Bancolombia CSV (9 Col)')
}


// --- Backend Response Types (subset, consider generating from OpenAPI spec if available) ---

export interface UploadResponse {
  filename: string;
  message: string;
  transaction_count: number;
  transactions: Transaction[];
}

export interface ManualReconcileResponse {
  success: boolean;
  message: string;
  matched_pair: MatchedPair | null;
}

export interface ManyToOneReconcileResponse {
  success: boolean;
  message: string;
  matched_pairs_created: MatchedPair[];
}

export interface OneToManyReconcileResponse {
  success: boolean;
  message: string;
  matched_pairs_created: MatchedPair[];
}

export interface AutoReconcileResponse {
    success: boolean;
    message: string;
    matched_pairs: MatchedPair[]; // Only the *newly* matched pairs from this run
}

export interface InitialDataResponse {
  bank_transactions: Transaction[];
  accounting_transactions: Transaction[];
}
```