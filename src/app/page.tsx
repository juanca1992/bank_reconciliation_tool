"use client";

import { useState, useEffect } from 'react';
import { StatementUpload } from '@/components/statement-upload';
import { StatementTable } from '@/components/statement-table';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import type { Transaction, MatchedPair, ManyToOneReconcileResponse } from '@/types'; // Asegúrate que ManyToOneReconcileResponse esté en @/types
import { Link2, RefreshCw, Sparkles } from 'lucide-react';
import {
  getInitialTransactions,
  uploadBankStatement,
  uploadAccountingStatement,
  reconcileManual,         // Para 1 a 1
  reconcileManualManyToOne, // Para 1 banco, muchos contables
  reconcileAuto,
  getMatchedPairs,
  // Quité las funciones reset...
} from '@/lib/api-client';

export default function Home() {
  const [bankTransactions, setBankTransactions] = useState<Transaction[]>([]);
  const [accountingTransactions, setAccountingTransactions] = useState<Transaction[]>([]);
  const [selectedBankIds, setSelectedBankIds] = useState<string[]>([]);
  const [selectedAccountingIds, setSelectedAccountingIds] = useState<string[]>([]);
  const [matchedPairs, setMatchedPairs] = useState<MatchedPair[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAutoReconciling, setIsAutoReconciling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { toast } = useToast();

  // --- Fetch Initial Data (sin cambios) ---
  const fetchInitialData = async () => {
    console.log("fetchInitialData: function starting");
    setIsLoading(true);
    setError(null);
    try {
      const initialData = await getInitialTransactions();
      console.log("Initial data fetched:", initialData);
      setBankTransactions(initialData?.bank_transactions || []);
      setAccountingTransactions(initialData?.accounting_transactions || []);
      const initialMatched = await getMatchedPairs();
      console.log("Initial matched pairs fetched:", initialMatched);
      setMatchedPairs(initialMatched || []);
      setSelectedBankIds([]);
      setSelectedAccountingIds([]);
    } catch (err) {
      console.error("Error fetching initial data:", err);
      const errorMsg = err instanceof Error ? err.message : "Error desconocido";
      setError(`Error al cargar los datos iniciales: ${errorMsg}. Inténtalo de nuevo.`);
    } finally {
      setIsLoading(false);
      console.log("fetchInitialData: function finished");
    }
  };

  useEffect(() => {
    fetchInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- File Upload Handlers (sin cambios) ---
  const handleBankFileUpload = async (file: File | null) => {
    // ... (código sin cambios) ...
     if (!file) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await uploadBankStatement(file);
      console.log("Bank upload response:", response);
      if (response && Array.isArray(response.transactions)) {
        setBankTransactions(response.transactions || []);
        toast({ title: "Extracto Bancario Subido", description: `${response.message}. ${response.transaction_count} transacciones cargadas.` });
        setSelectedBankIds([]);
      } else {
        console.warn("Bank upload response did not contain transactions array:", response);
        toast({ title: "Extracto Bancario Procesado", description: response?.message ?? "Respuesta inesperada" });
      }
    } catch (err) {
        console.error("Error uploading bank statement:", err);
        const errorMessage = err instanceof Error ? err.message : "Error desconocido";
        toast({ title: "Error al Subir", description: `Extracto bancario: ${errorMessage}`, variant: "destructive" });
        setError(`Error al subir extracto bancario: ${errorMessage}`);
    } finally {
        setIsLoading(false);
    }
  };

  const handleAccountingFileUpload = async (file: File | null) => {
    // ... (código sin cambios) ...
    if (!file) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await uploadAccountingStatement(file);
      console.log("Accounting upload response:", response);
       if (response && Array.isArray(response.transactions)) {
        setAccountingTransactions(response.transactions || []);
        toast({ title: "Extracto Contable Subido", description: `${response.message}. ${response.transaction_count} transacciones cargadas.` });
        setSelectedAccountingIds([]);
      } else {
         console.warn("Accounting upload response did not contain transactions array:", response);
         toast({ title: "Extracto Contable Procesado", description: response?.message ?? "Respuesta inesperada" });
      }
    } catch (err) {
        console.error("Error uploading accounting statement:", err);
        const errorMessage = err instanceof Error ? err.message : "Error desconocido";
        toast({ title: "Error al Subir", description: `Extracto contable: ${errorMessage}`, variant: "destructive" });
        setError(`Error al subir extracto contable: ${errorMessage}`);
    } finally {
        setIsLoading(false);
    }
  };

  // *** CORREGIDO: Handler Manual Inteligente ***
  const handleManualMatch = async () => {
    const numBankSelected = selectedBankIds.length;
    const numAccSelected = selectedAccountingIds.length;

    // Validación general: exactamente 1 bancaria y al menos 1 contable
    if (numBankSelected !== 1 || numAccSelected === 0) {
      toast({
        title: "Error de Selección Manual",
        description: "Debe seleccionar exactamente UNA transacción bancaria y al menos UNA transacción contable.",
        variant: "destructive",
      });
      return;
    }

    const bankTxId = selectedBankIds[0]; // Siempre el único seleccionado

    setIsLoading(true);
    setError(null);

    try {
      // Decidir qué API llamar basado en cuántos contables se seleccionaron
      if (numAccSelected === 1) {
        // --- Caso 1 a 1 ---
        const accTxId = selectedAccountingIds[0];
        console.log(`Attempting manual match (1-1): Bank ID ${bankTxId}, Accounting ID ${accTxId}`);
        const response = await reconcileManual(bankTxId, accTxId);
        console.log("Manual reconcile (1-1) response:", response);

        if (response.success && response.matched_pair) {
          setMatchedPairs(prev => [...prev, response.matched_pair!]);
          setBankTransactions(prev => prev.filter(tx => tx.id !== bankTxId));
          setAccountingTransactions(prev => prev.filter(tx => tx.id !== accTxId));
          toast({ title: "Conciliación Manual (1-1) Exitosa", description: response.message });
        } else {
          throw new Error(response.message || "No se pudo completar la conciliación (1-1).");
        }

      } else {
        // --- Caso 1 Banco a Muchos Contables ---
        const accTxIds = selectedAccountingIds; // La lista completa
        console.log(`Attempting manual match (1-Many): Bank ID ${bankTxId}, Accounting IDs ${accTxIds.join(', ')}`);
        const response = await reconcileManualManyToOne(bankTxId, accTxIds); // Llama a la API correcta
        console.log("Manual reconcile (1-Many) response:", response);

        if (response.success && response.matched_pairs_created && response.matched_pairs_created.length > 0) {
          setMatchedPairs(prev => [...prev, ...response.matched_pairs_created]);
          setBankTransactions(prev => prev.filter(tx => tx.id !== bankTxId));
          // Quitar todos los contables involucrados
          const matchedAccIdsSet = new Set(accTxIds);
          setAccountingTransactions(prev => prev.filter(tx => !matchedAccIdsSet.has(tx.id)));
          toast({ title: "Conciliación Manual (1-Muchos) Exitosa", description: response.message });
        } else {
           throw new Error(response.message || "No se pudo completar la conciliación (1-Muchos).");
        }
      }

      // Si cualquiera de las llamadas tuvo éxito, limpiar selecciones
      setSelectedBankIds([]);
      setSelectedAccountingIds([]);

    } catch (err) {
      // Captura errores de CUALQUIERA de las llamadas API o del throw new Error
      console.error("Error during manual reconciliation:", err);
      const errorMessage = err instanceof Error ? err.message : "Error desconocido al conciliar manualmente.";
      toast({ title: "Error en Conciliación Manual", description: errorMessage, variant: "destructive" });
      setError(`Error en conciliación manual: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };


  // --- Automatic Match Handler (sin cambios) ---
   const handleAutoMatch = async () => {
    // ... (código sin cambios) ...
     if (bankTransactions.length === 0 || accountingTransactions.length === 0) {
       toast({
           title: "Conciliación Automática",
           description: "Se requieren transacciones pendientes en ambos extractos (bancario y contable) para iniciar.",
           variant: "default", // o "warning"
         });
       return;
     }
     setIsAutoReconciling(true);
     setError(null);
     try {
       console.log("Attempting automatic reconcile...");
       const response = await reconcileAuto();
       console.log("Auto reconcile response:", response);
       if (response.success) {
         if (response.matched_pairs && response.matched_pairs.length > 0) {
           console.log("New matches found by auto reconcile:", response.matched_pairs);
           setMatchedPairs(prev => [...prev, ...response.matched_pairs]);
           const newlyMatchedBankIds = new Set(response.matched_pairs.map(p => p.bankTransactionId));
           const newlyMatchedAccIds = new Set(response.matched_pairs.map(p => p.accountingTransactionId));
           setBankTransactions(prev => prev.filter(tx => !newlyMatchedBankIds.has(tx.id)));
           setAccountingTransactions(prev => prev.filter(tx => !newlyMatchedAccIds.has(tx.id)));
           setSelectedBankIds([]);
           setSelectedAccountingIds([]);
           toast({
             title: "Conciliación Automática Completada",
             description: response.message,
             variant: "default",
             className: "bg-primary text-primary-foreground border-primary",
           });
         } else {
           console.log("No new matches found by auto reconcile.");
           toast({
             title: "Conciliación Automática Completada",
             description: response.message,
             variant: "default",
           });
         }
       } else {
         const errorDesc = response.message || "No se pudo completar la conciliación automática.";
         console.error("Auto reconcile error:", errorDesc);
         toast({
           title: "Error de Conciliación Automática",
           description: errorDesc,
           variant: "destructive",
         });
         setError(errorDesc);
       }
     } catch (err) {
       console.error("Error during automatic reconciliation call:", err);
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

  // --- RENDER JSX ---
  return (
     <main className="flex min-h-screen flex-col items-center p-4 md:p-12 bg-secondary">
        <h1 className="text-3xl font-bold mb-8 text-primary">Herramienta de Conciliación Bancaria</h1>

        {/* Loading and Error States (sin cambios) */}
        {(isLoading || isAutoReconciling) && (
          <div className="fixed inset-0 bg-background/80 flex items-center justify-center z-50">
              <RefreshCw className="h-8 w-8 animate-spin text-primary" />
              <span className="ml-3 text-lg text-foreground">{isAutoReconciling ? 'Conciliando automáticamente...' : 'Cargando...'}</span>
          </div>
        )}
        {error && (
          <Card className="w-full max-w-6xl mb-8 bg-destructive/10 border-destructive text-destructive-foreground p-4">
            <CardHeader><CardTitle className="text-lg text-destructive">Error</CardTitle></CardHeader>
            <CardContent>
                <p>{error}</p>
                <Button variant="outline" size="sm" onClick={fetchInitialData} className="mt-4 border-destructive text-destructive hover:bg-destructive/10">Reintentar Carga Inicial</Button>
                <Button variant="ghost" size="sm" onClick={() => setError(null)} className="mt-4 ml-2 text-muted-foreground">Descartar</Button>
            </CardContent>
          </Card>
        )}

        {/* Upload Section (sin cambios) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-6xl mb-8">
          {/* ... StatementUpload components ... */}
           <StatementUpload
            title="Subir Extracto Bancario"
            onFileUpload={handleBankFileUpload}
            className="bg-card"
            disabled={isLoading || isAutoReconciling}
          />
          <StatementUpload
            title="Subir Extracto del Sistema Contable"
            onFileUpload={handleAccountingFileUpload}
            className="bg-card"
            disabled={isLoading || isAutoReconciling}
          />
        </div>

        <Separator className="my-8 w-full max-w-6xl" />

        {/* Matching Controls */}
        <Card className="w-full max-w-6xl mb-8 shadow-md">
          <CardHeader>
              <CardTitle className="text-lg">Iniciar Conciliación</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col sm:flex-row flex-wrap items-center justify-center gap-4">
            {/* *** Botón Manual ÚNICO y CORREGIDO *** */}
            <Button
              onClick={handleManualMatch} // Llama al handler inteligente
              // Habilitado si hay 1 banco y al menos 1 contable seleccionados
              disabled={isLoading || isAutoReconciling || selectedBankIds.length !== 1 || selectedAccountingIds.length === 0}
              className="bg-accent text-accent-foreground hover:bg-accent/90"
              title="Seleccione UNA transacción bancaria y UNA O MÁS contables para activar"
            >
              <Link2 className="mr-2 h-4 w-4" />
              Conciliar Manualmente (Seleccionados)
            </Button>

            {/* Botón Automático (sin cambios) */}
            <Button
              onClick={handleAutoMatch}
              disabled={isLoading || isAutoReconciling || bankTransactions.length === 0 || accountingTransactions.length === 0}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
              title="Conciliar automáticamente las transacciones pendientes"
            >
                <Sparkles className="mr-2 h-4 w-4" />
                Conciliar Automáticamente
            </Button>

            {/* Botón de Reset Eliminado */}

          </CardContent>
        </Card>

        {/* Statement Tables Section (sin cambios) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full max-w-6xl">
           <StatementTable
            title="Transacciones Bancarias (Pendientes)"
            transactions={bankTransactions}
            selectedIds={selectedBankIds}
            onSelectionChange={setSelectedBankIds}
            className="bg-card"
            locale="es-CO" // Cambiado a es-CO para formato numérico
          />
          <StatementTable
            title="Transacciones Contables (Pendientes)"
            transactions={accountingTransactions}
            selectedIds={selectedAccountingIds}
            onSelectionChange={setSelectedAccountingIds}
            className="bg-card"
            locale="es-CO" // Cambiado a es-CO para formato numérico
          />
        </div>

        {/* Display matched pairs (sin cambios) */}
        {matchedPairs.length > 0 && (
          <>
            {/* ... Card para mostrar conciliados ... */}
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