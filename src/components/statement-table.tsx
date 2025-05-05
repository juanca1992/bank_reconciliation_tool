
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
import { ClientFormattedNumber } from '@/components/ui/client-formatted-number';
import { cn } from '@/lib/utils';
import type { Transaction } from '@/types';

interface StatementTableProps {
  title: string;
  transactions: Transaction[]; // These are now expected to be *unmatched* transactions
  selectedIds: string[];
  // matchedIds prop is removed as parent component now filters data
  onSelectionChange: (selectedIds: string[]) => void;
  className?: string;
  locale?: string; // Added locale prop
}

export function StatementTable({
  title,
  transactions,
  selectedIds,
  onSelectionChange,
  className,
  locale = 'es-ES',
}: StatementTableProps) {
  const [filter, setFilter] = useState('');
  const [sortColumn, setSortColumn] = useState<keyof Transaction | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const handleSelectAll = (checked: boolean | string) => {
    if (checked === true) {
      // Select all currently visible and selectable transactions
      const allSelectableIds = sortedTransactions.map((t) => t.id);
      onSelectionChange(allSelectableIds);
    } else {
      onSelectionChange([]);
    }
  };

  const handleRowSelect = (id: string, checked: boolean | string) => {
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

  // Filter transactions based on user input
  const filteredTransactions = transactions.filter((t) =>
    Object.values(t).some((value) =>
      String(value).toLowerCase().includes(filter.toLowerCase())
    )
  );

  // Sort the filtered transactions
  const sortedTransactions = [...filteredTransactions].sort((a, b) => {
    if (!sortColumn) return 0;
    const aValue = a[sortColumn];
    const bValue = b[sortColumn];

    if (sortColumn === 'amount') {
      return sortDirection === 'asc' ? (aValue as number) - (bValue as number) : (bValue as number) - (aValue as number);
    }

    // Default string/date comparison (ensure dates are compared correctly if needed)
     if (sortColumn === 'date') {
       // Simple string comparison works for YYYY-MM-DD format
       return sortDirection === 'asc' ? String(aValue).localeCompare(String(bValue)) : String(bValue).localeCompare(String(aValue));
     }

    if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
    if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  const selectableTransactionsCount = sortedTransactions.length; // All transactions in the table are selectable now
  const isAllSelected = selectableTransactionsCount > 0 && selectedIds.length === selectableTransactionsCount;
  const isIndeterminate = selectedIds.length > 0 && selectedIds.length < selectableTransactionsCount;


  return (
    <Card className={cn("w-full shadow-md", className)}>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
         <div className="flex items-center gap-2 pt-2">
             <Filter className="h-4 w-4 text-muted-foreground" />
             <Input
               placeholder="Filtrar transacciones..."
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
                  aria-label="Seleccionar todo"
                  disabled={selectableTransactionsCount === 0}
                />
              </TableHead>
              <TableHead onClick={() => handleSort('date')}>
                 <Button variant="ghost" size="sm" className="px-2 py-1 h-auto">
                  Fecha
                  <ArrowUpDown className="ml-2 h-3 w-3" />
                 </Button>
              </TableHead>
              <TableHead onClick={() => handleSort('description')}>
                 <Button variant="ghost" size="sm" className="px-2 py-1 h-auto">
                  Descripción
                  <ArrowUpDown className="ml-2 h-3 w-3" />
                  </Button>
              </TableHead>
              <TableHead onClick={() => handleSort('amount')} className="text-right">
                 <Button variant="ghost" size="sm" className="px-2 py-1 h-auto">
                  Monto
                  <ArrowUpDown className="ml-2 h-3 w-3" />
                 </Button>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedTransactions.length > 0 ? (
              sortedTransactions.map((transaction) => {
                 const isSelected = selectedIds.includes(transaction.id);
                 return (
                  <TableRow
                    key={transaction.id}
                    data-state={isSelected ? 'selected' : undefined}
                    className={cn(
                      isSelected ? 'bg-secondary' : '', // Style selected rows
                      'hover:bg-muted/50 cursor-pointer' // Default hover style and indicate clickability
                    )}
                    onClick={() => handleRowSelect(transaction.id, !isSelected)} // Allow clicking row to select/deselect
                  >
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={(checked) => handleRowSelect(transaction.id, checked)}
                        aria-label={`Seleccionar transacción ${transaction.id}`}
                        onClick={(e) => e.stopPropagation()} // Prevent row click handler when clicking checkbox directly
                      />
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{transaction.date}</TableCell>
                    <TableCell>{transaction.description}</TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                       <ClientFormattedNumber amount={transaction.amount} locale={locale} />
                    </TableCell>
                  </TableRow>
                 )
              })
            ) : (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                  No se encontraron transacciones pendientes o que coincidan con el filtro.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
