'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useSriLankaTime } from '@/hooks/useSriLankaTime';

const NAV_LINKS = [
  { label: 'Dashboard',   href: '/dashboard' },
  { label: 'Predictions', href: '/predictions' },
  { label: 'Portfolio',   href: '/portfolio' },
  { label: 'News',        href: '/news' },
] as const;

export function Navbar() {
  const pathname = usePathname();
  const time = useSriLankaTime();

  return (
    <header className="fixed top-0 left-0 right-0 h-16 bg-background border-b border-border z-50">
      <div className="max-w-[1440px] mx-auto h-full px-6 flex items-center justify-between">

        {/* Logo */}
        <Link href="/dashboard" className="shrink-0">
          <span className="text-golden font-bold text-2xl italic tracking-tight select-none">
            stoX
          </span>
        </Link>

        {/* Nav links */}
        <nav className="flex items-center gap-8">
          {NAV_LINKS.map(({ label, href }) => {
            const active = pathname === href || (href !== '/dashboard' && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  'text-sm font-medium transition-colors pb-0.5',
                  active
                    ? 'text-golden border-b-2 border-golden'
                    : 'text-muted-foreground hover:text-white'
                )}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Right: LIVE badge + time */}
        <div className="flex items-center gap-4 shrink-0">
          <div className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-jade opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-jade" />
            </span>
            <span className="text-xs font-semibold text-jade tracking-wider">LIVE</span>
          </div>
          <span className="font-mono text-sm text-muted-foreground tabular-nums">{time}</span>
        </div>

      </div>
    </header>
  );
}
