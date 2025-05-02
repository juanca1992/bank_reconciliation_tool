
"use client";

import { useState, useEffect } from 'react';

interface ClientFormattedCurrencyProps {
  amount: number;
  currency?: string; // e.g., 'USD'
  locale?: string;   // e.g., 'en-US'
  placeholder?: React.ReactNode;
}

export function ClientFormattedCurrency({
  amount,
  currency = 'USD',
  locale, // Let the browser decide default locale if not provided
  placeholder = "...", // Placeholder during initial render/calculation
}: ClientFormattedCurrencyProps) {
  const [formattedAmount, setFormattedAmount] = useState<string | null>(null);

  useEffect(() => {
    // Perform formatting only on the client side after mount
    try {
      const formatted = amount.toLocaleString(locale, {
        style: 'currency',
        currency: currency,
      });
      setFormattedAmount(formatted);
    } catch (error) {
      console.error("Error formatting currency:", error);
      // Fallback to simple display if formatting fails
      setFormattedAmount(`${currency} ${amount.toFixed(2)}`);
    }
  }, [amount, currency, locale]); // Re-run if amount, currency, or locale changes

  // Render placeholder initially, then the formatted amount
  return <>{formattedAmount ?? placeholder}</>;
}
