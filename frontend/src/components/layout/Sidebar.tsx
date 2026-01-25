import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Bell, BarChart3, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
}

const navItems: NavItem[] = [
  { to: '/', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Dashboard' },
  { to: '/alerts', icon: <Bell className="w-5 h-5" />, label: 'Alerts' },
  { to: '/markets', icon: <BarChart3 className="w-5 h-5" />, label: 'Markets' },
];

export function Sidebar() {
  return (
    <aside className="w-56 h-screen bg-white border-r border-gray-200 flex flex-col">
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-gray-200">
        <Activity className="w-6 h-6 text-gray-900 mr-2" />
        <span className="font-semibold text-gray-900">Polymarket</span>
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
                      ? 'bg-gray-100 text-gray-900'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
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

      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-200">
        <p className="text-xs text-gray-400">Analyzer v1.0</p>
      </div>
    </aside>
  );
}
