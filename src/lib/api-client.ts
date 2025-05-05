import type { Transaction, MatchedPair } from '@/types';

// Define the base URL for the FastAPI backend
// Use environment variable or default to localhost for development
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// --- Request/Response Types (matching backend models) ---

interface InitialDataResponse {
  bank_transactions: Transaction[];
  accounting_transactions: Transaction[];
}

interface UploadResponse {
  filename: string;
  message: string;
  transactions: Transaction[];
}

interface ManualReconcileRequest {
  bank_transaction_id: str;
  accounting_transaction_id: str;
}

interface ManualReconcileResponse {
  success: boolean;
  message: str;
  matched_pair: MatchedPair | null;
}

// New: Request body for automatic reconciliation
interface AutoReconcileRequest {
  bank_transactions: Transaction[];
  accounting_transactions: Transaction[];
}

// New: Response body for automatic reconciliation
interface AutoReconcileResponse {
    success: boolean;
    message: string;
    matched_pairs: MatchedPair[];
}

// --- Helper function for fetch requests ---
async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultHeaders = {
    'Content-Type': 'application/json',
    // Add other default headers if needed, e.g., Authorization
  };

  // Merge custom options with defaults
  const config: RequestInit = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  // Remove Content-Type header for FormData requests (like file uploads)
  if (options.body instanceof FormData) {
    delete (config.headers as Record<string, string>)['Content-Type'];
  }


  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      // Try to parse error details from the backend response
      let errorData;
      try {
        errorData = await response.json();
      } catch (e) {
        // If response is not JSON, use the status text
        errorData = { detail: response.statusText };
      }
      const errorMessage = errorData?.detail || `Error fetching ${endpoint}: ${response.statusText}`;
      console.error(`API Error (${response.status}): ${errorMessage}`);
      throw new Error(errorMessage);
    }

    // Check if the response has content before trying to parse JSON
    if (response.status === 204 || response.headers.get('content-length') === '0') {
        // Return something sensible for no content, matching expected type T
        // If T can be undefined, return undefined. If T expects an object, maybe return null or an empty object/array.
        // Adjust this based on what your API endpoints return for 204.
        return undefined as T;
    }


    return await response.json() as T;
  } catch (error) {
    console.error(`Network or other error fetching ${endpoint}:`, error);
    // Re-throw the error after logging
    // Ensure the error is an instance of Error for consistent handling
    if (error instanceof Error) {
        throw error;
    } else {
        throw new Error(String(error));
    }
  }
}

// --- API Client Functions ---

export const getInitialTransactions = async (): Promise<InitialDataResponse> => {
  return fetchApi<InitialDataResponse>('/api/transactions/initial');
};

export const uploadBankStatement = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  return fetchApi<UploadResponse>('/api/transactions/upload/bank', {
    method: 'POST',
    body: formData,
    // 'Content-Type' is automatically set by browser for FormData
  });
};

export const uploadAccountingStatement = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  return fetchApi<UploadResponse>('/api/transactions/upload/accounting', {
    method: 'POST',
    body: formData,
     // 'Content-Type' is automatically set by browser for FormData
  });
};

export const reconcileManual = async (bankTransactionId: string, accountingTransactionId: string): Promise<ManualReconcileResponse> => {
  const requestBody: ManualReconcileRequest = {
    bank_transaction_id: bankTransactionId,
    accounting_transaction_id: accountingTransactionId,
  };

  return fetchApi<ManualReconcileResponse>('/api/transactions/reconcile/manual', {
    method: 'POST',
    body: JSON.stringify(requestBody),
  });
};

// New: Function to call the automatic reconciliation endpoint
export const reconcileAuto = async (bankTransactions: Transaction[], accountingTransactions: Transaction[]): Promise<AutoReconcileResponse> => {
  const requestBody: AutoReconcileRequest = {
    bank_transactions: bankTransactions,
    accounting_transactions: accountingTransactions,
  };

  return fetchApi<AutoReconcileResponse>('/api/transactions/reconcile/auto', {
    method: 'POST',
    body: JSON.stringify(requestBody),
  });
};


export const getMatchedPairs = async (): Promise<MatchedPair[]> => {
   return fetchApi<MatchedPair[]>('/api/transactions/matched');
};