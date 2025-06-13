import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { 
  User, 
  Shield, 
  Eye, 
  LogIn, 
  UserPlus, 
  Settings, 
  LogOut,
  ChevronDown,
  AlertCircle,
  CheckCircle2,
  Clock
} from 'lucide-react';
import { LoginModal } from './LoginModal';
import { getFullName, getInitials } from '@/utils/userUtils';
import { cn } from '@/lib/utils';

type UserType = 'anonymous' | 'registered' | 'verified';

interface UserData {
  id?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  address?: string;
  verified?: boolean;
  avatar_url?: string;
  created_at?: string;
  last_login?: string;
}

interface UserButtonProps {
  className?: string;
  showUserMenu?: boolean;
  onProfileClick?: () => void;
  onSettingsClick?: () => void;
  onSignOut?: () => void;
  compact?: boolean;
}

const USER_TYPE_CONFIG = {
  anonymous: {
    icon: Eye,
    label: 'Anonymous User',
    badge: 'Guest',
    badgeVariant: 'secondary' as const,
    description: 'Limited access to basic services',
    priority: 0,
  },
  registered: {
    icon: User,
    label: 'Registered User',
    badge: 'Registered',
    badgeVariant: 'default' as const,
    description: 'Access to personalized services',
    priority: 1,
  },
  verified: {
    icon: Shield,
    label: 'Verified Resident',
    badge: 'Verified',
    badgeVariant: 'default' as const,
    description: 'Full access to all municipal services',
    priority: 2,
  },
} as const;

