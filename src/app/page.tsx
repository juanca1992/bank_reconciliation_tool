
"use client";

import { useState, useEffect } from 'react';
import { StatementUpload } from '@/components/statement-upload';
import { StatementTable } from '@/components/statement-table';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import type { Transaction, MatchedPair } from '@/types';
import { Link2, RefreshCw } from 'lucide-react';
import {
  getInitialTransactions,
  uploadBankStatement,
  uploadAccountingStatement,
  reconcileManual,
  getMatchedPairs,
} from '@/lib/api-client'; // Import API client functions

export default function Home() {
  const [bankTransactions, setBankTransactions] = useState<Transaction[]>([]);
  const [accountingTransactions, setAccountingTransactions] = useState<Transaction[]>([]);
  const [selectedBankIds, setSelectedBankIds] = useState<string[]>([]);
  const [selectedAccountingIds, setSelectedAccountingIds] = useState<string[]>([]);
  const [matchedPairs, setMatchedPairs] = useState<MatchedPair[]>([]);
  const [isLoading, setIsLoading] = useState(true); // Loading state
  const [error, setError] = useState<string | null>(null); // Error state

  const { toast } = useToast();

  // --- Fetch Initial Data ---
  const fetchInitialData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const initialData = await getInitialTransactions();
      setBankTransactions(initialData.bank_transactions || []);
      setAccountingTransactions(initialData.accounting_transactions || []);
      // Optionally fetch already matched pairs if needed on initial load
      // const initialMatched = await getMatchedPairs();
      // setMatchedPairs(initialMatched || []);
    } catch (err) {
      console.error("Error fetching initial data:", err);
      setError("Error al cargar los datos iniciales. Por favor, inténtalo de nuevo.");
      toast({
        title: "Error de Carga",
        description: "No se pudieron cargar las transacciones iniciales.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Fetch data on component mount

  // --- File Upload Handlers ---
  const handleBankFileUpload = async (file: File | null) => {
    if (!file) return;
    setIsLoading(true); // Consider separate loading states per upload if needed
    try {
      const response = await uploadBankStatement(file);
      toast({ title: "Extracto Bancario Subido", description: response.message });
      // Add newly uploaded transactions to the existing list
      setBankTransactions(prev => [...prev, ...response.transactions]);
    } catch (err) {
       const errorMessage = err instanceof Error ? err.message : "Error desconocido al subir el archivo.";
       toast({ title: "Error al Subir", description: errorMessage, variant: "destructive" });
    } finally {
       setIsLoading(false);
    }
  };

  const handleAccountingFileUpload = async (file: File | null) => {
     if (!file) return;
     setIsLoading(true);
    try {
      const response = await uploadAccountingStatement(file);
      toast({ title: "Extracto Contable Subido", description: response.message });
      setAccountingTransactions(prev => [...prev, ...response.transactions]);
    } catch (err) {
       const errorMessage = err instanceof Error ? err.message : "Error desconocido al subir el archivo.";
       toast({ title: "Error al Subir", description: errorMessage, variant: "destructive" });
    } finally {
        setIsLoading(false);
    }
  };

  // --- Manual Match Handler ---
  const handleManualMatch = async () => {
    if (selectedBankIds.length !== 1 || selectedAccountingIds.length !== 1) {
      toast({
        title: "Error de Conciliación",
        description: "Por favor, seleccione exactamente una transacción de cada extracto para conciliar.",
        variant: "destructive",
      });
      return;
    }

    const bankTxId = selectedBankIds[0];
    const accTxId = selectedAccountingIds[0];

    setIsLoading(true);
    try {
      const response = await reconcileManual(bankTxId, accTxId);

      if (response.success && response.matched_pair) {
        // Update matched pairs state
        setMatchedPairs(prev => [...prev, response.matched_pair!]);

        // Remove matched transactions from the displayed lists
        setBankTransactions(prev => prev.filter(tx => tx.id !== bankTxId));
        setAccountingTransactions(prev => prev.filter(tx => tx.id !== accTxId));

        // Clear selections
        setSelectedBankIds([]);
        setSelectedAccountingIds([]);

        toast({
          title: "Conciliación Exitosa",
          description: response.message,
          variant: "default",
          className: "bg-accent text-accent-foreground border-accent",
        });
      } else {
        // Handle potential backend failure message even if success=false isn't expected here
         toast({
           title: "Error de Conciliación",
           description: response.message || "No se pudo completar la conciliación.",
           variant: "destructive",
         });
      }
    } catch (err) {
       const errorMessage = err instanceof Error ? err.message : "Error desconocido al conciliar.";
       toast({
         title: "Error en la Conciliación",
         description: errorMessage,
         variant: "destructive",
       });
    } finally {
       setIsLoading(false);
    }
  };

  // Get flat lists of matched IDs for easy lookup in tables (though now handled by filtering state)
  // const matchedBankIds = matchedPairs.map(p => p.bankTransactionId);
  // const matchedAccountingIds = matchedPairs.map(p => p.accountingTransactionId);

  return (
    <main className="flex min-h-screen flex-col items-center p-4 md:p-12 bg-secondary">
       <h1 className="text-3xl font-bold mb-8 text-primary">Herramienta de Conciliación Bancaria</h1>

       {/* Loading and Error States */}
       {isLoading && (
         <div className="fixed inset-0 bg-background/80 flex items-center justify-center z-50">
            <RefreshCw className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-3 text-lg text-foreground">Cargando...</span>
         </div>
       )}
       {error && (
         <Card className="w-full max-w-6xl mb-8 bg-destructive/10 border-destructive text-destructive-foreground p-4">
            <CardHeader>
               <CardTitle className="text-lg">Error</CardTitle>
            </CardHeader>
            <CardContent>
               <p>{error}</p>
               <Button variant="outline" size="sm" onClick={fetchInitialData} className="mt-4">
                  Reintentar Carga
               </Button>
            </CardContent>
         </Card>
       )}


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
               disabled={isLoading || selectedBankIds.length !== 1 || selectedAccountingIds.length !== 1}
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
           title="Transacciones del Extracto Bancario (Pendientes)"
           transactions={bankTransactions} // Now shows only unmatched from state
           selectedIds={selectedBankIds}
           matchedIds={[]} // Not needed anymore as state holds unmatched
           onSelectionChange={setSelectedBankIds}
           className="bg-card"
           locale="es-ES" // Pass Spanish locale
          />
         <StatementTable
           title="Transacciones del Sistema Contable (Pendientes)"
           transactions={accountingTransactions} // Now shows only unmatched from state
           selectedIds={selectedAccountingIds}
           matchedIds={[]} // Not needed anymore as state holds unmatched
           onSelectionChange={setSelectedAccountingIds}
           className="bg-card"
           locale="es-ES" // Pass Spanish locale
          />
       </div>

        {/* Optional: Display matched pairs fetched from backend */}
        {/* This section could be enhanced to fetch and display matched pairs */}
        {matchedPairs.length > 0 && (
          <>
             <Separator className="my-8 w-full max-w-6xl" />
             <Card className="w-full max-w-6xl mb-8 shadow-md">
                <CardHeader><CardTitle className="text-lg">Transacciones Conciliadas Recientemente</CardTitle></CardHeader>
                <CardContent>
                  <ul>
                    {matchedPairs.map((pair, index) => (
                      <li key={index} className="text-sm mb-1 p-2 border-b">
                        ID Banco: {pair.bankTransactionId} &lt;--&gt; ID Contabilidad: {pair.accountingTransactionId}
                      </li>
                    ))}
                  </ul>
                   {/* Add a button to fetch all matched pairs if needed */}
                </CardContent>
              </Card>
           </>
         )}
    </main>
  );
}

