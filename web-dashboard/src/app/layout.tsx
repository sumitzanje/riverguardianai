import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RiverGuardian AI | Bridge Monitoring",
  description:
    "Real-time bridge flood and access monitoring powered by RiverGuardian AI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
