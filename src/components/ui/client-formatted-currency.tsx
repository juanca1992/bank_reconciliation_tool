
"use client";

import { useState, useEffect } from 'react';

interface ClientFormattedCurrencyProps {
  amount: number;
  currency?: string; // e.g., 'USD', 'EUR'
  locale?: string;   // e.g., 'en-US', 'es-ES'
  placeholder?: React.ReactNode;
}

export function ClientFormattedCurrency({
  amount,
  currency = 'USD', // Default currency
  locale = 'en-US', // Default locale
  placeholder = "...", // Placeholder during initial render/calculation
}: ClientFormattedCurrencyProps) {
  const [formattedAmount, setFormattedAmount] = useState<string | null>(null);

  useEffect(() => {
    // Perform formatting only on the client side after mount
    try {
      // Use navigator.language on the client if locale prop isn't explicitly 'en-US' or other provided locale.
      // This aims to use the browser's default language setting for better localization,
      // unless a specific locale is passed down.
      const clientLocale = locale === 'en-US' && typeof navigator !== 'undefined' ? navigator.language : locale;

      const formatted = amount.toLocaleString(clientLocale, {
        style: 'currency',
        currency: currency,
      });
      setFormattedAmount(formatted);
    } catch (error) {
      console.error("Error formatting currency:", error);
      // Fallback to simple display if formatting fails, try Spanish format as fallback
      try {
        const fallbackFormatted = amount.toLocaleString('es-ES', {
          style: 'currency',
          currency: currency,
        });
         setFormattedAmount(fallbackFormatted);
      } catch (fallbackError) {
          console.error("Fallback currency formatting failed:", fallbackError);
          // Final fallback
         setFormattedAmount(`${currency} ${amount.toFixed(2)}`);
      }
    }
  }, [amount, currency, locale]); // Re-run if amount, currency, or locale changes

  // Render placeholder initially, then the formatted amount
  return <>{formattedAmount ?? placeholder}</>;
}
