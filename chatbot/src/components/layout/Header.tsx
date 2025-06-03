
import React from 'react';
import { UserButton } from '@/components/auth/UserButton';
import { Building2, MapPin } from 'lucide-react';

export const Header = () => {
  return (
    <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-blue-600 p-2 rounded-lg">
              <Building2 className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-800">MyCitiyMentor</h1>
              <div className="flex items-center text-sm text-slate-500">
                <MapPin className="h-3 w-3 mr-1" />
                <span>Warwick RI Municipal Services</span>
              </div>
            </div>
          </div>
          <UserButton />
        </div>
      </div>
    </header>
  );
};