export const UserButton: React.FC<UserButtonProps> = ({
  className,
  showUserMenu = true,
  onProfileClick,
  onSettingsClick,
  onSignOut,
  compact = false,
}) => {
  const [userType, setUserType] = useState<UserType>('anonymous');
  const [userData, setUserData] = useState<UserData>({});
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [loginModalTab, setLoginModalTab] = useState<'login' | 'register'>('login');

  // Memoized user information
  const userInfo = useMemo(() => {
    const config = USER_TYPE_CONFIG[userType];
    const fullName = getFullName(userData);
    const initials = getInitials(userData);
    
    return {
      ...config,
      displayName: userType === 'anonymous' ? config.label : fullName || userData.email || config.label,
      initials: userType === 'anonymous' ? 'G' : initials,
      email: userData.email,
      avatar: userData.avatar_url,
    };
  }, [userType, userData]);

  // Update user data from storage
  const updateUserFromStorage = useCallback(() => {
    try {
      if (typeof window === 'undefined') {
        setIsLoading(false);
        return;
      }

      const userString = localStorage.getItem('user');
      const accessToken = localStorage.getItem('access_token');
      
      if (!accessToken || !userString) {
        setUserType('anonymous');
        setUserData({});
        setIsLoading(false);
        return;
      }

      const user: UserData = JSON.parse(userString);
      const type: UserType = user.verified ? 'verified' : 'registered';
      
      setUserType(type);
      setUserData(user);
      setIsLoading(false);
      
    } catch (error) {
      console.error('Error parsing user data from localStorage:', error);
      // Clear potentially corrupted data
      localStorage.removeItem('user');
      localStorage.removeItem('access_token');
      localStorage.removeItem('token_type');
      setUserType('anonymous');
      setUserData({});
      setIsLoading(false);
    }
  }, []);

  // Initialize and listen for storage changes
  useEffect(() => {
    updateUserFromStorage();

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'user' || e.key === 'access_token' || e.key === null) {
        updateUserFromStorage();
      }
    };

    const handleCustomStorageEvent = () => {
      updateUserFromStorage();
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('storage', handleCustomStorageEvent);
    
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('storage', handleCustomStorageEvent);
    };
  }, [updateUserFromStorage]);

  // Handle sign out
  const handleSignOut = useCallback(() => {
    try {
      // Clear all auth-related localStorage items
      const keysToRemove = ['user', 'access_token', 'token_type', 'refresh_token'];
      keysToRemove.forEach(key => localStorage.removeItem(key));
      
      // Dispatch storage event to notify other components
      window.dispatchEvent(new Event('storage'));
      
      // Call optional callback
      onSignOut?.();
      
    } catch (error) {
      console.error('Error during sign out:', error);
    }
  }, [onSignOut]);

  // Handle login modal
  const handleOpenLoginModal = useCallback((tab: 'login' | 'register' = 'login') => {
    setLoginModalTab(tab);
    setShowLoginModal(true);
  }, []);

  const handleLoginSuccess = useCallback((type: UserType) => {
    setUserType(type);
    setShowLoginModal(false);
    updateUserFromStorage();
  }, [updateUserFromStorage]);

  // Handle anonymous continue
  const handleAnonymousContinue = useCallback(() => {
    setUserType('anonymous');
    setShowLoginModal(false);
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div className={cn("flex items-center space-x-2", className)}>
        <div className="h-8 w-20 bg-slate-200 rounded animate-pulse" />
      </div>
    );
  }

  // Anonymous user state
  if (userType === 'anonymous') {
    return (
      <>
        <div className={cn("flex items-center space-x-2", className)}>
          {compact ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleOpenLoginModal('login')}
              className="flex items-center space-x-2"
            >
              <LogIn className="h-4 w-4" />
              <span>Sign In</span>
            </Button>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleOpenLoginModal('login')}
                className="flex items-center space-x-2 text-slate-600 hover:text-slate-900"
              >
                <LogIn className="h-4 w-4" />
                <span>Sign In</span>
              </Button>
              <Button
                size="sm"
                onClick={() => handleOpenLoginModal('register')}
                className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700"
              >
                <UserPlus className="h-4 w-4" />
                <span>Register</span>
              </Button>
            </>
          )}
        </div>

        <LoginModal
          isOpen={showLoginModal}
          onClose={() => setShowLoginModal(false)}
          onLogin={handleLoginSuccess}
          onAnonymousContinue={handleAnonymousContinue}
        />
      </>
    );
  }

  // Authenticated user state
  const IconComponent = userInfo.icon;

  return (
    <>
      <div className={cn("flex items-center", className)}>
        {showUserMenu ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="ghost" 
                className="flex items-center space-x-3 h-auto py-2 px-3 hover:bg-slate-50"
              >
                <Avatar className="h-8 w-8">
                  <AvatarImage src={userInfo.avatar} alt={userInfo.displayName} />
                  <AvatarFallback className="bg-slate-100 text-slate-600 text-sm">
                    {userInfo.initials}
                  </AvatarFallback>
                </Avatar>
                
                {!compact && (
                  <>
                    <div className="flex flex-col items-start text-left">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-medium text-slate-900 max-w-32 truncate">
                          {userInfo.displayName}
                        </span>
                        <IconComponent className="h-3 w-3 text-slate-400" />
                      </div>
                      <Badge 
                        variant={userInfo.badgeVariant}
                        className={cn(
                          "text-xs h-4 px-1.5",
                          userType === 'verified' && "bg-green-100 text-green-800 border-green-200",
                          userType === 'registered' && "bg-blue-100 text-blue-800 border-blue-200"
                        )}
                      >
                        {userInfo.badge}
                      </Badge>
                    </div>
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  </>
                )}
              </Button>
            </DropdownMenuTrigger>
            
            <DropdownMenuContent align="end" className="w-64">
              <div className="px-3 py-2">
                <div className="flex items-center space-x-3">
                  <Avatar className="h-10 w-10">
                    <AvatarImage src={userInfo.avatar} alt={userInfo.displayName} />
                    <AvatarFallback className="bg-slate-100 text-slate-600">
                      {userInfo.initials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">
                      {userInfo.displayName}
                    </p>
                    {userInfo.email && (
                      <p className="text-xs text-slate-500 truncate">
                        {userInfo.email}
                      </p>
                    )}
                    <div className="flex items-center space-x-1 mt-1">
                      <Badge 
                        variant={userInfo.badgeVariant}
                        className={cn(
                          "text-xs h-4 px-1.5",
                          userType === 'verified' && "bg-green-100 text-green-800 border-green-200",
                          userType === 'registered' && "bg-blue-100 text-blue-800 border-blue-200"
                        )}
                      >
                        {userType === 'verified' && <CheckCircle2 className="h-2.5 w-2.5 mr-1" />}
                        {userType === 'registered' && <Clock className="h-2.5 w-2.5 mr-1" />}
                        {userInfo.badge}
                      </Badge>
                    </div>
                  </div>
                </div>
                <p className="text-xs text-slate-600 mt-2">
                  {userInfo.description}
                </p>
              </div>
              
              <DropdownMenuSeparator />
              
              {onProfileClick && (
                <DropdownMenuItem onClick={onProfileClick}>
                  <User className="h-4 w-4 mr-2" />
                  Profile
                </DropdownMenuItem>
              )}
              
              {onSettingsClick && (
                <DropdownMenuItem onClick={onSettingsClick}>
                  <Settings className="h-4 w-4 mr-2" />
                  Settings
                </DropdownMenuItem>
              )}
              
              {(onProfileClick || onSettingsClick) && <DropdownMenuSeparator />}
              
              <DropdownMenuItem 
                onClick={handleSignOut}
                className="text-red-600 focus:text-red-600 focus:bg-red-50"
              >
                <LogOut className="h-4 w-4 mr-2" />
                Sign Out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          // Simple display without dropdown
          <div className="flex items-center space-x-3">
            <Avatar className="h-8 w-8">
              <AvatarImage src={userInfo.avatar} alt={userInfo.displayName} />
              <AvatarFallback className="bg-slate-100 text-slate-600 text-sm">
                {userInfo.initials}
              </AvatarFallback>
            </Avatar>
            
            <div className="flex flex-col">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium text-slate-900">
                  {userInfo.displayName}
                </span>
                <IconComponent className="h-3 w-3 text-slate-400" />
              </div>
              <Badge 
                variant={userInfo.badgeVariant}
                className={cn(
                  "text-xs h-4 px-1.5 w-fit",
                  userType === 'verified' && "bg-green-100 text-green-800 border-green-200",
                  userType === 'registered' && "bg-blue-100 text-blue-800 border-blue-200"
                )}
              >
                {userInfo.badge}
              </Badge>
            </div>
            
            <Button
              variant="outline"
              size="sm"
              onClick={handleSignOut}
              className="text-slate-600 hover:text-slate-900"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      <LoginModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
        onLogin={handleLoginSuccess}
        onAnonymousContinue={handleAnonymousContinue}
      />
    </>
  );
};