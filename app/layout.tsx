import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 회의 녹음 & 회의록 작성",
  description: "AI가 자동으로 회의를 전사하고 회의록을 작성해 드립니다 · 온라인·오프라인 회의 모두 사용 가능",
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
