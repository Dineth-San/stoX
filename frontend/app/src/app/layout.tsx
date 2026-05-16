import type { Metadata } from 'next';
import localFont from 'next/font/local';
import './globals.css';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';

const geistSans = localFont({
  src: './fonts/GeistVF.woff',
  variable: '--font-geist-sans',
  weight: '100 900',
});
const geistMono = localFont({
  src: './fonts/GeistMonoVF.woff',
  variable: '--font-geist-mono',
  weight: '100 900',
});

export const metadata: Metadata = {
  title: 'stoX — S&P SL20 Prediction Dashboard',
  description: 'Next-day stock price predictions for the Colombo Stock Exchange SL20 index.',
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="antialiased bg-background text-foreground font-sans">
        <Navbar />
        {/*
          mt-16   → clears 64px fixed navbar
          pt-5    → 20px top breathing room
          pb-20   → 80px bottom padding clears the 80px fixed footer
        */}
        <main className="mt-16 pt-5 pb-20 px-6 max-w-[1440px] mx-auto w-full">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
