import type { Transaction, MatchedPair, AvailableFormat } from '@/types'; // Add AvailableFormat

// Define the base URL for the FastAPI backend
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// --- Request/Response Types ---
// (Types related to specific endpoints might be moved closer to their usage or kept here)
interface InitialDataResponse {
  bank_transactions: Transaction[];
  accounting_transactions: Transaction[];
}
interface UploadResponse { // Response for the generic upload endpoint
  filename: string;
  message: string;
  transaction_count: number;
  transactions: Transaction[]; // The processed transactions based on the format
}
interface ManualReconcileRequest {
  bank_transaction_id: string;
  accounting_transaction_id: string;
}
interface ManualReconcileResponse {
  success: boolean;
  message: string;
  matched_pair: MatchedPair | null;
}
interface ManyToOneReconcileRequest {
  bank_transaction_id: string;
  accounting_transaction_ids: string[];
}
interface ManyToOneReconcileResponse {
  success: boolean;
  message: string;
  matched_pairs_created: MatchedPair[];
}
interface OneToManyReconcileRequest {
  accounting_transaction_id: string;
  bank_transaction_ids: string[];
}
interface OneToManyReconcileResponse {
  success: boolean;
  message: string;
  matched_pairs_created: MatchedPair[];
}
interface AutoReconcileResponse {
  success: boolean;
  message: string;
  matched_pairs: MatchedPair[];
}
// No specific request/response type needed for getAvailableFormats if it just returns List[AvailableFormat]

// --- Helper function for fetch requests ---
async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const defaultHeaders: HeadersInit = {};
    let bodyToSend = options.body;

    // Set Content-Type to application/json only if body exists and is not FormData
    if (options.body && !(options.body instanceof FormData)) {
        defaultHeaders['Content-Type'] = 'application/json';
        // Ensure body is stringified if it's an object
        if (typeof options.body !== 'string') {
            bodyToSend = JSON.stringify(options.body);
        }
    }
    // If body is FormData, fetch automatically sets the Content-Type to multipart/form-data

    const config: RequestInit = {
        ...options,
        body: bodyToSend, // Use potentially stringified body
        headers: {
            ...defaultHeaders,
            ...options.headers, // Allow overriding default headers
        },
    };

    console.log(`fetchApi: Calling ${config.method || 'GET'} ${url}`);
     // console.log(`fetchApi: Config:`, JSON.stringify(config, null, 2)); // Be cautious logging body, esp. FormData

    try {
      const response = await fetch(url, config);
      console.log(`fetchApi: Response Status for ${url}: ${response.status}`);

      // Handle non-OK responses
      if (!response.ok) {
        let errorData;
        const contentType = response.headers.get("content-type");
        try {
             // Try to parse JSON error detail only if content type suggests it
            if (contentType && contentType.includes("application/json")) {
                 errorData = await response.json();
            } else {
                 // Otherwise, use status text
                 errorData = { detail: await response.text() || response.statusText };
            }
        } catch (e) {
            // Fallback if parsing fails or content type is unexpected
             errorData = { detail: response.statusText };
             console.error("fetchApi: Failed to parse error response body:", e);
        }

        const errorMessage = errorData?.detail ?? `Error fetching ${endpoint}`;
        console.error(`API Error (${response.status}) for ${url}: ${errorMessage}`, errorData);
        // Create a custom error object to potentially hold more response info
        const error = new Error(errorMessage);
        (error as any).status = response.status;
        (error as any).response = response; // Attach full response if needed
        (error as any).data = errorData;   // Attach parsed error data
        throw error;
      }

      // Handle successful responses with no content (e.g., 204)
      if (response.status === 204 || response.headers.get('content-length') === '0') {
        console.log(`fetchApi: Received empty response (status ${response.status}) for ${url}`);
        return undefined as T; // Or potentially null based on expected type
      }

      // Parse JSON response for successful requests with content
      const jsonData = await response.json() as T;
      // console.log(`fetchApi: Received JSON data for ${url}:`, jsonData); // Log successful data
      return jsonData;

    } catch (error) {
        // Handle network errors or errors thrown from non-OK responses
        if (error instanceof Error && (error as any).status) {
             // If it's our custom error, re-throw it
             throw error;
        } else {
             // Otherwise, it's likely a network error
             console.error(`Network or processing error fetching ${endpoint}:`, error);
             throw new Error(`Network error or failed to process request for ${endpoint}: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
}

// --- API Client Functions ---

/** Fetches the list of available file formats supported by the backend. */
export const getAvailableFormats = async (): Promise<AvailableFormat[]> => {
    return await fetchApi<AvailableFormat[]>('/api/formats') ?? [];
};

/** Uploads a file using a specified format ID. */
export const uploadFile = async (file: File, formatId: string): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    // Pass format_id as a query parameter in the URL
    const endpoint = `/api/transactions/upload?format_id=${encodeURIComponent(formatId)}`;
    return await fetchApi<UploadResponse>(endpoint, {
        method: 'POST',
        body: formData,
        // Content-Type is set automatically by fetch for FormData
    });
};


/** Fetches initial unmatched bank and accounting transactions. */
export const getInitialTransactions = async (): Promise<InitialDataResponse> => {
    const data = await fetchApi<InitialDataResponse>('/api/transactions/initial');
    // Ensure arrays exist even if the backend sends null/undefined
    return {
        bank_transactions: data?.bank_transactions || [],
        accounting_transactions: data?.accounting_transactions || [],
    };
};

/** Performs a manual 1-to-1 reconciliation. */
export const reconcileManual = async (bankId: string, accId: string): Promise<ManualReconcileResponse> => {
    return await fetchApi<ManualReconcileResponse>('/api/transactions/reconcile/manual', {
        method: 'POST',
        body: { bank_transaction_id: bankId, accounting_transaction_id: accId },
    });
};

/** Performs a manual 1-bank-to-many-accounting reconciliation. */
export const reconcileManualManyToOne = async (bankId: string, accIds: string[]): Promise<ManyToOneReconcileResponse> => {
    return await fetchApi<ManyToOneReconcileResponse>('/api/transactions/reconcile/manual/many_to_one', {
        method: 'POST',
        body: { bank_transaction_id: bankId, accounting_transaction_ids: accIds },
    });
};

/** Performs a manual many-bank-to-1-accounting reconciliation. */
export const reconcileManualOneToMany = async (accId: string, bankIds: string[]): Promise<OneToManyReconcileResponse> => {
    return await fetchApi<OneToManyReconcileResponse>('/api/transactions/reconcile/manual/one_to_many', {
        method: 'POST',
        body: { accounting_transaction_id: accId, bank_transaction_ids: bankIds },
    });
};

/** Triggers the automatic reconciliation process. */
export const reconcileAuto = async (): Promise<AutoReconcileResponse> => {
    return await fetchApi<AutoReconcileResponse>('/api/transactions/reconcile/auto', {
        method: 'POST',
    });
};

/** Fetches all currently matched transaction pairs. */
export const getMatchedPairs = async (): Promise<MatchedPair[]> => {
    return await fetchApi<MatchedPair[]>('/api/transactions/matched') ?? [];
};
```