import React from 'react';
import { ChatWidget } from './components/ChatWidget';
import { Shield, Lock, Cpu, Server, ArrowRight, ExternalLink, MessageSquare } from 'lucide-react';

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col justify-between selection:bg-indigo-500 selection:text-white">
      {/* Navigation */}
      <header className="border-b border-slate-200/80 dark:border-slate-800/80 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Brand Logo & Name linking to real Incerro website */}
          <a
            href="https://www.incerro.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2.5 group cursor-pointer transition-transform hover:scale-[1.01]"
            title="Open official Incerro website (incerro.ai)"
          >
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white font-bold shadow-md shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition-shadow">
              <Shield className="w-5 h-5" />
            </div>
            <span className="font-bold text-lg tracking-tight text-slate-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
              Incerro Enterprise
            </span>
          </a>

          {/* Executive Navigation & CTA */}
          <div className="flex items-center gap-3">
            <a
              href="https://www.incerro.ai/about-us"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden md:inline-flex text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-300 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              About Incerro
            </a>
            <a
              href="https://www.incerro.ai/services"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden md:inline-flex text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-300 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Services
            </a>
            <a
              href="https://www.incerro.ai/contact-us"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-300 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Contact
            </a>
            <a
              href="https://www.incerro.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white text-xs font-bold px-4 py-2 rounded-xl shadow-md shadow-indigo-500/20 hover:shadow-indigo-500/30 transition-all"
            >
              <span>Visit incerro.ai</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="max-w-6xl mx-auto px-6 py-20 flex-1 flex flex-col justify-center">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800/80 text-indigo-700 dark:text-indigo-300 text-xs font-semibold mb-6">
            <Lock className="w-3.5 h-3.5" />
            Zero-Trust AI Gateway & Hybrid RAG with FlashRank Neural Reranking
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-tight text-slate-900 dark:text-white">
            Secure Enterprise AI Assistant with FlashRank & Deterministic Guardrails
          </h1>

          <p className="mt-5 text-lg text-slate-600 dark:text-slate-400 leading-relaxed">
            A production-ready website assistant powered by ultra-fast Groq LPU inference, multi-layered security guardrails, hybrid vector retrieval, and FlashRank neural cross-encoder reranking. Grounded exclusively in verified company documentation with zero hallucinations.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button
              onClick={() => window.dispatchEvent(new CustomEvent('open-chat'))}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm px-6 py-3.5 rounded-xl shadow-lg shadow-indigo-600/25 flex items-center gap-2 transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
            >
              <MessageSquare className="w-4 h-4" />
              Launch Chat Assistant <ArrowRight className="w-4 h-4" />
            </button>
            <a
              href="https://www.incerro.ai/services"
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 font-semibold text-sm px-5 py-3.5 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors inline-flex items-center gap-1.5"
            >
              <span>Explore Incerro Services</span>
              <ExternalLink className="w-4 h-4 text-slate-400" />
            </a>
          </div>
        </div>

        {/* Feature Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-20">
          <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950 flex items-center justify-center text-indigo-600 dark:text-indigo-400 mb-4">
              <Shield className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-base text-slate-900 dark:text-white mb-2">
              Multi-Stage Guardrails
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Deterministic Unicode NFKC normalization, prompt injection scanners, role-play jailbreak detectors, and credit-card Luhn verification.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-xl bg-violet-50 dark:bg-violet-950 flex items-center justify-center text-violet-600 dark:text-violet-400 mb-4">
              <Cpu className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-base text-slate-900 dark:text-white mb-2">
              Hybrid RAG & FlashRank Reranker
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Combines dense vector embeddings with Okapi BM25 keyword matching, powered by FlashRank neural cross-encoder reranking and verified citation tags.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950 flex items-center justify-center text-emerald-600 dark:text-emerald-400 mb-4">
              <Server className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-base text-slate-900 dark:text-white mb-2">
              Resilient AI Gateway
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Sub-second Groq LPU inference, circuit breakers, exponential backoff with full jitter, automated fallbacks, and sliding window rate-limiting.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-800 py-8 text-center text-xs text-slate-400">
        © 2026 Incerro (Invasion Software Technologies Pvt Ltd). Official Enterprise AI Website Assistant.
      </footer>

      {/* Floating Chat Widget */}
      <ChatWidget />
    </div>
  );
};
