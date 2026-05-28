import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "회의 녹음 & 정리 · AI Meeting Minutes",
  description: "AI가 자동으로 회의를 전사하고 회의록을 만들어 드립니다",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
