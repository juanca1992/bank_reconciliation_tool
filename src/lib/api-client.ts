import type { Transaction, MatchedPair } from '@/types';

// Define the base URL for the FastAPI backend
// Use environment variable or default to localhost for development
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Type for the initial data response from the backend
interface InitialDataResponse {
  bank_transactions: Transaction[];
  accounting_transactions: Transaction[];
}

// Type for the file upload response from the backend
interface UploadResponse {
  filename: string;
  message: string;
  transactions: Transaction[]; // Return the parsed transactions
}

// Type for the manual reconciliation request body
interface ManualReconcileRequest {
  bank_transaction_id: string;
  accounting_transaction_id: string;
}

// Type for the reconciliation response from the backend
interface ReconcileResponse {
  success: boolean;
  message: string;
  matched_pair: MatchedPair | null;
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
      console.error(`API Error (${response.status}): ${errorData?.detail || 'Unknown error'}`);
      throw new Error(errorData?.detail || `Error fetching ${endpoint}: ${response.statusText}`);
    }

    // Check if the response has content before trying to parse JSON
    if (response.status === 204 || response.headers.get('content-length') === '0') {
        return undefined as T; // Or null, depending on expected return type for no content
    }


    return await response.json() as T;
  } catch (error) {
    console.error(`Network or other error fetching ${endpoint}:`, error);
    // Re-throw the error after logging
    throw error;
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

export const reconcileManual = async (bankTransactionId: string, accountingTransactionId: string): Promise<ReconcileResponse> => {
  const requestBody: ManualReconcileRequest = {
    bank_transaction_id: bankTransactionId,
    accounting_transaction_id: accountingTransactionId,
  };

  return fetchApi<ReconcileResponse>('/api/transactions/reconcile/manual', {
    method: 'POST',
    body: JSON.stringify(requestBody),
  });
};

export const getMatchedPairs = async (): Promise<MatchedPair[]> => {
   return fetchApi<MatchedPair[]>('/api/transactions/matched');
};
