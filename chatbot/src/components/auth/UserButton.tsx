
import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { User, Shield, Eye, LogIn, UserPlus } from 'lucide-react';
import { LoginModal } from './LoginModal';

type UserType = 'anonymous' | 'registered' | 'verified';

export const UserButton = () => {
  const [userType, setUserType] = useState<UserType>('anonymous');
  const [showLoginModal, setShowLoginModal] = useState(false);

  const getUserInfo = () => {
    switch (userType) {
      case 'anonymous':
        return {
          icon: Eye,
          label: 'Anonymous User',
          badge: 'Limited Access',
          badgeColor: 'bg-gray-500'
        };
      case 'registered':
        return {
          icon: User,
          label: 'John Doe',
          badge: 'Registered',
          badgeColor: 'bg-blue-500'
        };
      case 'verified':
        return {
          icon: Shield,
          label: 'John Doe',
          badge: 'Verified Resident',
          badgeColor: 'bg-green-500'
        };
    }
  };

  const userInfo = getUserInfo();
  const IconComponent = userInfo.icon;

  return (
    <>
      <div className="flex items-center space-x-3">
        {userType === 'anonymous' ? (
          <div className="flex space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowLoginModal(true)}
              className="flex items-center space-x-2"
            >
              <LogIn className="h-4 w-4" />
              <span>Sign In</span>
            </Button>
            <Button
              size="sm"
              onClick={() => setShowLoginModal(true)}
              className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700"
            >
              <UserPlus className="h-4 w-4" />
              <span>Register</span>
            </Button>
          </div>
        ) : (
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <div className="bg-slate-100 p-2 rounded-full">
                <IconComponent className="h-4 w-4 text-slate-600" />
              </div>
              <div className="text-right">
                <div className="text-sm font-medium text-slate-800">{userInfo.label}</div>
                <Badge className={`text-xs ${userInfo.badgeColor} text-white`}>
                  {userInfo.badge}
                </Badge>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setUserType('anonymous')}
            >
              Sign Out
            </Button>
          </div>
        )}
      </div>

      <LoginModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
        onLogin={(type) => {
          setUserType(type);
          setShowLoginModal(false);
        }}
      />
    </>
  );
};