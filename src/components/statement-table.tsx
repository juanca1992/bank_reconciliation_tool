
"use client";

import type * as React from 'react';
import { useState } from 'react';
import { ArrowUpDown, Filter } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ClientFormattedCurrency } from '@/components/ui/client-formatted-currency'; // Import the new component
import { cn } from '@/lib/utils';
import type { Transaction } from '@/types'; // Ensure path is correct

interface StatementTableProps {
  title: string;
  transactions: Transaction[];
  selectedIds: string[];
  matchedIds: string[]; // IDs of transactions already matched
  onSelectionChange: (selectedIds: string[]) => void;
  className?: string;
  locale?: string; // Added locale prop
  currency?: string; // Added currency prop
}

export function StatementTable({
  title,
  transactions,
  selectedIds,
  matchedIds,
  onSelectionChange,
  className,
  locale = 'en-US', // Default locale
  currency = 'USD', // Default currency
}: StatementTableProps) {
  const [filter, setFilter] = useState('');
  const [sortColumn, setSortColumn] = useState<keyof Transaction | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const handleSelectAll = (checked: boolean | string) => {
    if (checked === true) {
      const allSelectableIds = transactions
        .filter((t) => !matchedIds.includes(t.id)) // Only select unmatched items
        .map((t) => t.id);
      onSelectionChange(allSelectableIds);
    } else {
      onSelectionChange([]);
    }
  };

  const handleRowSelect = (id: string, checked: boolean | string) => {
    if (matchedIds.includes(id)) return; // Prevent selecting matched items

    const newSelectedIds = checked
      ? [...selectedIds, id]
      : selectedIds.filter((selectedId) => selectedId !== id);
    onSelectionChange(newSelectedIds);
  };

   const handleSort = (column: keyof Transaction) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const filteredTransactions = transactions.filter((t) =>
    Object.values(t).some((value) =>
      String(value).toLowerCase().includes(filter.toLowerCase())
    )
  );

  const sortedTransactions = [...filteredTransactions].sort((a, b) => {
    if (!sortColumn) return 0;
    const aValue = a[sortColumn];
    const bValue = b[sortColumn];

    // Handle sorting for amount specifically as numbers
    if (sortColumn === 'amount') {
      return sortDirection === 'asc' ? (aValue as number) - (bValue as number) : (bValue as number) - (aValue as number);
    }

    // Default string/date comparison
    if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
    if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  const isAllSelected = transactions.length > 0 && transactions.every(t => matchedIds.includes(t.id) || selectedIds.includes(t.id)) && transactions.filter(t => !matchedIds.includes(t.id)).length > 0;

  const isIndeterminate = selectedIds.length > 0 && !isAllSelected && selectedIds.length < transactions.filter(t => !matchedIds.includes(t.id)).length;


  return (
    <Card className={cn("w-full shadow-md", className)}>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
         <div className="flex items-center gap-2 pt-2">
             <Filter className="h-4 w-4 text-muted-foreground" />
             <Input
               placeholder="Filtrar transacciones..." // Translated placeholder
               value={filter}
               onChange={(e) => setFilter(e.target.value)}
               className="max-w-sm h-8"
             />
           </div>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead padding="checkbox">
                <Checkbox
                  checked={isAllSelected ? true : (isIndeterminate ? 'indeterminate' : false)}
                  onCheckedChange={handleSelectAll}
                  aria-label="Seleccionar todo" // Translated aria-label
                  disabled={transactions.every(t => matchedIds.includes(t.id))} // Disable if all are matched
                />
              </TableHead>
              <TableHead onClick={() => handleSort('date')}>
                 <Button variant="ghost" size="sm" className="px-2 py-1 h-auto">
                  Fecha {/* Translated header */}
                  <ArrowUpDown className="ml-2 h-3 w-3" />
                 </Button>
              </TableHead>
              <TableHead onClick={() => handleSort('description')}>
                 <Button variant="ghost" size="sm" className="px-2 py-1 h-auto">
                  Descripción {/* Translated header */}
                  <ArrowUpDown className="ml-2 h-3 w-3" />
                  </Button>
              </TableHead>
              <TableHead onClick={() => handleSort('amount')} className="text-right">
                 <Button variant="ghost" size="sm" className="px-2 py-1 h-auto">
                  Monto {/* Translated header */}
                  <ArrowUpDown className="ml-2 h-3 w-3" />
                 </Button>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedTransactions.length > 0 ? (
              sortedTransactions.map((transaction) => {
                 const isSelected = selectedIds.includes(transaction.id);
                 const isMatched = matchedIds.includes(transaction.id);
                 return (
                  <TableRow
                    key={transaction.id}
                    data-state={isSelected ? 'selected' : undefined}
                    className={cn(
                      isMatched ? 'bg-accent/20 hover:bg-accent/30' : '',
                      isSelected && !isMatched ? 'bg-secondary' : ''
                    )}
                  >
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={isSelected || isMatched} // Show check if selected or matched
                        onCheckedChange={(checked) => handleRowSelect(transaction.id, checked)}
                        aria-label={`Seleccionar transacción ${transaction.id}`} // Translated aria-label
                        disabled={isMatched} // Disable checkbox if matched
                      />
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{transaction.date}</TableCell>
                    <TableCell>{transaction.description}</TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      {/* Use the client-side formatting component with passed locale and currency */}
                      <ClientFormattedCurrency amount={transaction.amount} currency={currency} locale={locale} />
                    </TableCell>
                  </TableRow>
                 )
              })
            ) : (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center">
                  No se encontraron transacciones. {/* Translated message */}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
