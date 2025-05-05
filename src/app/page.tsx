"use client";

import { useState, useEffect } from 'react';
import { StatementUpload } from '@/components/statement-upload';
import { StatementTable } from '@/components/statement-table';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
// Importar tipos necesarios
import type { Transaction, MatchedPair, ManualReconcileResponse, ManyToOneReconcileResponse, OneToManyReconcileResponse, AvailableFormat } from '@/types';
import { Link2, RefreshCw, Sparkles, Download } from 'lucide-react';
import {
  getInitialTransactions,
  uploadFile, // Cambiado de uploadBank/AccountingStatement a uploadFile genérico
  reconcileManual,
  reconcileManualManyToOne,
  reconcileManualOneToMany,
  reconcileAuto,
  getMatchedPairs,
  getAvailableFormats, // Nueva función para obtener formatos
} from '@/lib/api-client';

export default function Home() {
  const [bankTransactions, setBankTransactions] = useState<Transaction[]>([]);
  const [accountingTransactions, setAccountingTransactions] = useState<Transaction[]>([]);
  const [selectedBankIds, setSelectedBankIds] = useState<string[]>([]);
  const [selectedAccountingIds, setSelectedAccountingIds] = useState<string[]>([]);
  const [matchedPairs, setMatchedPairs] = useState<MatchedPair[]>([]);
  const [availableFormats, setAvailableFormats] = useState<AvailableFormat[]>([]); // Estado para formatos
  const [isLoading, setIsLoading] = useState(true);
  const [isAutoReconciling, setIsAutoReconciling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { toast } = useToast();

  // --- Fetch Initial Data and Formats ---
  const fetchInitialDataAndFormats = async () => {
    console.log("fetchInitialDataAndFormats: function starting");
    setIsLoading(true);
    setError(null);
    try {
      const [initialData, initialMatched, formats] = await Promise.all([
        getInitialTransactions(),
        getMatchedPairs(),
        getAvailableFormats() // Cargar formatos al inicio
      ]);
      console.log("Initial data fetched:", initialData);
      setBankTransactions(initialData?.bank_transactions || []);
      setAccountingTransactions(initialData?.accounting_transactions || []);
      console.log("Initial matched pairs fetched:", initialMatched);
      setMatchedPairs(initialMatched || []);
      console.log("Available formats fetched:", formats);
      setAvailableFormats(formats || []); // Guardar formatos
      setSelectedBankIds([]);
      setSelectedAccountingIds([]);
    } catch (err) {
      console.error("Error fetching initial data or formats:", err);
      const errorMsg = err instanceof Error ? err.message : "Error desconocido";
      const displayError = `Error al cargar datos iniciales o formatos: ${errorMsg}. Inténtalo de nuevo.`;
      setError(displayError);
      toast({ title: "Error de Carga", description: displayError, variant: "destructive" });
    } finally {
      setIsLoading(false);
      console.log("fetchInitialDataAndFormats: function finished");
    }
  };

  useEffect(() => {
    console.log("Mount useEffect: fetching initial data and formats");
    fetchInitialDataAndFormats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Generic File Upload Handler ---
  const handleFileUpload = async (file: File | null, formatId: string | null) => {
    if (!file || !formatId) {
        toast({title: "Carga Fallida", description: "Debe seleccionar un archivo y un formato.", variant: "destructive"});
        return;
    }
    setIsLoading(true); setError(null);
    try {
        console.log(`Uploading file '${file.name}' with format '${formatId}'`);
        const response = await uploadFile(file, formatId); // Usar la función genérica
        console.log("Upload response:", response);

        // Determinar si la respuesta es bancaria o contable basado en el formato ID (o backend podría incluirlo)
        const formatConfig = availableFormats.find(f => f.id === formatId);
        // Hacky way based on description until backend provides type directly
        const isBank = formatConfig?.description.toLowerCase().includes('banco');
        const isAccounting = formatConfig?.description.toLowerCase().includes('contable') || formatConfig?.description.toLowerCase().includes('siesa');


        if (response?.transactions) {
            if (isBank) {
                setBankTransactions(response.transactions);
                setSelectedBankIds([]); // Reset selection for the updated table
            } else if (isAccounting) {
                setAccountingTransactions(response.transactions);
                 setSelectedAccountingIds([]); // Reset selection for the updated table
            } else {
                 // Si no podemos determinar el tipo, recargamos todo como fallback
                 console.warn("Tipo de transacción no determinado desde el formato, recargando todo.");
                 await fetchInitialDataAndFormats(); // Recarga completa
            }
             toast({ title: "Archivo Subido", description: `${response.message}. ${response.transaction_count} transacciones.` });
             setMatchedPairs([]); // Reset matches on new upload
        } else {
            toast({ title: "Archivo Procesado", description: response?.message ?? "Respuesta inesperada, pero el archivo fue procesado." });
             // Si la carga fue exitosa pero sin transacciones (archivo vacío o solo cabecera),
             // reseteamos la tabla correspondiente y los matches
             if (response) {
                 if (isBank) setBankTransactions([]);
                 else if (isAccounting) setAccountingTransactions([]);
                 setMatchedPairs([]); // Reset matches
                 setSelectedBankIds([]);
                 setSelectedAccountingIds([]);
             }
        }
    } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Error desconocido";
        toast({ title: "Error al Subir Archivo", description: errorMessage, variant: "destructive" });
        setError(`Error al subir archivo: ${errorMessage}`);
    } finally { setIsLoading(false); }
  };


  // --- Combined Manual Match Handler (sin cambios) ---
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
        // Actualizar lista de pares globales
        setMatchedPairs(prev => [...prev, ...newMatchedPairs]);

        // Eliminar transacciones recién conciliadas de las listas de pendientes
        const justMatchedBankIds = new Set(newMatchedPairs.map(p => p.bankTransactionId));
        const justMatchedAccIds = new Set(newMatchedPairs.map(p => p.accountingTransactionId));

        setBankTransactions(prev => prev.filter(tx => !justMatchedBankIds.has(tx.id)));
        setAccountingTransactions(prev => prev.filter(tx => !justMatchedAccIds.has(tx.id)));

        // Limpiar selecciones
        setSelectedBankIds([]);
        setSelectedAccountingIds([]);

        toast({ title: `Conciliación Manual Exitosa (${scenario})`, description: message });
      } else {
          // Si success es false o no hay pares, lanzar error con el mensaje del backend
          throw new Error(message || "La conciliación manual no devolvió pares exitosos.");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Error desconocido.";
      toast({ title: "Error Conciliación Manual", description: errorMessage, variant: "destructive" });
      setError(`Error conciliación manual: ${errorMessage}`);
    } finally { setIsLoading(false); }
  };


  // --- Automatic Match Handler (sin cambios) ---
   const handleAutoMatch = async () => {
     if (bankTransactions.length === 0 || accountingTransactions.length === 0) {
       toast({ title: "Conciliación Automática", description: "Se requieren transacciones pendientes en ambos lados (banco y contable).", variant: "default" });
       return;
     }
     setIsAutoReconciling(true); setError(null);
     try {
       console.log("Attempting automatic reconcile...");
       const response = await reconcileAuto();
       console.log("Auto reconcile response:", response);
       if (response?.success) {
         if (response.matched_pairs?.length > 0) {
            // Añadir nuevos pares a la lista global
           setMatchedPairs(prev => [...prev, ...response.matched_pairs]);

           // Eliminar transacciones recién conciliadas automáticamente de las listas pendientes
           const newlyMatchedBankIds = new Set(response.matched_pairs.map(p => p.bankTransactionId));
           const newlyMatchedAccIds = new Set(response.matched_pairs.map(p => p.accountingTransactionId));
           setBankTransactions(prev => prev.filter(tx => !newlyMatchedBankIds.has(tx.id)));
           setAccountingTransactions(prev => prev.filter(tx => !newlyMatchedAccIds.has(tx.id)));

           // Limpiar selecciones
           setSelectedBankIds([]);
           setSelectedAccountingIds([]);
           toast({ title: "Conciliación Automática Completada", description: response.message, className: "bg-primary text-primary-foreground border-primary" });
         } else {
           // Éxito pero sin nuevos pares
           toast({ title: "Conciliación Automática Completada", description: response.message ?? "No se encontraron nuevas coincidencias.", variant: "default" });
         }
       } else {
         // La respuesta indica que no fue exitoso
         const errorDesc = response?.message || "No se pudo completar la conciliación automática.";
         toast({ title: "Error Conciliación Automática", description: errorDesc, variant: "destructive" });
         setError(errorDesc);
       }
     } catch (err) {
       // Error en la llamada API
       const errorMessage = err instanceof Error ? err.message : "Error desconocido.";
       toast({ title: "Error Conciliación Automática", description: errorMessage, variant: "destructive" });
       setError(`Error en conciliación automática: ${errorMessage}`);
     } finally { setIsAutoReconciling(false); }
   };

   // --- Download Handler (sin cambios) ---
   const handleDownload = () => {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const downloadUrl = `${baseUrl}/api/reconciliation/download`;
        console.log(`Initiating download from: ${downloadUrl}`);
        toast({ title: "Descarga Iniciada", description: "Preparando archivo Excel..." });
        // Abrir en nueva pestaña o usar otra técnica si se necesita manejo de errores más robusto
        window.open(downloadUrl, '_blank');
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
            <CardContent>
                <p>{error}</p>
                <div className="mt-4 space-x-2">
                     <Button variant="outline" size="sm" onClick={fetchInitialDataAndFormats} className="border-destructive text-destructive hover:bg-destructive/10">Reintentar Carga</Button>
                     <Button variant="ghost" size="sm" onClick={() => setError(null)} className="text-muted-foreground">Descartar</Button>
                </div>
            </CardContent>
          </Card>
        )}

        {/* Componente de carga genérico */}
        <Card className="w-full max-w-4xl mb-8 shadow-md">
            <CardHeader><CardTitle className="text-xl">Cargar Archivos</CardTitle></CardHeader>
            <CardContent>
                 <StatementUpload
                     title="Seleccione Archivo y Formato"
                     onFileUpload={handleFileUpload}
                     availableFormats={availableFormats} // Pasar formatos disponibles
                     className="bg-card"
                     disabled={isLoading || isAutoReconciling}
                 />
            </CardContent>
        </Card>


        <Separator className="my-8 w-full max-w-6xl" />

        <Card className="w-full max-w-6xl mb-8 shadow-md">
          <CardHeader><CardTitle className="text-lg">Iniciar Conciliación</CardTitle></CardHeader>
          <CardContent className="flex flex-col sm:flex-row flex-wrap items-center justify-center gap-4">
            {/* Botón Conciliar Manual */}
            <Button
               onClick={handleManualMatch}
               disabled={
                   isLoading || isAutoReconciling ||
                   selectedBankIds.length === 0 || selectedAccountingIds.length === 0 || // Necesita selección en ambos lados
                   (selectedBankIds.length > 1 && selectedAccountingIds.length > 1) // No permite M-M
               }
               className="bg-accent text-accent-foreground hover:bg-accent/90"
               title={
                   (selectedBankIds.length === 0 || selectedAccountingIds.length === 0)
                   ? "Seleccione al menos una transacción bancaria y una contable."
                   : (selectedBankIds.length > 1 && selectedAccountingIds.length > 1)
                   ? "Selección inválida (muchos-a-muchos no soportado)."
                   : "Conciliar transacciones seleccionadas manualmente (1-1, 1-M, M-1)."
               }
            >
              <Link2 className="mr-2 h-4 w-4" /> Conciliar Manualmente
            </Button>

             {/* Botón Conciliar Auto */}
            <Button
                onClick={handleAutoMatch}
                disabled={isLoading || isAutoReconciling || bankTransactions.length === 0 || accountingTransactions.length === 0}
                className="bg-primary text-primary-foreground hover:bg-primary/90"
                title={
                     (bankTransactions.length === 0 || accountingTransactions.length === 0)
                     ? "Se requieren transacciones pendientes en ambos lados para la conciliación automática."
                     : "Iniciar conciliación automática basada en monto."
                 }
             >
                <Sparkles className="mr-2 h-4 w-4" /> Conciliar Auto
            </Button>

            {/* Botón Descargar Reporte */}
            <Button
                onClick={handleDownload}
                variant="outline"
                disabled={isLoading || isAutoReconciling || (bankTransactions.length === 0 && accountingTransactions.length === 0 && matchedPairs.length === 0)}
                title="Descargar estado actual de conciliación (pendientes y conciliados) en Excel."
             >
                <Download className="mr-2 h-4 w-4" /> Descargar Reporte
            </Button>
          </CardContent>
        </Card>

        {/* Tablas de Transacciones Pendientes */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full max-w-6xl">
           <StatementTable
               title={`Transacciones Bancarias (${bankTransactions.length} Pend.)`}
               transactions={bankTransactions}
               selectedIds={selectedBankIds}
               onSelectionChange={setSelectedBankIds}
               className="bg-card"
               locale="es-CO" // Ajustar locale según sea necesario
               allowMultipleSelection={true}
           />
           <StatementTable
                title={`Transacciones Contables (${accountingTransactions.length} Pend.)`}
                transactions={accountingTransactions}
                selectedIds={selectedAccountingIds}
                onSelectionChange={setSelectedAccountingIds}
                className="bg-card"
                locale="es-CO"
                allowMultipleSelection={true}
            />
        </div>

        {/* Sección de Transacciones Conciliadas */}
        {matchedPairs.length > 0 && (
          <>
             <Separator className="my-8 w-full max-w-6xl" />
            <Card className="w-full max-w-6xl mb-8 shadow-md">
              <CardHeader><CardTitle className="text-lg">Transacciones Conciliadas ({matchedPairs.length} Pares)</CardTitle></CardHeader>
              <CardContent>
                  <ul className="max-h-60 overflow-y-auto text-sm space-y-1 divide-y divide-border">
                    {/* Mostrar los pares conciliados */}
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
```