import type { Transaction, MatchedPair } from '@/types'; // Asegúrate que estos tipos base estén en @/types

// Define the base URL for the FastAPI backend
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// --- Request/Response Types (matching backend models) ---
// (Idealmente, mover a @/types/index.ts)

interface InitialDataResponse {
  bank_transactions: Transaction[];
  accounting_transactions: Transaction[];
}

interface UploadResponse {
  filename: string;
  message: string;
  transaction_count: number;
  transactions: Transaction[];
}

// Para 1 a 1 manual
interface ManualReconcileRequest {
  bank_transaction_id: string; // Corregido
  accounting_transaction_id: string; // Corregido
}

interface ManualReconcileResponse {
  success: boolean;
  message: string; // Corregido
  matched_pair: MatchedPair | null;
}

// Para MUCHOS CONTABLES a UNO BANCARIO manual
interface ManyToOneReconcileRequest {
  bank_transaction_id: string;
  accounting_transaction_ids: string[]; // Lista de IDs contables
}

interface ManyToOneReconcileResponse { // <- Nombre corregido (era ManualReconcileManyToOneResponse)
  success: boolean;
  message: string;
  matched_pairs_created: MatchedPair[]; // Devuelve lista de pares creados
}

// Para Auto (el backend actual NO espera body)
// interface AutoReconcileRequest {
//   bank_transactions: Transaction[];
//   accounting_transactions: Transaction[];
// }

interface AutoReconcileResponse {
    success: boolean;
    message: string;
    matched_pairs: MatchedPair[];
}

// --- Helper function for fetch requests (sin cambios respecto a la última versión) ---
async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const defaultHeaders: HeadersInit = {};

    let bodyToSend = options.body;
    if (!(options.body instanceof FormData) && options.body != null) {
        defaultHeaders['Content-Type'] = 'application/json';
        if (typeof options.body !== 'string') {
           bodyToSend = JSON.stringify(options.body);
        }
    }

    const config: RequestInit = {
      ...options,
      body: bodyToSend,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch (e) {
          errorData = { detail: response.statusText };
        }
        const errorMessage = errorData?.detail ?? `Error fetching ${endpoint}: ${response.statusText}`;
        console.error(`API Error (${response.status}): ${errorMessage}`, errorData);
        const error = new Error(errorMessage);
        (error as any).response = response;
        (error as any).data = errorData;
        throw error;
      }

      if (response.status === 204 || response.headers.get('content-length') === '0') {
        return undefined as T;
      }
      return await response.json() as T;

    } catch (error) {
      console.error(`Network or processing error fetching ${endpoint}:`, error);
      throw error; // Re-lanzar siempre
    }
  }

// --- API Client Functions ---

export const getInitialTransactions = async (): Promise<InitialDataResponse> => {
  // No necesita try/catch aquí
  return await fetchApi<InitialDataResponse>('/api/transactions/initial') ?? { bank_transactions: [], accounting_transactions: [] };
};

export const uploadBankStatement = async (file: File): Promise<UploadResponse> => {
  // No necesita try/catch aquí
  const formData = new FormData();
  formData.append('file', file);
  return await fetchApi<UploadResponse>('/api/transactions/upload/bank', {
    method: 'POST',
    body: formData,
  });
};

export const uploadAccountingStatement = async (file: File): Promise<UploadResponse> => {
  // No necesita try/catch aquí
  const formData = new FormData();
  formData.append('file', file);
  return await fetchApi<UploadResponse>('/api/transactions/upload/accounting', {
    method: 'POST',
    body: formData,
  });
};

export const reconcileManual = async (bankTransactionId: string, accountingTransactionId: string): Promise<ManualReconcileResponse> => {
  // No necesita try/catch aquí
  const requestBody: ManualReconcileRequest = {
    bank_transaction_id: bankTransactionId,
    accounting_transaction_id: accountingTransactionId,
  };
  return await fetchApi<ManualReconcileResponse>('/api/transactions/reconcile/manual', {
    method: 'POST',
    body: requestBody, // fetchApi lo convierte a JSON
  });
};

// *** CORREGIDO: Conciliación Manual Muchos Contables a Uno Bancario ***
export const reconcileManualManyToOne = async (bankTxId: string, accTxIds: string[]): Promise<ManyToOneReconcileResponse> => {
  // No necesita try/catch aquí
  const requestBody: ManyToOneReconcileRequest = {
    bank_transaction_id: bankTxId,           // Un ID bancario
    accounting_transaction_ids: accTxIds,   // Lista de IDs contables
  };
  // Endpoint CORRECTO y body CORRECTO
  return await fetchApi<ManyToOneReconcileResponse>('/api/transactions/reconcile/manual/many_to_one', {
    method: 'POST',
    body: requestBody, // fetchApi lo convierte a JSON
  });
};


// *** CORREGIDO: Conciliación Automática (sin body) ***
export const reconcileAuto = async (): Promise<AutoReconcileResponse> => {
  // No necesita try/catch aquí
  return await fetchApi<AutoReconcileResponse>('/api/transactions/reconcile/auto', {
    method: 'POST',
    // Sin body
  });
};


export const getMatchedPairs = async (): Promise<MatchedPair[]> => {
   // No necesita try/catch aquí
   return await fetchApi<MatchedPair[]>('/api/transactions/matched') ?? [];
};

// QUITÉ LAS FUNCIONES reset... ya que no están implementadas en backend
// export const resetBankTransactions = async (): Promise<void> => { ... };
// export const resetAccountingTransactions = async (): Promise<void> => { ... };