
"use client";

import type * as React from 'react';
import { useState, useRef } from 'react'; // Added useRef
import { Upload } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
// import { Button } from '@/components/ui/button'; // Button removed as upload happens on file selection
import { cn } from '@/lib/utils';

interface StatementUploadProps {
  title: string;
  onFileUpload: (file: File | null) => void;
  className?: string;
  disabled?: boolean; // Add disabled prop
}

export function StatementUpload({ title, onFileUpload, className, disabled = false }: StatementUploadProps) {
  const [fileName, setFileName] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null); // Ref for the file input
  const inputId = `file-upload-${title.toLowerCase().replace(/\s+/g, '-')}`;

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setFileName(file.name);
      onFileUpload(file);
    } else {
      // If the user cancels the file selection, fileName might already be set
      // Only reset if there truly is no file selected (e.g., cleared)
      if (!event.target.value) {
         setFileName(null);
         onFileUpload(null);
      }
    }
  };

   // Reset file input when component might re-render or when explicitly needed
   const resetInput = () => {
    if (inputRef.current) {
      inputRef.current.value = ''; // Clear the selected file in the input
    }
    setFileName(null); // Clear the displayed file name
    onFileUpload(null); // Notify parent that file is cleared
  };

  // Consider resetting input if disabled state changes to true?
  // Or perhaps only reset on successful upload/processing elsewhere?
  // For now, manual reset is not implemented, file selection triggers upload.


  return (
    <Card className={cn("w-full shadow-md", className)}>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid w-full max-w-sm items-center gap-2">
           <Label htmlFor={inputId} className={cn("sr-only", disabled && "cursor-not-allowed opacity-50")}>
             {title} {/* Label text is dynamic based on title prop */}
           </Label>
           <Input
              ref={inputRef} // Attach ref
              id={inputId}
              type="file"
              onChange={handleFileChange}
              className={cn(
                "cursor-pointer file:cursor-pointer file:text-primary file:font-medium",
                disabled && "cursor-not-allowed opacity-50 file:cursor-not-allowed" // Style when disabled
              )}
              disabled={disabled} // Pass disabled prop to input
              // Add specific accept types if needed, e.g., accept=".csv, application/vnd.ms-excel, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
           />
          {fileName && <p className="text-sm text-muted-foreground mt-2 truncate">Seleccionado: {fileName}</p>}
        </div>
         {/* Upload happens automatically on file selection, so no explicit button needed */}
      </CardContent>
    </Card>
  );
}
