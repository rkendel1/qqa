
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

  const handleLogin = () => {
    toast.success("Successfully signed in!");
    onLogin(isVerified ? 'verified' : 'registered');
  };

  const handleRegister = () => {
    toast.success("Account created successfully!");
    onLogin(isVerified ? 'verified' : 'registered');
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
                <Input id="email" placeholder="your@email.com" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input id="password" type="password" />
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox id="verified" checked={isVerified} onCheckedChange={(checked) => 
                  setIsVerified(checked as boolean)} />
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
                  <Input id="firstName" placeholder="John" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lastName">Last Name</Label>
                  <Input id="lastName" placeholder="Doe" />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="newEmail">Email</Label>
                <Input id="newEmail" placeholder="your@email.com" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="newPassword">Password</Label>
                <Input id="newPassword" type="password" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="address">Home Address</Label>
                <Input id="address" placeholder="123 Main St, Springfield" />
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox id="verifiedReg" checked={isVerified} onCheckedChange={(checked) => 
                  setIsVerified(checked as boolean)} />
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
