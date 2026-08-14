import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

const themeScript = `
(() => {
  try {
    const stored = window.localStorage.getItem("forgeai-theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = stored === "dark" || stored === "light" ? stored : prefersDark ? "dark" : "light";
    document.documentElement.classList.toggle("dark", theme === "dark");
  } catch {}
})();
`;

export const metadata: Metadata = {
  title: "ForgeAI",
  description: "Approval-gated autonomous software engineering control plane"
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        {children}
      </body>
    </html>
  );
}
