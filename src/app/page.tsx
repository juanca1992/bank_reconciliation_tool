
"use client";

import { useState, useEffect } from 'react';
import { StatementUpload } from '@/components/statement-upload';
import { StatementTable } from '@/components/statement-table';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import type { Transaction, MatchedPair } from '@/types';
import { Link2, RefreshCw, Sparkles } from 'lucide-react'; // Added Sparkles icon
import {
  getInitialTransactions,
  uploadBankStatement,
  uploadAccountingStatement,
  reconcileManual,
  reconcileAuto, // Import the new auto reconcile function
  getMatchedPairs,
} from '@/lib/api-client'; // Import API client functions

export default function Home() {
  const [bankTransactions, setBankTransactions] = useState<Transaction[]>([]);
  const [accountingTransactions, setAccountingTransactions] = useState<Transaction[]>([]);
  const [selectedBankIds, setSelectedBankIds] = useState<string[]>([]);
  const [selectedAccountingIds, setSelectedAccountingIds] = useState<string[]>([]);
  const [matchedPairs, setMatchedPairs] = useState<MatchedPair[]>([]);
  const [isLoading, setIsLoading] = useState(true); // Loading state for initial load/manual
  const [isAutoReconciling, setIsAutoReconciling] = useState(false); // Separate loading state for auto
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
      // Reset matched pairs on initial fetch or refresh if desired
      // Keep existing matches if needed, fetch them if not already loaded
      // const initialMatched = await getMatchedPairs();
      // setMatchedPairs(initialMatched || []);
      setMatchedPairs([]); // Assuming we start fresh on reload
      setSelectedBankIds([]); // Clear selections on reload
      setSelectedAccountingIds([]); // Clear selections on reload

    } catch (err) {
      console.error("Error fetching initial data:", err);
      const errorMessage = err instanceof Error ? err.message : "Error desconocido al cargar datos.";
      setError(`Error al cargar los datos iniciales: ${errorMessage}. Por favor, inténtalo de nuevo.`);
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
    setIsLoading(true);
    setError(null); // Clear previous errors
    try {
      const response = await uploadBankStatement(file);
      console.log("Bank upload response:", response); // Log response for debugging
      if (response && Array.isArray(response.transactions)) {
         // Add only new transactions that don't already exist by ID
         const existingIds = new Set(bankTransactions.map(tx => tx.id));
         const newUniqueTransactions = response.transactions.filter(tx => !existingIds.has(tx.id));
         setBankTransactions(prev => [...prev, ...newUniqueTransactions]);
        toast({ title: "Extracto Bancario Subido", description: response.message });
      } else {
        console.error("Invalid bank upload response format:", response);
        toast({ title: "Error al Procesar", description: "Formato de respuesta inesperado del servidor.", variant: "destructive" });
      }
    } catch (err) {
       console.error("Error uploading bank statement:", err);
       const errorMessage = err instanceof Error ? err.message : "Error desconocido al subir el archivo.";
       toast({ title: "Error al Subir", description: `Error al subir extracto bancario: ${errorMessage}`, variant: "destructive" });
       setError(`Error al subir extracto bancario: ${errorMessage}`);
    } finally {
       setIsLoading(false);
    }
  };

  const handleAccountingFileUpload = async (file: File | null) => {
     if (!file) return;
     setIsLoading(true);
     setError(null); // Clear previous errors
    try {
      const response = await uploadAccountingStatement(file);
       console.log("Accounting upload response:", response); // Log response for debugging
      if (response && Array.isArray(response.transactions)) {
        // Add only new transactions that don't already exist by ID
        const existingIds = new Set(accountingTransactions.map(tx => tx.id));
        const newUniqueTransactions = response.transactions.filter(tx => !existingIds.has(tx.id));
        setAccountingTransactions(prev => [...prev, ...newUniqueTransactions]);
        toast({ title: "Extracto Contable Subido", description: response.message });
      } else {
         console.error("Invalid accounting upload response format:", response);
         toast({ title: "Error al Procesar", description: "Formato de respuesta inesperado del servidor.", variant: "destructive" });
      }
    } catch (err) {
        console.error("Error uploading accounting statement:", err);
       const errorMessage = err instanceof Error ? err.message : "Error desconocido al subir el archivo.";
       toast({ title: "Error al Subir", description: `Error al subir extracto contable: ${errorMessage}`, variant: "destructive" });
       setError(`Error al subir extracto contable: ${errorMessage}`);
    } finally {
        setIsLoading(false);
    }
  };

  // --- Manual Match Handler ---
  const handleManualMatch = async () => {
    if (selectedBankIds.length !== 1 || selectedAccountingIds.length !== 1) {
      toast({
        title: "Error de Conciliación Manual",
        description: "Por favor, seleccione exactamente una transacción de cada extracto para conciliar.",
        variant: "destructive",
      });
      return;
    }

    const bankTxId = selectedBankIds[0];
    const accTxId = selectedAccountingIds[0];

    setIsLoading(true);
    setError(null); // Clear previous errors
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
          title: "Conciliación Manual Exitosa",
          description: response.message,
          variant: "default",
          className: "bg-accent text-accent-foreground border-accent",
        });
      } else {
         // Display backend message if available, otherwise generic error
         const errorDesc = response.message || "No se pudo completar la conciliación.";
         toast({
           title: "Error de Conciliación Manual",
           description: errorDesc,
           variant: "destructive",
         });
         setError(errorDesc);
      }
    } catch (err) {
       console.error("Error during manual reconciliation:", err);
       const errorMessage = err instanceof Error ? err.message : "Error desconocido al conciliar manualmente.";
       toast({
         title: "Error en Conciliación Manual",
         description: errorMessage,
         variant: "destructive",
       });
       setError(`Error en conciliación manual: ${errorMessage}`);
    } finally {
       setIsLoading(false);
    }
  };

  // --- Automatic Match Handler ---
   const handleAutoMatch = async () => {
      if (bankTransactions.length === 0 || accountingTransactions.length === 0) {
        toast({
           title: "Conciliación Automática",
           description: "Se requieren transacciones pendientes en ambos extractos para iniciar la conciliación automática.",
           variant: "default",
         });
        return;
      }

      setIsAutoReconciling(true);
      setError(null); // Clear previous errors
      try {
        // Pass the current lists of unmatched transactions to the backend
        const response = await reconcileAuto(bankTransactions, accountingTransactions);

        if (response.success) {
          if (response.matched_pairs.length > 0) {
             // Update matched pairs state with newly found matches
             setMatchedPairs(prev => [...prev, ...response.matched_pairs]);

             // Update the bank and accounting transaction lists to remove the newly matched ones
             const newlyMatchedBankIds = new Set(response.matched_pairs.map(p => p.bankTransactionId));
             const newlyMatchedAccIds = new Set(response.matched_pairs.map(p => p.accountingTransactionId));

             setBankTransactions(prev => prev.filter(tx => !newlyMatchedBankIds.has(tx.id)));
             setAccountingTransactions(prev => prev.filter(tx => !newlyMatchedAccIds.has(tx.id)));

             // Clear selections
             setSelectedBankIds([]);
             setSelectedAccountingIds([]);
          }

          toast({
            title: "Conciliación Automática Completada",
            description: response.message, // Message from backend indicates matches found or not
            variant: "default", // Or a success variant if you have one
            className: "bg-primary text-primary-foreground border-primary",
          });
        } else {
            // Display backend message if available, otherwise generic error
            const errorDesc = response.message || "No se pudo completar la conciliación automática.";
           toast({
             title: "Error de Conciliación Automática",
             description: errorDesc,
             variant: "destructive",
           });
           setError(errorDesc);
        }
      } catch (err) {
         console.error("Error during automatic reconciliation:", err);
         const errorMessage = err instanceof Error ? err.message : "Error desconocido al ejecutar la conciliación automática.";
         toast({
           title: "Error en Conciliación Automática",
           description: errorMessage,
           variant: "destructive",
         });
         setError(`Error en conciliación automática: ${errorMessage}`);
      } finally {
         setIsAutoReconciling(false);
      }
    };

  return (
    <main className="flex min-h-screen flex-col items-center p-4 md:p-12 bg-secondary">
       <h1 className="text-3xl font-bold mb-8 text-primary">Herramienta de Conciliación Bancaria</h1>

       {/* Loading and Error States */}
       {(isLoading || isAutoReconciling) && (
         <div className="fixed inset-0 bg-background/80 flex items-center justify-center z-50">
            <RefreshCw className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-3 text-lg text-foreground">{isAutoReconciling ? 'Conciliando automáticamente...' : 'Cargando...'}</span>
         </div>
       )}
       {error && (
         <Card className="w-full max-w-6xl mb-8 bg-destructive/10 border-destructive text-destructive-foreground p-4">
            <CardHeader>
               <CardTitle className="text-lg text-destructive">Error</CardTitle> {/* Ensure title uses destructive color */}
            </CardHeader>
            <CardContent>
               <p>{error}</p>
               <Button variant="outline" size="sm" onClick={fetchInitialData} className="mt-4 border-destructive text-destructive hover:bg-destructive/10">
                  Reintentar Carga Inicial
               </Button>
               {/* Optionally add a button to clear the error */}
               <Button variant="ghost" size="sm" onClick={() => setError(null)} className="mt-4 ml-2 text-muted-foreground">
                  Descartar
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
           disabled={isLoading || isAutoReconciling} // Disable upload while loading/matching
          />
         <StatementUpload
           title="Subir Extracto del Sistema Contable"
           onFileUpload={handleAccountingFileUpload}
           className="bg-card"
           disabled={isLoading || isAutoReconciling} // Disable upload while loading/matching
          />
       </div>

       <Separator className="my-8 w-full max-w-6xl" />

        {/* Matching Controls */}
       <Card className="w-full max-w-6xl mb-8 shadow-md">
          <CardHeader>
             <CardTitle className="text-lg">Iniciar Conciliación</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col sm:flex-row items-center justify-center gap-4">
             {/* Manual Match Button */}
             <Button
               onClick={handleManualMatch}
               disabled={isLoading || isAutoReconciling || selectedBankIds.length !== 1 || selectedAccountingIds.length !== 1}
               className="bg-accent text-accent-foreground hover:bg-accent/90"
               title="Seleccione una transacción de cada tabla para activar"
              >
                <Link2 className="mr-2 h-4 w-4" />
                Conciliar Manualmente (Seleccionados)
             </Button>

              {/* Automatic Match Button */}
              <Button
                onClick={handleAutoMatch}
                disabled={isLoading || isAutoReconciling || bankTransactions.length === 0 || accountingTransactions.length === 0}
                className="bg-primary text-primary-foreground hover:bg-primary/90"
                title="Conciliar automáticamente las transacciones pendientes"
              >
                 <Sparkles className="mr-2 h-4 w-4" />
                 Conciliar Automáticamente (Simulado)
              </Button>
          </CardContent>
       </Card>

       {/* Statement Tables Section */}
       <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full max-w-6xl">
         <StatementTable
           title="Transacciones Bancarias (Pendientes)" // Updated title
           transactions={bankTransactions}
           selectedIds={selectedBankIds}
           onSelectionChange={setSelectedBankIds}
           className="bg-card"
           locale="es-ES" // Pass Spanish locale
          />
         <StatementTable
           title="Transacciones Contables (Pendientes)" // Updated title
           transactions={accountingTransactions}
           selectedIds={selectedAccountingIds}
           onSelectionChange={setSelectedAccountingIds}
           className="bg-card"
           locale="es-ES" // Pass Spanish locale
          />
       </div>

        {/* Display matched pairs */}
        {matchedPairs.length > 0 && (
          <>
             <Separator className="my-8 w-full max-w-6xl" />
             <Card className="w-full max-w-6xl mb-8 shadow-md">
                <CardHeader><CardTitle className="text-lg">Transacciones Conciliadas</CardTitle></CardHeader>
                <CardContent>
                  <ul className="max-h-48 overflow-y-auto text-sm space-y-1">
                    {matchedPairs.map((pair, index) => (
                      <li key={`${pair.bankTransactionId}-${pair.accountingTransactionId}-${index}`} className="p-2 border-b text-muted-foreground">
                        Conciliado: Banco ID <code className="bg-muted px-1 rounded">{pair.bankTransactionId}</code> con Contabilidad ID <code className="bg-muted px-1 rounded">{pair.accountingTransactionId}</code>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
           </>
         )}
    </main>
  );
}
