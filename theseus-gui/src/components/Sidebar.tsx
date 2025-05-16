"use client";
import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Settings,
  Mail,
  Mic,
  BookOpen,
  ListChecks,
  Menu,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

const links = [
  { href: '/settings', label: 'Settings', icon: Settings },
  { href: '/newsletter', label: 'Newsletter Builder', icon: Mail },
  { href: '/podcast', label: 'Podcast Builder', icon: Mic },
  { href: '/papers', label: 'Paper Ratings', icon: BookOpen },
  { href: '/runs', label: 'Run Log', icon: ListChecks },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <aside
      className={`h-screen bg-zinc-900 text-zinc-100 flex flex-col transition-all duration-200 border-r border-zinc-800
        ${collapsed ? 'w-16' : 'w-60'}
        fixed md:static z-40
      `}
    >
      <div className="flex items-center justify-between h-16 px-4 border-b border-zinc-800">
        {!collapsed && <span className="font-bold text-lg tracking-wide">Theseus</span>}
        <button
          className="p-2 rounded hover:bg-zinc-800 transition-colors"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
        </button>
      </div>
      <nav className="flex-1 flex flex-col gap-1 mt-4">
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-3 px-4 py-2 rounded-lg mx-2 my-1 transition-colors
              ${pathname === href ? 'bg-zinc-800 text-primary' : 'hover:bg-zinc-800'}
              ${collapsed ? 'justify-center px-2' : ''}
            `}
          >
            <Icon size={20} />
            {!collapsed && <span className="truncate">{label}</span>}
          </Link>
        ))}
      </nav>
      <div className="mt-auto mb-4 px-4 text-xs text-zinc-500 text-center">
        {!collapsed && '© 2024 Theseus Insight'}
      </div>
    </aside>
  );
} 