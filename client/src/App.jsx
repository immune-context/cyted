import { useState } from 'react';
import './App.css';
import About from './components/About';
import Database from './components/Database';

function App() {
  const [activeTab, setActiveTab] = useState('about');

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div className="w-full px-6 py-6">
          <h1 className="text-3xl font-bold mb-2">CytED</h1>

          {/* Tabs */}
          <nav className="flex gap-1 mt-6 -mb-px">
            <button
              onClick={() => setActiveTab('about')}
              className={`flex items-center gap-2 px-4 py-3 font-medium text-sm transition-colors ${
                activeTab === 'about'
                  ? 'tab-active text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              About
            </button>
            <button
              onClick={() => setActiveTab('database')}
              className={`flex items-center gap-2 px-4 py-3 font-medium text-sm transition-colors ${
                activeTab === 'database'
                  ? 'tab-active text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              Database
            </button>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="w-full px-6 py-8">
        {activeTab === 'about' && <About />}
        {activeTab === 'database' && <Database />}
      </main>
    </div>
  );
}

export default App;
