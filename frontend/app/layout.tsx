import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mater",
  description: "Real-time vehicle telemetry and assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <nav className="flex h-14 items-center gap-6 border-b border-slate-800 px-6">
          <span className="font-bold">Mater</span>
          <Link href="/driver" className="text-sm text-slate-300 hover:text-white">
            Driver
          </Link>
          <Link href="/host" className="text-sm text-slate-300 hover:text-white">
            Host
          </Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
