
import type { Metadata } from 'next';
import { Inter } from 'next/font/google'; // Using Inter as a clean, professional font
import './globals.css';
import { Toaster } from "@/components/ui/toaster"; // Import Toaster

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'Herramienta de Conciliación Bancaria', // Updated title to Spanish
  description: 'Herramienta para conciliar extractos bancarios y contables.', // Updated description to Spanish
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es"> {/* Set language to Spanish */}
      <body className={`${inter.variable} font-sans antialiased`}>
        {children}
        <Toaster /> {/* Add Toaster here */}
      </body>
    </html>
  );
}
