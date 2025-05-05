"use client";

import { useState, useEffect } from 'react';
import { StatementUpload } from '@/components/statement-upload';
import { StatementTable } from '@/components/statement-table';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
// Asegúrate que estos tipos (especialmente los nuevos de respuesta) estén definidos en @/types
import type { Transaction, MatchedPair, ManualReconcileResponse, ManyToOneReconcileResponse, OneToManyReconcileResponse } from '@/types';
import { Link2, RefreshCw, Sparkles, Download } from 'lucide-react'; // Añadido Download
import {
  getInitialTransactions,
  uploadBankStatement,
  uploadAccountingStatement,
  reconcileManual,         // Para 1 a 1
  reconcileManualManyToOne, // Para 1 banco, muchos contables
  reconcileManualOneToMany, // Para muchos bancos, 1 contable
  reconcileAuto,
  getMatchedPairs,
} from '@/lib/api-client'; // Importar todas las funciones necesarias

export default function Home() {
  const [bankTransactions, setBankTransactions] = useState<Transaction[]>([]);
  const [accountingTransactions, setAccountingTransactions] = useState<Transaction[]>([]);
  const [selectedBankIds, setSelectedBankIds] = useState<string[]>([]);
  const [selectedAccountingIds, setSelectedAccountingIds] = useState<string[]>([]);
  const [matchedPairs, setMatchedPairs] = useState<MatchedPair[]>([]);
  const [isLoading, setIsLoading] = useState(true); // Loading general o para acciones manuales
  const [isAutoReconciling, setIsAutoReconciling] = useState(false); // Loading específico para auto
  const [error, setError] = useState<string | null>(null);

  const { toast } = useToast();

  // --- Fetch Initial Data ---
  const fetchInitialData = async () => {
    console.log("fetchInitialData: function starting");
    setIsLoading(true);
    setError(null);
    try {
      const [initialData, initialMatched] = await Promise.all([
        getInitialTransactions(),
        getMatchedPairs()
      ]);
      console.log("Initial data fetched:", initialData);
      setBankTransactions(initialData?.bank_transactions || []);
      setAccountingTransactions(initialData?.accounting_transactions || []);
      console.log("Initial matched pairs fetched:", initialMatched);
      setMatchedPairs(initialMatched || []);
      setSelectedBankIds([]);
      setSelectedAccountingIds([]);
    } catch (err) {
      console.error("Error fetching initial data:", err);
      const errorMsg = err instanceof Error ? err.message : "Error desconocido";
      const displayError = `Error al cargar datos iniciales: ${errorMsg}. Inténtalo de nuevo.`;
      setError(displayError);
      toast({ title: "Error de Carga", description: displayError, variant: "destructive" });
    } finally {
      setIsLoading(false);
      console.log("fetchInitialData: function finished");
    }
  };

  useEffect(() => {
    console.log("Mount useEffect: fetching initial data");
    fetchInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- File Upload Handlers ---
  const handleBankFileUpload = async (file: File | null) => {
    if (!file) return;
    setIsLoading(true); setError(null);
    try {
      const response = await uploadBankStatement(file);
      console.log("Bank upload response:", response);
      if (response?.transactions) {
        setBankTransactions(response.transactions);
        toast({ title: "Extracto Bancario Subido", description: `${response.message}. ${response.transaction_count} transacciones.` });
      } else {
         toast({ title: "Extracto Bancario Procesado", description: response?.message ?? "Respuesta inesperada." });
         if (response) await fetchInitialData(); // Recarga si fue ok pero sin datos?
      }
      setSelectedBankIds([]);
    } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Error desconocido";
        toast({ title: "Error al Subir Banco", description: errorMessage, variant: "destructive" });
        setError(`Error al subir extracto bancario: ${errorMessage}`);
    } finally { setIsLoading(false); }
  };

  const handleAccountingFileUpload = async (file: File | null) => {
      if (!file) return;
      setIsLoading(true); setError(null);
    try {
      const response = await uploadAccountingStatement(file);
      console.log("Accounting upload response:", response);
      if (response?.transactions) {
        setAccountingTransactions(response.transactions);
        toast({ title: "Extracto Contable Subido", description: `${response.message}. ${response.transaction_count} transacciones.` });
      } else {
        toast({ title: "Extracto Contable Procesado", description: response?.message ?? "Respuesta inesperada." });
        if (response) await fetchInitialData();
      }
      setSelectedAccountingIds([]);
    } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Error desconocido";
        toast({ title: "Error al Subir Contable", description: errorMessage, variant: "destructive" });
        setError(`Error al subir extracto contable: ${errorMessage}`);
    } finally { setIsLoading(false); }
  };

  // --- Combined Manual Match Handler ---
  const handleManualMatch = async () => {
    const numBankSelected = selectedBankIds.length;
    const numAccSelected = selectedAccountingIds.length;
    let scenario: '1-1' | '1-ManyAcc' | 'ManyBank-1' | 'Invalid' = 'Invalid';
    if (numBankSelected === 1 && numAccSelected === 1) scenario = '1-1';
    else if (numBankSelected === 1 && numAccSelected > 1) scenario = '1-ManyAcc';
    else if (numBankSelected > 1 && numAccSelected === 1) scenario = 'ManyBank-1';

    if (scenario === 'Invalid') {
      toast({ title: "Error Selección Manual", description: "Selección inválida. Elija: (1 Banco y 1 Contable) O (1 Banco y Varios Contables) O (Varios Bancos y 1 Contable).", variant: "destructive" });
      return;
    }

    setIsLoading(true); setError(null);
    try {
      let response: ManualReconcileResponse | ManyToOneReconcileResponse | OneToManyReconcileResponse | null = null;
      let newMatchedPairs: MatchedPair[] = [];
      let message = ""; let success = false;

      switch (scenario) {
        case '1-1': {
          const bankTxId = selectedBankIds[0]; const accTxId = selectedAccountingIds[0];
          console.log(`API Call (${scenario}): B:${bankTxId}, A:${accTxId}`);
          response = await reconcileManual(bankTxId, accTxId);
          if (response?.success && response.matched_pair) { newMatchedPairs = [response.matched_pair]; success = true; }
          message = response?.message || `Error ${scenario}.`; break;
        }
        case '1-ManyAcc': {
          const bankTxId = selectedBankIds[0]; const accTxIds = selectedAccountingIds;
          console.log(`API Call (${scenario}): B:${bankTxId}, A:[${accTxIds.join(',')}]`);
          response = await reconcileManualManyToOne(bankTxId, accTxIds);
          if (response?.success && response.matched_pairs_created) { newMatchedPairs = response.matched_pairs_created; success = true; }
          message = response?.message || `Error ${scenario}.`; break;
        }
        case 'ManyBank-1': {
          const accTxId = selectedAccountingIds[0]; const bankTxIds = selectedBankIds;
          console.log(`API Call (${scenario}): B:[${bankTxIds.join(',')}], A:${accTxId}`);
          response = await reconcileManualOneToMany(accTxId, bankTxIds);
          if (response?.success && response.matched_pairs_created) { newMatchedPairs = response.matched_pairs_created; success = true; }
          message = response?.message || `Error ${scenario}.`; break;
        }
      }

      if (success && newMatchedPairs.length > 0) {
        setMatchedPairs(prev => [...prev, ...newMatchedPairs]);
        const justMatchedBankIds = new Set(newMatchedPairs.map(p => p.bankTransactionId));
        const justMatchedAccIds = new Set(newMatchedPairs.map(p => p.accountingTransactionId));
        setBankTransactions(prev => prev.filter(tx => !justMatchedBankIds.has(tx.id)));
        setAccountingTransactions(prev => prev.filter(tx => !justMatchedAccIds.has(tx.id)));
        setSelectedBankIds([]); setSelectedAccountingIds([]);
        toast({ title: `Conciliación Manual Exitosa (${scenario})`, description: message });
      } else { throw new Error(message); }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Error desconocido.";
      toast({ title: "Error Conciliación Manual", description: errorMessage, variant: "destructive" });
      setError(`Error conciliación manual: ${errorMessage}`);
    } finally { setIsLoading(false); }
  };

  // --- Automatic Match Handler ---
   const handleAutoMatch = async () => {
     if (bankTransactions.length === 0 || accountingTransactions.length === 0) {
       toast({ title: "Conciliación Automática", description: "Se requieren transacciones pendientes.", variant: "default" });
       return;
     }
     setIsAutoReconciling(true); setError(null);
     try {
       console.log("Attempting automatic reconcile...");
       const response = await reconcileAuto();
       console.log("Auto reconcile response:", response);
       if (response?.success) {
         if (response.matched_pairs?.length > 0) {
           setMatchedPairs(prev => [...prev, ...response.matched_pairs]);
           const newlyMatchedBankIds = new Set(response.matched_pairs.map(p => p.bankTransactionId));
           const newlyMatchedAccIds = new Set(response.matched_pairs.map(p => p.accountingTransactionId));
           setBankTransactions(prev => prev.filter(tx => !newlyMatchedBankIds.has(tx.id)));
           setAccountingTransactions(prev => prev.filter(tx => !newlyMatchedAccIds.has(tx.id)));
           setSelectedBankIds([]); setSelectedAccountingIds([]);
           toast({ title: "Conciliación Automática Completada", description: response.message, className: "bg-primary text-primary-foreground border-primary" });
         } else {
           toast({ title: "Conciliación Automática Completada", description: response.message ?? "No se encontraron nuevas coincidencias.", variant: "default" });
         }
       } else {
         const errorDesc = response?.message || "No se pudo completar.";
         toast({ title: "Error Conciliación Automática", description: errorDesc, variant: "destructive" }); setError(errorDesc);
       }
     } catch (err) {
       const errorMessage = err instanceof Error ? err.message : "Error desconocido.";
       toast({ title: "Error Conciliación Automática", description: errorMessage, variant: "destructive" }); setError(`Error auto: ${errorMessage}`);
     } finally { setIsAutoReconciling(false); }
   };

   // --- Download Handler ---
   const handleDownload = () => {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const downloadUrl = `${baseUrl}/api/reconciliation/download`;
        console.log(`Initiating download from: ${downloadUrl}`);
        toast({ title: "Descarga Iniciada", description: "Preparando archivo Excel..." });
        window.open(downloadUrl, '_blank'); // Abre en nueva pestaña para iniciar descarga
   };


  // --- RENDER JSX ---
  return (
     <main className="flex min-h-screen flex-col items-center p-4 md:p-12 bg-secondary">
        <h1 className="text-3xl font-bold mb-8 text-primary">Herramienta de Conciliación Bancaria</h1>

        {(isLoading || isAutoReconciling) && (
          <div className="fixed inset-0 bg-background/80 flex items-center justify-center z-50 backdrop-blur-sm">
              <RefreshCw className="h-8 w-8 animate-spin text-primary" />
              <span className="ml-3 text-lg font-semibold text-foreground">{isAutoReconciling ? 'Conciliando Automáticamente...' : 'Procesando...'}</span>
          </div>
        )}
        {error && (
          <Card className="w-full max-w-6xl mb-8 bg-destructive/10 border-destructive text-destructive-foreground p-4">
            <CardHeader><CardTitle className="text-lg text-destructive">Error</CardTitle></CardHeader>
            <CardContent><p>{error}</p>
              <Button variant="outline" size="sm" onClick={fetchInitialData} className="mt-4 border-destructive text-destructive hover:bg-destructive/10">Reintentar Carga</Button>
              <Button variant="ghost" size="sm" onClick={() => setError(null)} className="mt-4 ml-2 text-muted-foreground">Descartar</Button>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-6xl mb-8">
           <StatementUpload title="Subir Extracto Bancario (.csv)" onFileUpload={handleBankFileUpload} className="bg-card" disabled={isLoading || isAutoReconciling} />
           <StatementUpload title="Subir Auxiliar Contable (.xlsx)" onFileUpload={handleAccountingFileUpload} className="bg-card" disabled={isLoading || isAutoReconciling} />
        </div>
        <Separator className="my-8 w-full max-w-6xl" />

        <Card className="w-full max-w-6xl mb-8 shadow-md">
          <CardHeader><CardTitle className="text-lg">Iniciar Conciliación</CardTitle></CardHeader>
          <CardContent className="flex flex-col sm:flex-row flex-wrap items-center justify-center gap-4">
            <Button onClick={handleManualMatch} disabled={ isLoading || isAutoReconciling || selectedBankIds.length === 0 || selectedAccountingIds.length === 0 || (selectedBankIds.length > 1 && selectedAccountingIds.length > 1) } className="bg-accent text-accent-foreground hover:bg-accent/90" title="Seleccione (1 Banco y 1+ Contable) O (1+ Banco y 1 Contable)">
              <Link2 className="mr-2 h-4 w-4" /> Conciliar Manualmente
            </Button>
            <Button onClick={handleAutoMatch} disabled={isLoading || isAutoReconciling || bankTransactions.length === 0 || accountingTransactions.length === 0} className="bg-primary text-primary-foreground hover:bg-primary/90" title="Conciliar automáticamente">
                <Sparkles className="mr-2 h-4 w-4" /> Conciliar Auto
            </Button>
            <Button onClick={handleDownload} variant="outline" disabled={isLoading || isAutoReconciling || (bankTransactions.length === 0 && accountingTransactions.length === 0 && matchedPairs.length === 0)} title="Descargar estado actual">
                <Download className="mr-2 h-4 w-4" /> Descargar Reporte
            </Button>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full max-w-6xl">
           <StatementTable title={`Bancarias (${bankTransactions.length} Pend.)`} transactions={bankTransactions} selectedIds={selectedBankIds} onSelectionChange={setSelectedBankIds} className="bg-card" locale="es-CO" allowMultipleSelection={true} />
           <StatementTable title={`Contables (${accountingTransactions.length} Pend.)`} transactions={accountingTransactions} selectedIds={selectedAccountingIds} onSelectionChange={setSelectedAccountingIds} className="bg-card" locale="es-CO" allowMultipleSelection={true} />
        </div>

        {matchedPairs.length > 0 && (
          <>
             <Separator className="my-8 w-full max-w-6xl" />
            <Card className="w-full max-w-6xl mb-8 shadow-md">
              <CardHeader><CardTitle className="text-lg">Transacciones Conciliadas ({matchedPairs.length} Pares)</CardTitle></CardHeader>
              <CardContent>
                  <ul className="max-h-60 overflow-y-auto text-sm space-y-1 divide-y divide-border">
                    {matchedPairs.map((pair, index) => (
                      <li key={`${pair.bankTransactionId}-${pair.accountingTransactionId}-${index}`} className="p-2 text-muted-foreground hover:bg-muted/50">
                        Conciliado: Banco <code className="bg-muted px-1 rounded text-foreground">{pair.bankTransactionId}</code> con Contable <code className="bg-muted px-1 rounded text-foreground">{pair.accountingTransactionId}</code>
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