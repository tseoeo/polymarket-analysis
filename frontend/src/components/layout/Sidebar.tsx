import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Bell,
  BarChart3,
  Activity,
  GitBranch,
  BookOpen,
  TrendingUp,
  Users,
  Sun,
  Star,
  Moon,
  Monitor,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
}

const navItems: NavItem[] = [
  { to: '/', icon: <Sun className="w-5 h-5" />, label: 'Daily Briefing' },
  { to: '/watchlist', icon: <Star className="w-5 h-5" />, label: 'Watchlist' },
  { to: '/alerts', icon: <Bell className="w-5 h-5" />, label: 'Alerts' },
  { to: '/arbitrage', icon: <GitBranch className="w-5 h-5" />, label: 'Arbitrage' },
  { to: '/orderbook', icon: <BookOpen className="w-5 h-5" />, label: 'Liquidity' },
  { to: '/volume', icon: <TrendingUp className="w-5 h-5" />, label: 'Activity' },
  { to: '/mm', icon: <Users className="w-5 h-5" />, label: 'Liquidity Providers' },
  { to: '/markets', icon: <BarChart3 className="w-5 h-5" />, label: 'Markets' },
  { to: '/dashboard', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Dashboard' },
];

const themeOptions = [
  { value: 'light' as const, icon: Sun, label: 'Light' },
  { value: 'system' as const, icon: Monitor, label: 'System' },
  { value: 'dark' as const, icon: Moon, label: 'Dark' },
];

export function Sidebar() {
  const { theme, setTheme } = useTheme();

  return (
    <aside className="w-56 h-screen bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 flex flex-col">
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-gray-200 dark:border-gray-700">
        <Activity className="w-6 h-6 text-gray-900 dark:text-gray-50 mr-2" />
        <span className="font-semibold text-gray-900 dark:text-gray-50">Polymarket</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-50'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-50'
                  )
                }
              >
                {item.icon}
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Theme Toggle */}
      <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center rounded-md bg-gray-100 dark:bg-gray-800 p-0.5" role="radiogroup" aria-label="Theme">
          {themeOptions.map(({ value, icon: Icon, label }) => (
            <button
              key={value}
              role="radio"
              aria-checked={theme === value}
              aria-label={label}
              onClick={() => setTheme(value)}
              className={cn(
                'flex-1 flex items-center justify-center gap-1 py-1.5 rounded text-xs font-medium transition-colors focus-ring',
                theme === value
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-50 shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">Analyzer v1.0</p>
      </div>
    </aside>
  );
}
