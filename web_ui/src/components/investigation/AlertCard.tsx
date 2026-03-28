'use client';

import React from 'react';
import { clsx } from 'clsx';
import { AlertTriangle } from 'lucide-react';
import { ChatMessage } from '@/types/chat';
import { BrandIcon } from '@/components/BrandIcon';

export function AlertCard({ message }: { message: ChatMessage }) {
    if (!message.metadata) return null;

    return (
        <div className="mb-6">
            <div className="flex items-center gap-2 mb-2">
                <div className="w-6 h-6 rounded bg-[#00B67A] flex items-center justify-center text-white font-bold text-xs">
                    PD
                </div>
                <span className="text-sm font-bold text-stone-900 dark:text-white">PagerDuty</span>
                <span className="text-xs text-[#00B67A] bg-[#00B67A]/10 px-1.5 py-0.5 rounded uppercase font-bold">App</span>
                <span className="text-xs text-stone-500 ml-auto">{message.timestamp}</span>
            </div>
            
            <div className="bg-white dark:bg-stone-800 border-l-4 border-clay rounded-r-lg shadow-sm p-4 ml-8">
                <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle className="w-5 h-5 text-clay" />
                    <h3 className="text-lg font-bold text-stone-900 dark:text-white leading-tight">
                        [CRITICAL] Transaction Authorization Latency Spike
                    </h3>
                </div>

                <div className="grid grid-cols-2 gap-y-2 text-sm mb-4">
                    <div>
                        <span className="text-stone-500 block text-xs uppercase tracking-wide">Service</span>
                        <span className="font-mono text-stone-800 dark:text-stone-200 bg-stone-100 dark:bg-stone-700 px-1.5 py-0.5 rounded">
                            {message.metadata.service}
                        </span>
                    </div>
                    <div>
                        <span className="text-stone-500 block text-xs uppercase tracking-wide">Cluster</span>
                        <span className="font-mono text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/30 px-1.5 py-0.5 rounded">
                            {message.metadata.cluster}
                        </span>
                    </div>
                    <div>
                        <span className="text-stone-500 block text-xs uppercase tracking-wide">Urgency</span>
                        <span className="text-clay font-bold">{message.metadata.severity}</span>
                    </div>
                    <div>
                        <span className="text-stone-500 block text-xs uppercase tracking-wide">Impact</span>
                        <span className="text-stone-700 dark:text-stone-300">Auth Latency p99 {'>'} 5s</span>
                    </div>
                </div>

                <div className="flex gap-3">
                    <button className="px-4 py-1.5 bg-stone-100 dark:bg-stone-700 hover:bg-stone-200 dark:hover:bg-stone-700 text-stone-700 dark:text-stone-300 text-sm font-medium rounded transition-colors border border-stone-200 dark:border-stone-600">
                        Acknowledge
                    </button>
                    <button className="px-4 py-1.5 bg-stone-100 dark:bg-stone-700 hover:bg-stone-200 dark:hover:bg-stone-700 text-stone-700 dark:text-stone-300 text-sm font-medium rounded transition-colors border border-stone-200 dark:border-stone-600">
                        Escalate
                    </button>
                </div>
            </div>
        </div>
    );
}

