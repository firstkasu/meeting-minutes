import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "회의 녹음 & 정리",
  description: "회의 녹음·전사·회의록 자동 생성",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
