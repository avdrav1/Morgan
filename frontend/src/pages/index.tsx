import React from 'react';
import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Home, FolderOpen, Settings as SettingsIcon, LogOut } from 'lucide-react';
import ProjectDetailComponent from './ProjectDetail';

// Register component
export function Register() {
  return <div className="p-8">Register page - To be implemented</div>;
}

// Layout component with navigation
export function Layout() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center space-x-8">
              <Link to="/" className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-lg">A</span>
                </div>
                <span className="font-semibold text-gray-900">Accountability Assistant</span>
              </Link>
              
              <div className="hidden md:flex space-x-4">
                <Link
                  to="/"
                  className="flex items-center px-3 py-2 text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <Home className="w-4 h-4 mr-2" />
                  Dashboard
                </Link>
                <Link
                  to="/projects/new"
                  className="flex items-center px-3 py-2 text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <FolderOpen className="w-4 h-4 mr-2" />
                  New Project
                </Link>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <Link
                to="/settings"
                className="flex items-center px-3 py-2 text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <SettingsIcon className="w-4 h-4 mr-2" />
                Settings
              </Link>
              <button
                onClick={handleLogout}
                className="flex items-center px-3 py-2 text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main>
        <Outlet />
      </main>
    </div>
  );
}

// Re-export ProjectDetail
export const ProjectDetail = ProjectDetailComponent;

// Settings component
export function Settings() {
  return <div className="p-8">Settings page - To be implemented</div>;
}

export default { Register, Layout, ProjectDetail, Settings };
