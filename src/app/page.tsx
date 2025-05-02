
"use client";

import { useState } from 'react';
import { StatementUpload } from '@/components/statement-upload';
import { StatementTable } from '@/components/statement-table';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import type { Transaction, MatchedPair } from '@/types';
import { Link2 } from 'lucide-react';

// Placeholder data - replace with actual data loading logic
// Translated descriptions
const initialBankTransactions: Transaction[] = [
  { id: 'b1', date: '2024-07-01', description: 'Depósito del Cliente A', amount: 1500.00, type: 'bank' },
  { id: 'b2', date: '2024-07-03', description: 'Retiro - Cajero Automático', amount: -100.00, type: 'bank' },
  { id: 'b3', date: '2024-07-05', description: 'Pago - Proveedor X', amount: -350.50, type: 'bank' },
  { id: 'b4', date: '2024-07-08', description: 'Intereses Ganados', amount: 5.25, type: 'bank' },
];

const initialAccountingTransactions: Transaction[] = [
  { id: 'a1', date: '2024-07-01', description: 'Pago Factura #123', amount: 1500.00, type: 'accounting' },
  { id: 'a2', date: '2024-07-04', description: 'Gasto Suministros Oficina', amount: -100.00, type: 'accounting' },
  { id: 'a3', date: '2024-07-05', description: 'Pago por INV-SUPX', amount: -350.50, type: 'accounting' },
  { id: 'a4', date: '2024-07-09', description: 'Ingreso Intereses Bancarios', amount: 5.25, type: 'accounting' },
];


export default function Home() {
  const [bankTransactions, setBankTransactions] = useState<Transaction[]>(initialBankTransactions);
  const [accountingTransactions, setAccountingTransactions] = useState<Transaction[]>(initialAccountingTransactions);
  const [selectedBankIds, setSelectedBankIds] = useState<string[]>([]);
  const [selectedAccountingIds, setSelectedAccountingIds] = useState<string[]>([]);
  const [matchedPairs, setMatchedPairs] = useState<MatchedPair[]>([]); // Stores matched pairs

  const { toast } = useToast();

  const handleBankFileUpload = (file: File | null) => {
    console.log("Archivo bancario subido:", file?.name);
    // Add logic here to parse the file and update bankTransactions state
    if (file) {
       toast({ title: "Extracto Bancario Subido", description: file.name });
       // Example: Placeholder data update on upload (replace with actual parsing)
       // setBankTransactions(parsedBankData);
    }
  };

  const handleAccountingFileUpload = (file: File | null) => {
    console.log("Archivo contable subido:", file?.name);
    // Add logic here to parse the file and update accountingTransactions state
    if (file) {
      toast({ title: "Extracto Contable Subido", description: file.name });
      // Example: Placeholder data update on upload (replace with actual parsing)
      // setAccountingTransactions(parsedAccountingData);
    }
  };

  const handleManualMatch = () => {
    if (selectedBankIds.length !== 1 || selectedAccountingIds.length !== 1) {
      toast({
        title: "Error de Conciliación",
        description: "Por favor, seleccione exactamente una transacción de cada extracto para conciliar.",
        variant: "destructive",
      });
      return;
    }

    const bankTx = bankTransactions.find(tx => tx.id === selectedBankIds[0]);
    const accTx = accountingTransactions.find(tx => tx.id === selectedAccountingIds[0]);

    if (!bankTx || !accTx) {
       toast({ title: "Error", description: "Transacción seleccionada no encontrada.", variant: "destructive" });
       return;
    }

    // Basic check (can be more sophisticated)
    if (bankTx.amount !== accTx.amount) {
       toast({
         title: "Posible Discrepancia",
         description: `Los montos difieren (${bankTx.amount.toFixed(2)} vs ${accTx.amount.toFixed(2)}). ¿Conciliar de todas formas?`,
         // Optionally add an action button for confirmation
       });
       // For now, let's allow mismatch for demonstration
    }

    const newMatch: MatchedPair = {
      bankTransactionId: selectedBankIds[0],
      accountingTransactionId: selectedAccountingIds[0],
    };

    setMatchedPairs([...matchedPairs, newMatch]);
    // Clear selections after matching
    setSelectedBankIds([]);
    setSelectedAccountingIds([]);

    toast({
      title: "Conciliación Exitosa",
      description: `Conciliado ${bankTx.description} con ${accTx.description}`,
      variant: "default", // or use 'success' if you add that variant
      className: "bg-accent text-accent-foreground border-accent", // Use gold accent for success
    });
  };

  // Get flat lists of matched IDs for easy lookup in tables
  const matchedBankIds = matchedPairs.map(p => p.bankTransactionId);
  const matchedAccountingIds = matchedPairs.map(p => p.accountingTransactionId);

  return (
    <main className="flex min-h-screen flex-col items-center p-4 md:p-12 bg-secondary">
       <h1 className="text-3xl font-bold mb-8 text-primary">Herramienta de Conciliación Bancaria</h1>

       {/* Upload Section */}
       <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-6xl mb-8">
         <StatementUpload
           title="Subir Extracto Bancario"
           onFileUpload={handleBankFileUpload}
           className="bg-card"
          />
         <StatementUpload
           title="Subir Extracto del Sistema Contable"
           onFileUpload={handleAccountingFileUpload}
           className="bg-card"
          />
       </div>

       <Separator className="my-8 w-full max-w-6xl" />

        {/* Matching Controls */}
       <Card className="w-full max-w-6xl mb-8 shadow-md">
          <CardHeader>
             <CardTitle className="text-lg">Conciliación Manual</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-center">
             <Button
               onClick={handleManualMatch}
               disabled={selectedBankIds.length !== 1 || selectedAccountingIds.length !== 1}
               className="bg-accent text-accent-foreground hover:bg-accent/90"
              >
                <Link2 className="mr-2 h-4 w-4" />
                Conciliar Transacciones Seleccionadas
             </Button>
          </CardContent>
       </Card>

       {/* Statement Tables Section */}
       <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full max-w-6xl">
         <StatementTable
           title="Transacciones del Extracto Bancario"
           transactions={bankTransactions}
           selectedIds={selectedBankIds}
           matchedIds={matchedBankIds}
           onSelectionChange={setSelectedBankIds}
           className="bg-card"
           locale="es-ES" // Pass Spanish locale
           currency="EUR" // Use Euro for example
          />
         <StatementTable
           title="Transacciones del Sistema Contable"
           transactions={accountingTransactions}
           selectedIds={selectedAccountingIds}
           matchedIds={matchedAccountingIds}
           onSelectionChange={setSelectedAccountingIds}
           className="bg-card"
           locale="es-ES" // Pass Spanish locale
           currency="EUR" // Use Euro for example
          />
       </div>

        {/* Optional: Display matched pairs */}
        {/*
        <Separator className="my-8 w-full max-w-6xl" />
        <Card className="w-full max-w-6xl mb-8 shadow-md">
           <CardHeader><CardTitle className="text-lg">Transacciones Conciliadas</CardTitle></CardHeader>
           <CardContent>
             {matchedPairs.length > 0 ? (
               <ul>
                 {matchedPairs.map((pair, index) => (
                   <li key={index} className="text-sm mb-1 p-2 border-b">
                     ID Banco: {pair.bankTransactionId} &lt;--&gt; ID Contabilidad: {pair.accountingTransactionId}
                   </li>
                 ))}
               </ul>
             ) : (
               <p className="text-muted-foreground text-center">Aún no hay transacciones conciliadas.</p>
             )}
           </CardContent>
         </Card>
         */}
    </main>
  );
}
