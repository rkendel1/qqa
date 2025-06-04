import React, { useState } from 'react';
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
import { UseFormReturn } from 'react-hook-form';
import { toast } from "sonner";

type UserType = 'anonymous' | 'registered' | 'verified';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogin: (userType: UserType) => void;
}

export const LoginModal = ({ isOpen, onClose, onLogin }: LoginModalProps) => {
  const [activeTab, setActiveTab] = useState<string>('login');
  const [isVerified, setIsVerified] = useState<boolean>(false);
  // State hooks for login and registration fields
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [address, setAddress] = useState('');

  const handleLogin = async () => {
    try {
      const res = await fetch('http://localhost:8000/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword }),
      });
      if (!res.ok) throw new Error('Login failed');
      const data = await res.json();
      localStorage.setItem('user', JSON.stringify({
        id: data.id,
        email: data.email,
        first_name: data.first_name,
        last_name: data.last_name,
        address: data.address,
        verified: data.verified,
      }));
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('token_type', data.token_type);
      window.dispatchEvent(new Event('storage'));
      toast.success("Successfully signed in!");
      onLogin(isVerified ? 'verified' : 'registered');
    } catch (err) {
      toast.error("Login failed. Check your credentials.");
    }
  };

  const handleRegister = async () => {
    try {
      const res = await fetch('http://localhost:8000/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: registerEmail,
          password: registerPassword,
          first_name: firstName,
          last_name: lastName,
          address,
          verified: isVerified,
        }),
      });
      if (!res.ok) throw new Error('Registration failed');
      const data = await res.json();
      localStorage.setItem('user', JSON.stringify({
        id: data.id,
        email: data.email,
        first_name: data.first_name,
        last_name: data.last_name,
        address: data.address,
        verified: data.verified,
      }));
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('token_type', data.token_type);
      window.dispatchEvent(new Event('storage'));
      toast.success("Account created successfully!");
      onLogin(isVerified ? 'verified' : 'registered');
    } catch (err) {
      toast.error("Registration failed. Please try again.");
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>City Hall Assistant Account</DialogTitle>
          <DialogDescription>
            Sign in or register to access enhanced services and personalized assistance.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="login">Sign In</TabsTrigger>
            <TabsTrigger value="register">Register</TabsTrigger>
          </TabsList>
          
          <TabsContent value="login" className="space-y-4 pt-4">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  placeholder="your@email.com"
                  value={loginEmail}
                  onChange={e => setLoginEmail(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={loginPassword}
                  onChange={e => setLoginPassword(e.target.value)}
                />
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="verified"
                  checked={isVerified}
                  onCheckedChange={checked => setIsVerified(checked as boolean)}
                />
                <Label htmlFor="verified" className="text-sm">
                  Login as a verified resident
                </Label>
              </div>
              <Button className="w-full" onClick={handleLogin}>
                Sign In
              </Button>
            </div>
          </TabsContent>
          
          <TabsContent value="register" className="space-y-4 pt-4">
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="firstName">First Name</Label>
                  <Input
                    id="firstName"
                    placeholder="John"
                    value={firstName}
                    onChange={e => setFirstName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lastName">Last Name</Label>
                  <Input
                    id="lastName"
                    placeholder="Doe"
                    value={lastName}
                    onChange={e => setLastName(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="newEmail">Email</Label>
                <Input
                  id="newEmail"
                  placeholder="your@email.com"
                  value={registerEmail}
                  onChange={e => setRegisterEmail(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="newPassword">Password</Label>
                <Input
                  id="newPassword"
                  type="password"
                  value={registerPassword}
                  onChange={e => setRegisterPassword(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="address">Home Address</Label>
                <Input
                  id="address"
                  placeholder="123 Main St, Springfield"
                  value={address}
                  onChange={e => setAddress(e.target.value)}
                />
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="verifiedReg"
                  checked={isVerified}
                  onCheckedChange={checked => setIsVerified(checked as boolean)}
                />
                <Label htmlFor="verifiedReg" className="text-sm">
                  Register as a verified resident (requires address verification)
                </Label>
              </div>
              <Button className="w-full" onClick={handleRegister}>
                Register
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};
