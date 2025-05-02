
"use client";

import type * as React from 'react';
import { useState } from 'react';
import { Upload } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface StatementUploadProps {
  title: string;
  onFileUpload: (file: File | null) => void;
  className?: string;
}

export function StatementUpload({ title, onFileUpload, className }: StatementUploadProps) {
  const [fileName, setFileName] = useState<string | null>(null);
  const inputId = `file-upload-${title.toLowerCase().replace(/\s+/g, '-')}`;

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setFileName(file.name);
      onFileUpload(file);
    } else {
      setFileName(null);
      onFileUpload(null);
    }
  };

  return (
    <Card className={cn("w-full shadow-md", className)}>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid w-full max-w-sm items-center gap-2">
           <Label htmlFor={inputId} className="sr-only">
             {title}
           </Label>
           <Input
              id={inputId}
              type="file"
              onChange={handleFileChange}
              className="cursor-pointer file:cursor-pointer file:text-primary file:font-medium"
              // Add specific accept types if needed, e.g., accept=".csv, application/vnd.ms-excel, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
           />
          {fileName && <p className="text-sm text-muted-foreground mt-2">Selected: {fileName}</p>}
        </div>
         {/* Optionally add an upload button if direct backend interaction is needed here */}
         {/* <Button className="mt-4">
            <Upload className="mr-2 h-4 w-4" /> Upload
         </Button> */}
      </CardContent>
    </Card>
  );
}
