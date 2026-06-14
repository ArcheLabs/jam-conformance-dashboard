import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "M1 Conformance Evaluation Runtime Statistics",
  description: "This page summarizes runtime statistics from the M1 conformance tests to help JAM implementations identify targeted optimization opportunities. The data should be treated as reference only and not as strict performance benchmark results.",
  keywords: ["JAM", "blockchain", "performance", "benchmarks", "conformance", "protocol"],
  authors: [{ name: "JAM Conformance Team" }],
  openGraph: {
    title: "M1 Conformance Evaluation Runtime Statistics",
    description: "This page summarizes runtime statistics from the M1 conformance tests to help JAM implementations identify targeted optimization opportunities. The data should be treated as reference only and not as strict performance benchmark results.",
    type: "website",
  },
  manifest: "/site.webmanifest",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
