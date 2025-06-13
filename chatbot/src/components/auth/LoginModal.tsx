import React, { useState, useCallback, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Eye, 
  EyeOff, 
  Loader2, 
  AlertCircle, 
  CheckCircle2,
  Shield,
  User,
  Mail,
  Lock,
  Home
} from 'lucide-react';
import { toast } from "sonner";
import { cn } from '@/lib/utils';

type UserType = 'anonymous' | 'registered' | 'verified';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogin: (userType: UserType) => void;
  onAnonymousContinue?: () => void;
  apiBaseUrl?: string;
}

interface FormErrors {
  email?: string;
  password?: string;
  firstName?: string;
  lastName?: string;
  address?: string;
  general?: string;
}

interface LoginFormData {
  email: string;
  password: string;
}

interface RegisterFormData {
  email: string;
  password: string;
  confirmPassword: string;
  firstName: string;
  lastName: string;
  address: string;
  acceptTerms: boolean;
}

const API_ENDPOINTS = {
  LOGIN: '/auth/login',
  SIGNUP: '/auth/signup',
  VERIFY_EMAIL: '/auth/verify-email',
} as const;

const VALIDATION_RULES = {
  email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  password: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/,
  name: /^[a-zA-Z\s]{2,30}$/,
} as const;

export const LoginModal: React.FC<LoginModalProps> = ({ 
  isOpen, 
  onClose, 
  onLogin,
  onAnonymousContinue,
  apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
}) => {
  // UI State
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  // Login Form State
  const [loginForm, setLoginForm] = useState<LoginFormData>({
    email: '',
    password: '',
  });

  // Registration Form State
  const [registerForm, setRegisterForm] = useState<RegisterFormData>({
    email: '',
    password: '',
    confirmPassword: '',
    firstName: '',
    lastName: '',
    address: '',
    acceptTerms: false,
  });

  const [isVerifiedRegistration, setIsVerifiedRegistration] = useState(false);

  // Clear errors when switching tabs
  useEffect(() => {
    setErrors({});
  }, [activeTab]);

  // Clear form data when modal closes
  useEffect(() => {
    if (!isOpen) {
      setLoginForm({ email: '', password: '' });
      setRegisterForm({
        email: '',
        password: '',
        confirmPassword: '',
        firstName: '',
        lastName: '',
        address: '',
        acceptTerms: false,
      });
      setErrors({});
      setIsVerifiedRegistration(false);
      setShowPassword(false);
      setShowConfirmPassword(false);
    }
  }, [isOpen]);

  // Validation Functions
  const validateEmail = (email: string): string | undefined => {
    if (!email.trim()) return 'Email is required';
    if (!VALIDATION_RULES.email.test(email)) return 'Please enter a valid email address';
    return undefined;
  };

  const validatePassword = (password: string, isRegistration = false): string | undefined => {
    if (!password) return 'Password is required';
    if (isRegistration && !VALIDATION_RULES.password.test(password)) {
      return 'Password must be at least 8 characters with uppercase, lowercase, number, and special character';
    }
    return undefined;
  };

  const validateName = (name: string, fieldName: string): string | undefined => {
    if (!name.trim()) return `${fieldName} is required`;
    if (!VALIDATION_RULES.name.test(name.trim())) {
      return `${fieldName} must be 2-30 characters and contain only letters and spaces`;
    }
    return undefined;
  };

  const validateAddress = (address: string): string | undefined => {
    if (isVerifiedRegistration && !address.trim()) {
      return 'Address is required for verified registration';
    }
    return undefined;
  };

  // API Functions
  const makeApiRequest = async (endpoint: string, data: any) => {
    const response = await fetch(`${apiBaseUrl}${endpoint}`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(data),
    });

    const responseData = await response.json();

    if (!response.ok) {
      throw new Error(responseData.detail || responseData.message || 'Request failed');
    }

    return responseData;
  };

  const storeUserData = (userData: any) => {
    const user = {
      id: userData.id,
      email: userData.email,
      first_name: userData.first_name,
      last_name: userData.last_name,
      address: userData.address,
      verified: userData.verified,
    };

    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem('access_token', userData.access_token);
    localStorage.setItem('token_type', userData.token_type);
    
    // Dispatch storage event to notify other components
    window.dispatchEvent(new Event('storage'));
    
    return user;
  };

  // Event Handlers
  const handleLogin = useCallback(async () => {
    setErrors({});
    
    // Validate form
    const emailError = validateEmail(loginForm.email);
    const passwordError = validatePassword(loginForm.password);

    if (emailError || passwordError) {
      setErrors({ email: emailError, password: passwordError });
      return;
    }

    setIsLoading(true);

    try {
      const data = await makeApiRequest(API_ENDPOINTS.LOGIN, {
        email: loginForm.email.trim().toLowerCase(),
        password: loginForm.password,
      });

      const user = storeUserData(data);
      
      toast.success(`Welcome back, ${user.first_name || 'User'}!`);
      onLogin(user.verified ? 'verified' : 'registered');
      onClose();

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Login failed';
      setErrors({ general: errorMessage });
      toast.error('Login failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  }, [loginForm, apiBaseUrl, onLogin, onClose]);

  const handleRegister = useCallback(async () => {
    setErrors({});
    
    // Validate form
    const emailError = validateEmail(registerForm.email);
    const passwordError = validatePassword(registerForm.password, true);
    const firstNameError = validateName(registerForm.firstName, 'First name');
    const lastNameError = validateName(registerForm.lastName, 'Last name');
    const addressError = validateAddress(registerForm.address);
    
    let confirmPasswordError: string | undefined;
    if (registerForm.password !== registerForm.confirmPassword) {
      confirmPasswordError = 'Passwords do not match';
    }

    let termsError: string | undefined;
    if (!registerForm.acceptTerms) {
      termsError = 'You must accept the terms and conditions';
    }

    const formErrors: FormErrors = {
      email: emailError,
      password: passwordError || confirmPasswordError,
      firstName: firstNameError,
      lastName: lastNameError,
      address: addressError,
      general: termsError,
    };

    // Remove undefined errors
    const cleanErrors = Object.fromEntries(
      Object.entries(formErrors).filter(([_, value]) => value !== undefined)
    );

    if (Object.keys(cleanErrors).length > 0) {
      setErrors(cleanErrors);
      return;
    }

    setIsLoading(true);

    try {
      const data = await makeApiRequest(API_ENDPOINTS.SIGNUP, {
        email: registerForm.email.trim().toLowerCase(),
        password: registerForm.password,
        first_name: registerForm.firstName.trim(),
        last_name: registerForm.lastName.trim(),
        address: registerForm.address.trim(),
        verified: isVerifiedRegistration,
      });

      const user = storeUserData(data);
      
      toast.success(`Welcome, ${user.first_name}! Your account has been created.`);
      onLogin(user.verified ? 'verified' : 'registered');
      onClose();

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Registration failed';
      setErrors({ general: errorMessage });
      toast.error('Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [registerForm, isVerifiedRegistration, apiBaseUrl, onLogin, onClose]);

  const handleAnonymousContinue = useCallback(() => {
    onLogin('anonymous');
    onAnonymousContinue?.();
    onClose();
  }, [onLogin, onAnonymousContinue, onClose]);

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isLoading) {
      if (activeTab === 'login') {
        handleLogin();
      } else {
        handleRegister();
      }
    }
  }, [activeTab, isLoading, handleLogin, handleRegister]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[480px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-blue-600" />
            City Hall Assistant Account
          </DialogTitle>
          <DialogDescription>
            Sign in or register to access enhanced services and personalized assistance.
          </DialogDescription>
        </DialogHeader>

        {/* Anonymous Continue Option */}
        <div className="bg-slate-50 p-4 rounded-lg border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <User className="h-5 w-5 text-slate-600" />
              <div>
                <p className="font-medium text-slate-900">Continue as Guest</p>
                <p className="text-sm text-slate-600">Limited access to basic services</p>
              </div>
            </div>
            <Button 
              variant="outline" 
              onClick={handleAnonymousContinue}
              disabled={isLoading}
            >
              Continue
            </Button>
          </div>
        </div>

        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-white px-2 text-slate-500">Or sign in for full access</span>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="login">Sign In</TabsTrigger>
            <TabsTrigger value="register">Register</TabsTrigger>
          </TabsList>
          
          {/* Error Alert */}
          {errors.general && (
            <Alert variant="destructive" className="mt-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{errors.general}</AlertDescription>
            </Alert>
          )}
          
          {/* Login Tab */}
          <TabsContent value="login" className="space-y-4 pt-4">
            <div className="space-y-4" onKeyPress={handleKeyPress}>
              <div className="space-y-2">
                <Label htmlFor="login-email" className="flex items-center gap-2">
                  <Mail className="h-4 w-4" />
                  Email
                </Label>
                <Input
                  id="login-email"
                  type="email"
                  placeholder="your@email.com"
                  value={loginForm.email}
                  onChange={(e) => setLoginForm(prev => ({ ...prev, email: e.target.value }))}
                  className={cn(errors.email && "border-red-500")}
                  disabled={isLoading}
                  autoComplete="email"
                />
                {errors.email && (
                  <p className="text-sm text-red-600">{errors.email}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="login-password" className="flex items-center gap-2">
                  <Lock className="h-4 w-4" />
                  Password
                </Label>
                <div className="relative">
                  <Input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your password"
                    value={loginForm.password}
                    onChange={(e) => setLoginForm(prev => ({ ...prev, password: e.target.value }))}
                    className={cn(errors.password && "border-red-500", "pr-10")}
                    disabled={isLoading}
                    autoComplete="current-password"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={isLoading}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                {errors.password && (
                  <p className="text-sm text-red-600">{errors.password}</p>
                )}
              </div>

              <Button 
                className="w-full" 
                onClick={handleLogin}
                disabled={isLoading || !loginForm.email || !loginForm.password}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Signing In...
                  </>
                ) : (
                  'Sign In'
                )}
              </Button>
            </div>
          </TabsContent>
          
          {/* Register Tab */}
          <TabsContent value="register" className="space-y-4 pt-4">
            <div className="space-y-4" onKeyPress={handleKeyPress}>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="firstName">First Name</Label>
                  <Input
                    id="firstName"
                    placeholder="John"
                    value={registerForm.firstName}
                    onChange={(e) => setRegisterForm(prev => ({ ...prev, firstName: e.target.value }))}
                    className={cn(errors.firstName && "border-red-500")}
                    disabled={isLoading}
                    autoComplete="given-name"
                  />
                  {errors.firstName && (
                    <p className="text-sm text-red-600">{errors.firstName}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lastName">Last Name</Label>
                  <Input
                    id="lastName"
                    placeholder="Doe"
                    value={registerForm.lastName}
                    onChange={(e) => setRegisterForm(prev => ({ ...prev, lastName: e.target.value }))}
                    className={cn(errors.lastName && "border-red-500")}
                    disabled={isLoading}
                    autoComplete="family-name"
                  />
                  {errors.lastName && (
                    <p className="text-sm text-red-600">{errors.lastName}</p>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="register-email" className="flex items-center gap-2">
                  <Mail className="h-4 w-4" />
                  Email
                </Label>
                <Input
                  id="register-email"
                  type="email"
                  placeholder="your@email.com"
                  value={registerForm.email}
                  onChange={(e) => setRegisterForm(prev => ({ ...prev, email: e.target.value }))}
                  className={cn(errors.email && "border-red-500")}
                  disabled={isLoading}
                  autoComplete="email"
                />
                {errors.email && (
                  <p className="text-sm text-red-600">{errors.email}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="register-password">Password</Label>
                <div className="relative">
                  <Input
                    id="register-password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Create a strong password"
                    value={registerForm.password}
                    onChange={(e) => setRegisterForm(prev => ({ ...prev, password: e.target.value }))}
                    className={cn(errors.password && "border-red-500", "pr-10")}
                    disabled={isLoading}
                    autoComplete="new-password"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={isLoading}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                <p className="text-xs text-slate-600">
                  At least 8 characters with uppercase, lowercase, number, and special character
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm-password">Confirm Password</Label>
                <div className="relative">
                  <Input
                    id="confirm-password"
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="Confirm your password"
                    value={registerForm.confirmPassword}
                    onChange={(e) => setRegisterForm(prev => ({ ...prev, confirmPassword: e.target.value }))}
                    className={cn(errors.password && "border-red-500", "pr-10")}
                    disabled={isLoading}
                    autoComplete="new-password"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    disabled={isLoading}
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                {errors.password && (
                  <p className="text-sm text-red-600">{errors.password}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="address" className="flex items-center gap-2">
                  <Home className="h-4 w-4" />
                  Home Address {isVerifiedRegistration && <span className="text-red-500">*</span>}
                </Label>
                <Input
                  id="address"
                  placeholder="123 Main St, Springfield"
                  value={registerForm.address}
                  onChange={(e) => setRegisterForm(prev => ({ ...prev, address: e.target.value }))}
                  className={cn(errors.address && "border-red-500")}
                  disabled={isLoading}
                  autoComplete="street-address"
                />
                {errors.address && (
                  <p className="text-sm text-red-600">{errors.address}</p>
                )}
              </div>

              <div className="space-y-4">
                <div className="flex items-start space-x-2">
                  <Checkbox
                    id="verified-registration"
                    checked={isVerifiedRegistration}
                    onCheckedChange={(checked) => setIsVerifiedRegistration(checked as boolean)}
                    disabled={isLoading}
                  />
                  <div className="grid gap-1.5 leading-none">
                    <Label 
                      htmlFor="verified-registration" 
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                    >
                      Register as verified resident
                    </Label>
                    <p className="text-xs text-slate-600">
                      Requires address verification for enhanced services
                    </p>
                  </div>
                </div>

                <div className="flex items-start space-x-2">
                  <Checkbox
                    id="accept-terms"
                    checked={registerForm.acceptTerms}
                    onCheckedChange={(checked) => setRegisterForm(prev => ({ ...prev, acceptTerms: checked as boolean }))}
                    disabled={isLoading}
                  />
                  <div className="grid gap-1.5 leading-none">
                    <Label 
                      htmlFor="accept-terms" 
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                    >
                      I accept the terms and conditions <span className="text-red-500">*</span>
                    </Label>
                    <p className="text-xs text-slate-600">
                      By registering, you agree to our privacy policy and terms of service
                    </p>
                  </div>
                </div>
              </div>

              <Button 
                className="w-full" 
                onClick={handleRegister}
                disabled={isLoading || !registerForm.acceptTerms}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating Account...
                  </>
                ) : (
                  'Create Account'
                )}
              </Button>
            </div>
          </TabsContent>
        </Tabs>

        <div className="text-center text-xs text-slate-500 mt-4">
          <p>Your data is protected and will only be used for municipal services.</p>
        </div>
      </DialogContent>
    </Dialog>
  );
};