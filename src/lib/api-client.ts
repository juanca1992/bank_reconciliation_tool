import type { Transaction, MatchedPair } from '@/types';

// Define the base URL for the FastAPI backend
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// --- Request/Response Types ---
// (Recomendado mover a @/types/index.ts)
interface InitialDataResponse {
  bank_transactions: Transaction[];
  accounting_transactions: Transaction[];
}
interface UploadResponse {
  filename: string; message: string; transaction_count: number; transactions: Transaction[];
}
interface ManualReconcileRequest {
  bank_transaction_id: string; accounting_transaction_id: string;
}
interface ManualReconcileResponse {
  success: boolean; message: string; matched_pair: MatchedPair | null;
}
interface ManyToOneReconcileRequest {
  bank_transaction_id: string; accounting_transaction_ids: string[];
}
interface ManyToOneReconcileResponse {
  success: boolean; message: string; matched_pairs_created: MatchedPair[];
}
interface OneToManyReconcileRequest {
  accounting_transaction_id: string; bank_transaction_ids: string[];
}
interface OneToManyReconcileResponse {
  success: boolean; message: string; matched_pairs_created: MatchedPair[];
}
interface AutoReconcileResponse {
  success: boolean; message: string; matched_pairs: MatchedPair[];
}

// --- Helper function for fetch requests ---
async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const defaultHeaders: HeadersInit = {};
    let bodyToSend = options.body;
    if (!(options.body instanceof FormData) && options.body != null) {
        defaultHeaders['Content-Type'] = 'application/json';
        if (typeof options.body !== 'string') { bodyToSend = JSON.stringify(options.body); }
    }
    const config: RequestInit = { ...options, body: bodyToSend, headers: { ...defaultHeaders, ...options.headers } };
    try {
      const response = await fetch(url, config);
      if (!response.ok) {
        let errorData;
        try { errorData = await response.json(); } catch (e) { errorData = { detail: response.statusText }; }
        const errorMessage = errorData?.detail ?? `Error fetching ${endpoint}: ${response.statusText}`;
        console.error(`API Error (${response.status}): ${errorMessage}`, errorData);
        const error = new Error(errorMessage); (error as any).response = response; (error as any).data = errorData;
        throw error;
      }
      if (response.status === 204 || response.headers.get('content-length') === '0') { return undefined as T; }
      return await response.json() as T;
    } catch (error) { console.error(`Network/processing error fetching ${endpoint}:`, error); throw error; }
}

// --- API Client Functions ---
export const getInitialTransactions = async (): Promise<InitialDataResponse> => await fetchApi<InitialDataResponse>('/api/transactions/initial') ?? { bank_transactions: [], accounting_transactions: [] };
export const uploadBankStatement = async (file: File): Promise<UploadResponse> => { const fd = new FormData(); fd.append('file', file); return await fetchApi<UploadResponse>('/api/transactions/upload/bank', { method: 'POST', body: fd }); };
export const uploadAccountingStatement = async (file: File): Promise<UploadResponse> => { const fd = new FormData(); fd.append('file', file); return await fetchApi<UploadResponse>('/api/transactions/upload/accounting', { method: 'POST', body: fd }); };
export const reconcileManual = async (bankId: string, accId: string): Promise<ManualReconcileResponse> => await fetchApi<ManualReconcileResponse>('/api/transactions/reconcile/manual', { method: 'POST', body: { bank_transaction_id: bankId, accounting_transaction_id: accId } });
export const reconcileManualManyToOne = async (bankId: string, accIds: string[]): Promise<ManyToOneReconcileResponse> => await fetchApi<ManyToOneReconcileResponse>('/api/transactions/reconcile/manual/many_to_one', { method: 'POST', body: { bank_transaction_id: bankId, accounting_transaction_ids: accIds } });
export const reconcileManualOneToMany = async (accId: string, bankIds: string[]): Promise<OneToManyReconcileResponse> => await fetchApi<OneToManyReconcileResponse>('/api/transactions/reconcile/manual/one_to_many', { method: 'POST', body: { accounting_transaction_id: accId, bank_transaction_ids: bankIds } });
export const reconcileAuto = async (): Promise<AutoReconcileResponse> => await fetchApi<AutoReconcileResponse>('/api/transactions/reconcile/auto', { method: 'POST' });
export const getMatchedPairs = async (): Promise<MatchedPair[]> => await fetchApi<MatchedPair[]>('/api/transactions/matched') ?? [];