"use client";

import { useState } from "react";
import { CommandCenterDashboard } from "@/components/dashboard/CommandCenterDashboard";
import { ChatInterface } from "@/components/chat/ChatInterface";

export default function DashboardPage() {
  const [view, setView] = useState<"dashboard" | "chat">("dashboard");
  
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-4 py-3 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg flex items-center justify-center text-white font-bold">
              ORCA
            </div>
            <h1 className="text-xl font-semibold text-gray-900">Marine Intelligence Platform</h1>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setView("dashboard")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                view === "dashboard" 
                  ? "bg-blue-600 text-white" 
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              📊 Dashboard
            </button>
            <button
              onClick={() => setView("chat")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                view === "chat" 
                  ? "bg-blue-600 text-white" 
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              💬 Chat
            </button>
          </div>
        </div>
      </nav>
      
      <main className="flex-1">
        {view === "dashboard" ? (
          <CommandCenterDashboard />
        ) : (
          <ChatInterface />
        )}
      </main>
    </div>
  );
}