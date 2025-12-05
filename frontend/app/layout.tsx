import './globals.css'
import type { Metadata } from 'next'
import { Providers } from '@/components/providers/Providers'

export const metadata: Metadata = {
  title: '2nd Brain',
  description: 'AI-Powered Knowledge Transfer System',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}
