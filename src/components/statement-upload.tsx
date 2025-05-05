"use client";

import type * as React from 'react';
import { useState, useRef } from 'react';
import { Upload } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'; // Import Select components
import { Button } from '@/components/ui/button'; // Import Button for explicit upload action
import { cn } from '@/lib/utils';
import type { AvailableFormat } from '@/types'; // Import AvailableFormat type

interface StatementUploadProps {
  title: string;
  onFileUpload: (file: File | null, formatId: string | null) => void; // Update handler signature
  availableFormats: AvailableFormat[]; // Add prop for available formats
  className?: string;
  disabled?: boolean;
}

export function StatementUpload({
  title,
  onFileUpload,
  availableFormats,
  className,
  disabled = false
}: StatementUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFormatId, setSelectedFormatId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = `file-upload-${title.toLowerCase().replace(/\s+/g, '-')}`;

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setFileName(file.name);
    } else {
       // Reset if file selection is cancelled
      setSelectedFile(null);
      setFileName(null);
      // Do not call onFileUpload here, wait for explicit upload button click
    }
  };

  const handleFormatChange = (value: string) => {
    setSelectedFormatId(value);
  };

  const handleUploadClick = () => {
     if (selectedFile && selectedFormatId) {
         onFileUpload(selectedFile, selectedFormatId);
     } else {
         // Optionally show a toast or message if file or format is missing
         console.warn("File or format not selected.");
         // Consider using useToast hook here if needed
     }
  };

  // Function to reset state (could be called after successful upload by parent)
  const resetInput = () => {
    if (inputRef.current) {
      inputRef.current.value = '';
    }
    setSelectedFile(null);
    setFileName(null);
    setSelectedFormatId(null); // Also reset selected format
    // onFileUpload(null, null); // Notify parent if needed immediately
  };

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid w-full items-center gap-4">
           {/* File Input */}
           <div className="grid w-full max-w-sm items-center gap-1.5">
             <Label htmlFor={inputId} className={cn(disabled && "cursor-not-allowed opacity-50")}>
                Archivo
             </Label>
             <Input
                ref={inputRef}
                id={inputId}
                type="file"
                onChange={handleFileChange}
                className={cn(
                  "cursor-pointer file:cursor-pointer file:text-primary file:font-medium",
                  disabled && "cursor-not-allowed opacity-50 file:cursor-not-allowed"
                )}
                disabled={disabled}
                // Consider adding accept=".csv, .xlsx, .xls" etc.
             />
             {fileName && <p className="text-sm text-muted-foreground mt-1 truncate">Seleccionado: {fileName}</p>}
           </div>

           {/* Format Selector */}
           <div className="grid w-full max-w-sm items-center gap-1.5">
              <Label htmlFor={`${inputId}-format`} className={cn(disabled && "cursor-not-allowed opacity-50")}>
                  Formato del Archivo
              </Label>
              <Select
                  value={selectedFormatId ?? ""}
                  onValueChange={handleFormatChange}
                  disabled={disabled || availableFormats.length === 0}
              >
                  <SelectTrigger id={`${inputId}-format`} className={cn(disabled && "cursor-not-allowed opacity-50")}>
                      <SelectValue placeholder="Seleccione un formato..." />
                  </SelectTrigger>
                  <SelectContent>
                      {availableFormats.length > 0 ? (
                          availableFormats.map((format) => (
                              <SelectItem key={format.id} value={format.id}>
                                  {format.description}
                              </SelectItem>
                          ))
                      ) : (
                          <SelectItem value="loading" disabled>Cargando formatos...</SelectItem>
                      )}
                  </SelectContent>
              </Select>
           </div>

            {/* Upload Button */}
            <Button
               onClick={handleUploadClick}
               disabled={disabled || !selectedFile || !selectedFormatId}
               className="w-full max-w-sm justify-center"
               aria-label="Cargar el archivo seleccionado con el formato elegido"
             >
               <Upload className="mr-2 h-4 w-4" /> Cargar Archivo
             </Button>

        </div>
      </CardContent>
    </Card>
  );
}
```