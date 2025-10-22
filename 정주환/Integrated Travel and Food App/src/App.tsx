import { useState } from 'react';
import { Navigation, Utensils, Route, Settings } from 'lucide-react';
import { RouteNavigationTab } from './components/RouteNavigationTab';
import { FoodExplorationTab } from './components/FoodExplorationTab';
import { PresetCoursesTab } from './components/PresetCoursesTab';
import { SettingsTab } from './components/SettingsTab';

const tabs = [
  { id: 'route', label: '경로 안내', icon: Navigation, component: RouteNavigationTab },
  { id: 'food', label: '음식', icon: Utensils, component: FoodExplorationTab },
  { id: 'courses', label: '프리셋 코스', icon: Route, component: PresetCoursesTab },
  { id: 'settings', label: '설정', icon: Settings, component: SettingsTab },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('route');

  const ActiveComponent = tabs.find(tab => tab.id === activeTab)?.component || RouteNavigationTab;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900">길따라 맛따라</h1>
          <div className="flex gap-2">
            <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-sm">
              오후 2:30
            </span>
            <span className="bg-green-100 text-green-800 px-2 py-1 rounded-full text-sm">
              맑음 18°C
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        <ActiveComponent />
      </main>

      {/* Bottom Navigation */}
      <nav className="bg-white border-t border-gray-200 px-4 py-2">
        <div className="flex justify-around">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex flex-col items-center py-2 px-3 rounded-lg transition-colors ${
                  isActive
                    ? 'text-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                <Icon className="w-5 h-5 mb-1" />
                <span className="text-xs">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
}