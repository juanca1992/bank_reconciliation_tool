
export interface Transaction {
  id: string;
  date: string; // Consider using Date object if doing date manipulation
  description: string;
  amount: number; // Use positive for credits, negative for debits
  type: 'bank' | 'accounting';
}

export interface MatchedPair {
  bankTransactionId: string;
  accountingTransactionId: string;
}
