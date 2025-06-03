
import React from 'react';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { Header } from '@/components/layout/Header';

const Index = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <Header />
      <main className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-slate-800 mb-4">
              City Hall Assistant
            </h1>
            <p className="text-xl text-slate-600 mb-2">
              Your 24/7 AI-powered municipal services helper
            </p>
            <p className="text-sm text-slate-500">
              Ask questions about permits, zoning, city services, and more
            </p>
          </div>
          <ChatInterface />
        </div>
      </main>
    </div>
  );
};

export default Index;
