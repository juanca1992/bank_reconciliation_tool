
"use client";

import { useState, useEffect } from 'react';

interface ClientFormattedNumberProps {
  amount: number;
  locale?: string;   // e.g., 'en-US', 'es-ES'
  placeholder?: React.ReactNode;
}

export function ClientFormattedNumber({
  amount,
  locale = 'en-US', // Default locale
  placeholder = "...", // Placeholder during initial render/calculation
}: ClientFormattedNumberProps) {
  const [formattedAmount, setFormattedAmount] = useState<string | null>(null);

  useEffect(() => {
    // Perform formatting only on the client side after mount
    try {
      // Use navigator.language on the client if locale prop isn't explicitly 'en-US' or other provided locale.
      const clientLocale = locale === 'en-US' && typeof navigator !== 'undefined' ? navigator.language : locale;

      const formatted = amount.toLocaleString(clientLocale, {
        style: 'decimal', // Format as a decimal number, not currency
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
      setFormattedAmount(formatted);
    } catch (error) {
      console.error("Error formatting number:", error);
      // Fallback to simple display if formatting fails
       try {
         const fallbackFormatted = amount.toLocaleString('es-ES', {
           style: 'decimal',
           minimumFractionDigits: 2,
           maximumFractionDigits: 2,
         });
          setFormattedAmount(fallbackFormatted);
       } catch (fallbackError) {
           console.error("Fallback number formatting failed:", fallbackError);
           // Final fallback
          setFormattedAmount(amount.toFixed(2));
       }
    }
  }, [amount, locale]); // Re-run if amount or locale changes

  // Render placeholder initially, then the formatted amount
  return <>{formattedAmount ?? placeholder}</>;
}

